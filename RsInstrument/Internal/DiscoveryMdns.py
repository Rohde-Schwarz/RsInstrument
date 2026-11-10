"""Optional mDNS / DNS-SD discovery backend (requires zeroconf)."""

from __future__ import annotations

import importlib
import logging
import time
from dataclasses import replace
from typing import Any

from RsInstrument.Internal.Discovery import DiscoveredInstrument
from RsInstrument.Internal.DiscoveryEnrich import (
    infer_visa_from_services,
    is_usable_ipv4,
)

logger = logging.getLogger(__name__)

try:
    _zeroconf = importlib.import_module("zeroconf")
    ServiceBrowser = _zeroconf.ServiceBrowser
    Zeroconf = _zeroconf.Zeroconf
    _HAS_ZEROCONF = True
except ImportError:
    _HAS_ZEROCONF = False
    ServiceBrowser = None
    Zeroconf = None

_LXI_SERVICE_TYPES = [
    "_lxi._tcp.local.",
    "_hislip._tcp.local.",
    "_scpi-raw._tcp.local.",
    "_vxi-11._tcp.local.",
]


def mdns_available() -> bool:
    """Return True when the zeroconf package is importable."""
    return _HAS_ZEROCONF


def _preferred_ipv4(addresses: list[str]) -> str:
    """Return the first usable IPv4 address, or empty string."""
    for addr in addresses:
        if is_usable_ipv4(addr):
            return addr
    return ""


class _MdnsListener:
    """Collects mDNS service announcements during a browse window."""

    def __init__(self) -> None:
        self.instruments: dict[str, DiscoveredInstrument] = {}

    def _upsert(self, ip: str, service_type: str, info: Any) -> None:
        props = {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else str(v)
            )
            for k, v in (info.properties or {}).items()
        }
        if ip not in self.instruments:
            self.instruments[ip] = DiscoveredInstrument(
                resource="",
                ip=ip,
                discovery_source="mdns",
            )
        inst = self.instruments[ip]
        short = service_type.replace("._tcp.local.", "").replace(
            "._tcp.local", ""
        )
        services = tuple(dict.fromkeys([*inst.services, short]))
        self.instruments[ip] = replace(
            inst,
            manufacturer=props.get("Manufacturer", inst.manufacturer),
            model=props.get("Model", inst.model),
            serial=props.get("SerialNumber", inst.serial),
            firmware=props.get("FirmwareVersion", inst.firmware)
            or props.get("FirmwareRevision", inst.firmware),
            hostname=(info.server or inst.hostname or "").rstrip("."),
            services=services,
            discovery_source="mdns",
        )

    def add_service(self, zc: Any, type_: str, name: str) -> None:
        """Handle a newly discovered service."""
        info = zc.get_service_info(type_, name)
        if info is None:
            return
        addresses = info.parsed_addresses()
        ip = _preferred_ipv4(list(addresses))
        if not ip:
            return
        self._upsert(ip, type_, info)

    def remove_service(
        self, zc: Any, type_: str, name: str
    ) -> None:  # noqa: ARG002
        """Handle service removal (no-op during bounded browse)."""

    def update_service(self, zc: Any, type_: str, name: str) -> None:
        """Handle service update by re-processing it."""
        self.add_service(zc, type_, name)


def discover_via_mdns(timeout_s: float = 2.0) -> tuple[DiscoveredInstrument, ...]:
    """Browse LXI-related mDNS service types. Returns empty if zeroconf missing."""
    if not _HAS_ZEROCONF or timeout_s <= 0:
        return ()
    if Zeroconf is None or ServiceBrowser is None:
        return ()

    zc = Zeroconf()
    listener = _MdnsListener()
    try:
        browsers = [ServiceBrowser(zc, svc, listener) for svc in _LXI_SERVICE_TYPES]
        del browsers
        time.sleep(timeout_s)
    except Exception:
        logger.debug("mDNS browse failed", exc_info=True)
        return ()
    finally:
        try:
            zc.close()
        except Exception:
            logger.debug("Zeroconf close failed", exc_info=True)

    results: list[DiscoveredInstrument] = []
    for inst in listener.instruments.values():
        resource = infer_visa_from_services(inst.services, inst.ip)
        results.append(replace(inst, resource=resource))
    return tuple(results)
