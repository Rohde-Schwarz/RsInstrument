"""Pure discovery enrichment helpers (no VISA sessions).

IP parsing, LXI HTTP identification, reverse DNS, and merge of VISA/mDNS results.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as ET

from RsInstrument.Internal.Discovery import DiscoveredInstrument

logger = logging.getLogger(__name__)

_ENRICH_MAX_WORKERS = 8
_TCPIP_IP_RE = re.compile(r"TCPIP\d*::([^:]+)::", re.IGNORECASE)


def is_usable_ipv4(addr: str) -> bool:
    """Return True if *addr* is a non-link-local, non-loopback IPv4 address."""
    try:
        parsed = ipaddress.ip_address(addr)
        return (
            parsed.version == 4
            and not parsed.is_link_local
            and not parsed.is_loopback
            and not parsed.is_unspecified
        )
    except ValueError:
        return False


def parse_resource_ip(resource: str) -> str:
    r"""Extract a usable IPv4 address from a TCPIP VISA resource, or ``""``."""
    match = _TCPIP_IP_RE.match(resource.strip())
    if not match:
        return ""
    host = match.group(1)
    return host if is_usable_ipv4(host) else ""


def _normalize_service(raw: str) -> str:
    """Strip the ``._tcp.local.`` suffix to get a short service name."""
    return raw.replace("._tcp.local.", "").replace("._tcp.local", "")


def infer_visa_from_services(services: Iterable[str], ip: str) -> str:
    r"""Derive a VISA resource string from an IP and discovered service set.

    Selection order:
      1. _hislip  -> TCPIP::<ip>::hislip0
      2. _vxi-11  -> TCPIP::<ip>::INSTR
      3. _scpi-raw -> TCPIP::<ip>::5025::SOCKET
      4. otherwise -> ""
    """
    if not ip:
        return ""
    short = {_normalize_service(s) for s in services}
    if "_hislip" in short or "hislip" in short:
        return f"TCPIP::{ip}::hislip0"
    if "_vxi-11" in short or "vxi-11" in short:
        return f"TCPIP::{ip}::INSTR"
    if "_scpi-raw" in short or "scpi-raw" in short:
        return f"TCPIP::{ip}::5025::SOCKET"
    return ""


def _resolve_ptr(ip: str, timeout_s: float) -> str:
    """Resolve PTR hostname for *ip*; return empty string on failure."""
    prev = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout_s)
        hostname, _aliases, _addrs = socket.gethostbyaddr(ip)
        if hostname and hostname != ip:
            return hostname.rstrip(".")
    except (socket.herror, socket.gaierror, OSError, TimeoutError):
        return ""
    finally:
        socket.setdefaulttimeout(prev)
    return ""


def enrich_via_reverse_dns(
    instruments: tuple[DiscoveredInstrument, ...],
    timeout_s: float = 2.0,
    max_workers: int = _ENRICH_MAX_WORKERS,
) -> tuple[DiscoveredInstrument, ...]:
    """Fill ``hostname`` via parallel PTR lookups. Never raises."""
    if not instruments:
        return ()

    results = list(instruments)
    indexed = [(i, inst) for i, inst in enumerate(instruments) if inst.ip]
    if not indexed:
        return tuple(results)

    workers = max(1, min(max_workers, len(indexed)))
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="DiscoveryPtr"
    ) as pool:
        futures = {
            pool.submit(_resolve_ptr, inst.ip, timeout_s): idx for idx, inst in indexed
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                hostname = future.result()
            except Exception:
                logger.debug("PTR lookup failed", exc_info=True)
                hostname = ""
            if hostname:
                results[idx] = replace(results[idx], hostname=hostname)
    return tuple(results)


def _apply_lxi_xml(inst: DiscoveredInstrument, body: bytes) -> DiscoveredInstrument:
    """Parse LXI identification XML and fill missing identity fields."""
    root = ET.fromstring(body)
    ns = ""
    ns_match = re.match(r"\{([^}]+)\}", root.tag)
    if ns_match:
        ns = ns_match.group(1)

    def _find(tag: str) -> str:
        el = root.find(f"{{{ns}}}{tag}" if ns else tag)
        return (el.text or "").strip() if el is not None else ""

    return replace(
        inst,
        manufacturer=inst.manufacturer or _find("Manufacturer"),
        model=inst.model or _find("Model"),
        serial=inst.serial or _find("SerialNumber"),
        firmware=inst.firmware or _find("FirmwareRevision"),
    )


def _lxi_fetch_one(
    inst: DiscoveredInstrument, timeout_s: float
) -> DiscoveredInstrument:
    """GET /lxi/identification for one instrument; return unchanged on failure."""
    if not inst.ip or (inst.model and inst.serial):
        return inst
    url = f"http://{inst.ip}/lxi/identification"
    try:
        with urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
            body = resp.read(16_384)
        return _apply_lxi_xml(inst, body)
    except (URLError, OSError, ParseError, Exception):
        logger.debug("LXI HTTP enrich failed for %s", inst.ip, exc_info=True)
        return inst


def enrich_via_lxi_http(
    instruments: tuple[DiscoveredInstrument, ...],
    timeout_s: float = 2.0,
    max_workers: int = _ENRICH_MAX_WORKERS,
) -> tuple[DiscoveredInstrument, ...]:
    """Fill sparse identity from LXI HTTP identification. Never raises."""
    if not instruments:
        return ()

    results = list(instruments)
    indexed = [
        (i, inst)
        for i, inst in enumerate(instruments)
        if inst.ip and not (inst.model and inst.serial)
    ]
    if not indexed:
        return tuple(results)

    workers = max(1, min(max_workers, len(indexed)))
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="DiscoveryLxi"
    ) as pool:
        futures = {
            pool.submit(_lxi_fetch_one, inst, timeout_s): idx for idx, inst in indexed
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception:
                logger.debug("LXI worker failed", exc_info=True)
    return tuple(results)


def merge_discovery_results(
    visa_instruments: tuple[DiscoveredInstrument, ...],
    mdns_instruments: tuple[DiscoveredInstrument, ...],
) -> tuple[DiscoveredInstrument, ...]:
    """Merge VISA and mDNS results, deduplicating by IP where possible."""
    merged: dict[str, DiscoveredInstrument] = {}

    for inst in visa_instruments:
        key = inst.ip if inst.ip else inst.resource
        source = inst.discovery_source or "visa"
        merged[key] = replace(inst, discovery_source=source)

    for inst in mdns_instruments:
        key = inst.ip if inst.ip else inst.resource
        if key in merged:
            existing = merged[key]
            services = tuple(dict.fromkeys([*existing.services, *inst.services]))
            notes = tuple(dict.fromkeys([*existing.notes, *inst.notes]))
            merged[key] = replace(
                existing,
                discovery_source="both",
                manufacturer=existing.manufacturer or inst.manufacturer,
                model=existing.model or inst.model,
                serial=existing.serial or inst.serial,
                firmware=existing.firmware or inst.firmware,
                hostname=existing.hostname or inst.hostname,
                services=services,
                notes=notes,
                resource=existing.resource or inst.resource,
            )
        else:
            source = inst.discovery_source or "mdns"
            merged[key] = replace(inst, discovery_source=source)

    return tuple(merged.values())
