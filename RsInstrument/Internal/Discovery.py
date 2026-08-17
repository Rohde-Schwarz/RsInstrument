"""In-process instrument discovery: VISA find, optional *IDN?, TTL cache."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

import pyvisa
import pyvisa.constants

from RsInstrument.Internal.InstrumentErrors import RsInstrException
from RsInstrument.Internal.VisaSession import VisaSession

if TYPE_CHECKING:
    from pyvisa import ResourceManager

logger = logging.getLogger(__name__)

_SOCKETIO_ALIASES = frozenset({"socketio", "socket", "none"})
_DEFAULT_EXPRESSION = "?*::INSTR"
_IDENTIFY_MAX_WORKERS = 8


@dataclass(frozen=True)
class DiscoveredInstrument:
    """One discovered instrument."""

    resource: str
    identified: bool = False
    manufacturer: str = ""
    model: str = ""
    serial: str = ""
    firmware: str = ""
    idn_raw: str = ""
    ip: str = ""
    hostname: str = ""
    services: tuple[str, ...] = ()
    discovery_source: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiscoverySnapshot:
    """Immutable point-in-time discovery result."""

    instruments: tuple[DiscoveredInstrument, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expression: str = _DEFAULT_EXPRESSION
    visa_select: str | None = None
    identify: bool = False
    method_notes: dict[str, str] = field(default_factory=dict)

    def filter(
        self,
        model: str = "",
        manufacturer: str = "",
    ) -> tuple[DiscoveredInstrument, ...]:
        """Filter instruments by model/manufacturer substring (case-insensitive).

        Returns an empty tuple when called on a snapshot where identify=False
        was used, because model/manufacturer fields are empty strings.
        This is intentional — callers should use identify=True before filtering.
        """
        result = self.instruments
        if model:
            result = tuple(i for i in result if model.lower() in i.model.lower())
        if manufacturer:
            result = tuple(
                i for i in result if manufacturer.lower() in i.manufacturer.lower()
            )
        return result


@dataclass(frozen=True)
class DiscoveryResult:
    """Return type of Discovery.get() and Discovery.refresh()."""

    snapshot: DiscoverySnapshot
    source: Literal["cache", "live"]


def _cache_key(
    expression: str,
    visa_select: str | None,
    identify: bool,
    *,
    enrich_lxi: bool = False,
    enrich_dns: bool = False,
    mdns: bool = False,
) -> str:
    """Deterministic cache key from every parameter that shapes the snapshot.

    Enrichment flags belong in the key: two configurations that differ only in
    enrichment produce different instruments and must not share a cache entry.
    """
    return (
        f"{expression}|{visa_select or ''}|{identify}"
        f"|lxi={enrich_lxi}|dns={enrich_dns}|mdns={mdns}"
    )


def _filter_dataclass_kwargs(cls: type, data: dict) -> dict:
    """Keep only keys that exist as fields on *cls* (forward-compatible loads)."""
    allowed = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in allowed}


def _snapshot_to_dict(snapshot: DiscoverySnapshot) -> dict:
    """Serialize a DiscoverySnapshot for JSON file storage."""
    data = asdict(snapshot)
    data["timestamp"] = snapshot.timestamp.isoformat()
    return data


def _snapshot_from_dict(data: dict) -> DiscoverySnapshot:
    """Reconstruct a DiscoverySnapshot from JSON file storage."""
    instruments = []
    for item in data.get("instruments", ()):
        if not isinstance(item, dict):
            continue
        filtered = _filter_dataclass_kwargs(DiscoveredInstrument, item)
        if "services" in filtered and isinstance(filtered["services"], list):
            filtered["services"] = tuple(filtered["services"])
        if "notes" in filtered and isinstance(filtered["notes"], list):
            filtered["notes"] = tuple(filtered["notes"])
        instruments.append(DiscoveredInstrument(**filtered))
    timestamp_raw = data.get("timestamp")
    if isinstance(timestamp_raw, str):
        timestamp = datetime.fromisoformat(timestamp_raw)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)
    snap_kwargs = _filter_dataclass_kwargs(
        DiscoverySnapshot,
        {
            "instruments": tuple(instruments),
            "timestamp": timestamp,
            "expression": data.get("expression", _DEFAULT_EXPRESSION),
            "visa_select": data.get("visa_select"),
            "identify": bool(data.get("identify", False)),
            "method_notes": data.get("method_notes") or {},
        },
    )
    return DiscoverySnapshot(**snap_kwargs)


class DiscoveryCacheStore(Protocol):
    """Pluggable cache backend for Discovery.

    Thread-safety contract: ``load`` / ``save`` / ``delete`` are safe for
    concurrent calls from multiple threads in the same process.
    """

    def load(self, key: str) -> tuple[DiscoverySnapshot, float] | None:
        """Return (snapshot, age_seconds) or None if not cached."""
        ...

    def save(self, key: str, snapshot: DiscoverySnapshot) -> None:
        """Persist snapshot under key. Store records its own timestamp."""
        ...

    def delete(self, key: str) -> None:
        """Remove the entry for key. No-op if not present."""
        ...


class InMemoryDiscoveryCache:
    """Process-local cache using time.monotonic() for age tracking."""

    def __init__(self) -> None:
        """Create an empty in-memory cache."""
        self._data: dict[str, tuple[DiscoverySnapshot, float]] = {}
        self._lock = threading.Lock()

    def load(self, key: str) -> tuple[DiscoverySnapshot, float] | None:
        """Return (snapshot, age_seconds) or None if not cached."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            snapshot, stored_at = entry
            age_s = time.monotonic() - stored_at
            return snapshot, age_s

    def save(self, key: str, snapshot: DiscoverySnapshot) -> None:
        """Persist snapshot under key using monotonic time."""
        with self._lock:
            self._data[key] = (snapshot, time.monotonic())

    def delete(self, key: str) -> None:
        """Remove the entry for key. No-op if not present."""
        with self._lock:
            self._data.pop(key, None)


class FileDiscoveryCache:
    """JSON file cache using UTC wall clock for cross-process age tracking.

    One file = one cache entry. No merge — each save fully replaces the file.
    """

    _VERSION = 1

    def __init__(self, path: str | Path) -> None:
        """Create a file-backed cache at ``path`` (one entry per file)."""
        self._path = Path(path)
        self._lock = threading.Lock()

    def load(self, key: str) -> tuple[DiscoverySnapshot, float] | None:
        """Return (snapshot, age_seconds) or None if missing/invalid."""
        try:
            with self._lock:
                text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        if data.get("key") != key or data.get("version") != self._VERSION:
            return None
        raw_snapshot = data.get("snapshot")
        if not isinstance(raw_snapshot, dict):
            return None
        try:
            stored_at = datetime.fromisoformat(data["stored_at_utc"])
            if stored_at.tzinfo is None:
                stored_at = stored_at.replace(tzinfo=timezone.utc)
            age_s = (datetime.now(timezone.utc) - stored_at).total_seconds()
            snapshot = _snapshot_from_dict(raw_snapshot)
        except (KeyError, TypeError, ValueError):
            return None
        return snapshot, age_s

    def save(self, key: str, snapshot: DiscoverySnapshot) -> None:
        """Atomically replace the cache file with ``snapshot`` for ``key``."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "version": self._VERSION,
                "key": key,
                "stored_at_utc": datetime.now(timezone.utc).isoformat(),
                "snapshot": _snapshot_to_dict(snapshot),
            },
            indent=2,
        )
        with self._lock:
            fd, tmp_name = tempfile.mkstemp(
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.replace(tmp_name, self._path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

    def delete(self, key: str) -> None:
        """Delete the cache file. No-op if missing."""
        with self._lock:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass


def _reject_socketio(visa_select: str | None) -> None:
    """Raise if visa_select refers to the SocketIO backend (no VISA find)."""
    if visa_select is None:
        return
    if visa_select.lower() in _SOCKETIO_ALIASES:
        raise RsInstrException(
            "SocketIO does not support VISA discovery; "
            "use visa_select='rs' or pass explicit resource strings",
        )


def parse_idn(idn_raw: str) -> dict[str, str]:
    """Parse IEEE 488.2 *IDN? response: manufacturer,model,serial,firmware."""
    parts = [p.strip() for p in idn_raw.split(",", maxsplit=3)]
    return {
        "manufacturer": parts[0] if len(parts) > 0 else "",
        "model": parts[1] if len(parts) > 1 else "",
        "serial": parts[2] if len(parts) > 2 else "",
        "firmware": parts[3] if len(parts) > 3 else "",
    }


def _find(
    expression: str,
    visa_select: str | None,
) -> tuple[tuple[str, ...], ResourceManager]:
    """Open a fresh RM, list resources, return (resource_tuple, rm).

    Caller is responsible for closing the returned RM.
    """
    _reject_socketio(visa_select)
    try:
        rm = VisaSession.get_resource_manager(visa_select)
    except Exception as exc:
        raise RsInstrException(f"Failed to open VISA ResourceManager: {exc}") from exc
    try:
        resources = rm.list_resources(expression)
    except Exception as exc:
        try:
            rm.close()
        except Exception:
            logger.debug("Failed to close ResourceManager after list_resources error", exc_info=True)
        raise RsInstrException(f"VISA list_resources failed: {exc}") from exc
    return tuple(resources), rm


def _identify_one(
    resource: str,
    visa_select: str | None,
    timeout_ms: int,
    *,
    ip: str = "",
    hostname: str = "",
    services: tuple[str, ...] = (),
    discovery_source: str = "",
    notes: tuple[str, ...] = (),
) -> DiscoveredInstrument:
    """Attempt *IDN? on a single resource using a dedicated RM for this thread."""
    rm = None
    session = None
    base_kwargs = {
        "resource": resource,
        "ip": ip,
        "hostname": hostname,
        "services": services,
        "discovery_source": discovery_source,
        "notes": notes,
    }
    try:
        rm = VisaSession.get_resource_manager(visa_select)
        session = rm.open_resource(
            resource,
            timeout=timeout_ms,
            access_mode=pyvisa.constants.AccessModes.no_lock,
        )
        idn_raw = session.query("*IDN?").strip()
        parsed = parse_idn(idn_raw)
        return DiscoveredInstrument(
            identified=True,
            idn_raw=idn_raw,
            **base_kwargs,
            **parsed,
        )
    except Exception:
        logger.debug("Identify failed for %s", resource, exc_info=True)
        return DiscoveredInstrument(identified=False, **base_kwargs)
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                logger.debug("Session close failed for %s", resource, exc_info=True)
        if rm is not None:
            try:
                rm.close()
            except Exception:
                logger.debug("Identify RM close failed for %s", resource, exc_info=True)


def _identify_all(
    instruments: tuple[DiscoveredInstrument, ...],
    visa_select: str | None,
    timeout_ms: int,
    max_workers: int = _IDENTIFY_MAX_WORKERS,
) -> tuple[DiscoveredInstrument, ...]:
    """Identify all resources in parallel (I/O-bound ThreadPoolExecutor)."""
    if not instruments:
        return ()
    _reject_socketio(visa_select)
    workers = max(1, min(max_workers, len(instruments)))
    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="DiscoveryIdentify",
    ) as pool:
        return tuple(
            pool.map(
                lambda inst: _identify_one(
                    inst.resource,
                    visa_select,
                    timeout_ms,
                    ip=inst.ip,
                    hostname=inst.hostname,
                    services=inst.services,
                    discovery_source=inst.discovery_source,
                    notes=inst.notes,
                ),
                instruments,
            ),
        )


def run_discovery(
    expression: str = _DEFAULT_EXPRESSION,
    visa_select: str | None = None,
    identify: bool = False,
    identify_timeout_ms: int = 3000,
    identify_workers: int = _IDENTIFY_MAX_WORKERS,
    *,
    enrich_lxi: bool = False,
    enrich_dns: bool = False,
    mdns_timeout_s: float = 0.0,
    lxi_timeout_s: float = 2.0,
    dns_timeout_s: float = 2.0,
    enrich_workers: int = _IDENTIFY_MAX_WORKERS,
) -> DiscoverySnapshot:
    """One-shot find (+ optional enrich / parallel identify). Fresh find RM."""
    from RsInstrument.Internal.DiscoveryEnrich import (
        enrich_via_lxi_http,
        enrich_via_reverse_dns,
        merge_discovery_results,
        parse_resource_ip,
    )
    from RsInstrument.Internal.DiscoveryMdns import (
        discover_via_mdns,
        mdns_available,
    )

    method_notes: dict[str, str] = {}
    resources, rm = _find(expression, visa_select)
    try:
        rm.close()
    except Exception:
        logger.debug("Find RM close failed", exc_info=True)
    method_notes["visa"] = f"ok ({len(resources)} found)"

    instruments = tuple(
        DiscoveredInstrument(
            resource=r,
            ip=parse_resource_ip(r),
            discovery_source="visa",
        )
        for r in resources
    )

    if mdns_timeout_s > 0 and mdns_available():
        try:
            mdns_hits = discover_via_mdns(timeout_s=mdns_timeout_s)
            method_notes["mdns"] = f"ok ({len(mdns_hits)} found)"
            instruments = merge_discovery_results(instruments, mdns_hits)
        except Exception:
            logger.debug("mDNS discovery failed", exc_info=True)
            method_notes["mdns"] = "error"
    elif mdns_timeout_s > 0:
        method_notes["mdns"] = "skipped (zeroconf not installed)"
    else:
        method_notes["mdns"] = "skipped"

    if enrich_lxi:
        before = sum(1 for i in instruments if i.model)
        instruments = enrich_via_lxi_http(
            instruments,
            timeout_s=lxi_timeout_s,
            max_workers=enrich_workers,
        )
        after = sum(1 for i in instruments if i.model)
        enriched = max(0, after - before)
        method_notes["lxi_http"] = (
            f"{enriched} enriched" if enriched else "none enriched"
        )
    else:
        method_notes["lxi_http"] = "skipped"

    if enrich_dns:
        instruments = enrich_via_reverse_dns(
            instruments,
            timeout_s=dns_timeout_s,
            max_workers=enrich_workers,
        )
        resolved = sum(1 for i in instruments if i.hostname)
        method_notes["reverse_dns"] = f"{resolved} resolved"
    else:
        method_notes["reverse_dns"] = "skipped"

    if identify:
        instruments = _identify_all(
            instruments,
            visa_select,
            identify_timeout_ms,
            max_workers=identify_workers,
        )
        method_notes["identify"] = "ok"
    else:
        method_notes["identify"] = "skipped"

    return DiscoverySnapshot(
        instruments=instruments,
        expression=expression,
        visa_select=visa_select,
        identify=identify,
        method_notes=method_notes,
    )


class Discovery:
    """Pull-based instrument discovery with TTL cache.

    No background threads — cache is refreshed on demand via get().
    Caches DiscoverySnapshot results only; never holds RsInstrument sessions.
    """

    def __init__(
        self,
        expression: str = _DEFAULT_EXPRESSION,
        visa_select: str | None = None,
        identify: bool = False,
        identify_timeout_ms: int = 3000,
        identify_workers: int = _IDENTIFY_MAX_WORKERS,
        ttl_s: float = 30.0,
        cache: DiscoveryCacheStore | None = None,
        *,
        enrich_lxi: bool = False,
        enrich_dns: bool = False,
        mdns_timeout_s: float = 0.0,
        lxi_timeout_s: float = 2.0,
        dns_timeout_s: float = 2.0,
        enrich_workers: int = _IDENTIFY_MAX_WORKERS,
    ) -> None:
        """Configure discovery parameters, TTL, enrichment, and cache backend."""
        self._expression = expression
        self._visa_select = visa_select
        self._identify = identify
        self._identify_timeout_ms = identify_timeout_ms
        self._identify_workers = identify_workers
        self._ttl_s = ttl_s
        self._enrich_lxi = enrich_lxi
        self._enrich_dns = enrich_dns
        self._mdns_timeout_s = mdns_timeout_s
        self._lxi_timeout_s = lxi_timeout_s
        self._dns_timeout_s = dns_timeout_s
        self._enrich_workers = enrich_workers
        self._cache: DiscoveryCacheStore = cache or InMemoryDiscoveryCache()
        self._key = _cache_key(
            expression,
            visa_select,
            identify,
            enrich_lxi=enrich_lxi,
            enrich_dns=enrich_dns,
            mdns=mdns_timeout_s > 0,
        )
        self._lock = threading.Lock()

    def get(self, *, use_cache: bool = True) -> DiscoveryResult:
        """Return cached snapshot if fresh; else live-scan, save, return."""
        if use_cache:
            with self._lock:
                entry = self._cache.load(self._key)
            if entry is not None:
                snapshot, age_s = entry
                if age_s <= self._ttl_s:
                    return DiscoveryResult(snapshot=snapshot, source="cache")

        snapshot = run_discovery(
            expression=self._expression,
            visa_select=self._visa_select,
            identify=self._identify,
            identify_timeout_ms=self._identify_timeout_ms,
            identify_workers=self._identify_workers,
            enrich_lxi=self._enrich_lxi,
            enrich_dns=self._enrich_dns,
            mdns_timeout_s=self._mdns_timeout_s,
            lxi_timeout_s=self._lxi_timeout_s,
            dns_timeout_s=self._dns_timeout_s,
            enrich_workers=self._enrich_workers,
        )
        with self._lock:
            self._cache.save(self._key, snapshot)

        return DiscoveryResult(snapshot=snapshot, source="live")

    def refresh(self) -> DiscoveryResult:
        """Force live scan and update cache."""
        return self.get(use_cache=False)

    def clear_cache(self) -> None:
        """Invalidate the store entry without scanning."""
        with self._lock:
            self._cache.delete(self._key)

    @property
    def snapshot(self) -> DiscoverySnapshot | None:
        """Last stored snapshot if present (ignores TTL). None if never scanned."""
        with self._lock:
            entry = self._cache.load(self._key)
        return entry[0] if entry is not None else None
