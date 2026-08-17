"""Device I/O profiles: screenshot strategies and user-interaction helpers."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import typing
from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol

from RsInstrument import RsInstrException, RsInstrument
from RsInstrument.mcp._common import safe_tool

logger = logging.getLogger(__name__)

_SIGGEN_PATTERN = re.compile(
    r"SMW|SMB|SMA|SMCV|SMM|SGT|SGS|SGU|SFI",
    re.IGNORECASE,
)
_MXO_PATTERN = re.compile(r"MXO", re.IGNORECASE)
_ANALYZER_PATTERN = re.compile(
    r"FSW|FSWX|FSWP|FSV3000|FSPN|FPS|FPL1000|AREG800A",
    re.IGNORECASE,
)
_FSW_SCREENSHOT_PATH = "C:/R_S/INSTR/USER/mcp_screenshot.png"


class ScreenshotStrategy(Protocol):
    """Protocol for model-family screenshot capture.

    The caller passes the desired OPC timeout (ms). The strategy MUST set
    ``inst.opc_timeout = opc_timeout`` before any ``write_with_opc`` call and may
    rely on the short-lived handle being discarded afterward.
    """

    def capture(self, inst: RsInstrument, *, opc_timeout: int) -> bytes: ...


@dataclass(frozen=True)
class DeviceIoProfile:
    """Model-family profile for screenshot and front-panel interaction."""

    name: str
    model_pattern: re.Pattern[str]
    screenshot_strategy: ScreenshotStrategy
    interaction_commands: tuple[str, ...]


@dataclass(frozen=True)
class DirectDataScreenshotStrategy:
    """Signal-generator style: ``HCOPy:DATA?`` binary block."""

    def capture(self, inst: RsInstrument, *, opc_timeout: int) -> bytes:
        inst.opc_timeout = opc_timeout
        inst.write("HCOPy:DEVice:LANGuage PNG")
        return inst.query_bin_block("HCOPy:DATA?")


@dataclass(frozen=True)
class MxoScreenshotStrategy:
    """MXO scopes: display-update wait then ``HCOPY:DATA?``."""

    settle_s: float = 1.0

    def capture(self, inst: RsInstrument, *, opc_timeout: int) -> bytes:
        inst.opc_timeout = opc_timeout
        inst.write("&NREN")
        try:
            inst.write_str_with_opc("&GTL;SYSTem:DISPlay:UPDate 1", timeout=opc_timeout)
        except RsInstrException:
            inst.write("&GTL")
            inst.write_str_with_opc("SYSTem:DISPlay:UPDate 1", timeout=opc_timeout)
        time.sleep(self.settle_s)
        inst.query("DIAGnostic:SERVice:DISPlay:WAIT?")
        inst.write("HCOPy:DEVice:LANGuage PNG")
        return inst.query_bin_block("HCOPY:DATA?")


@dataclass(frozen=True)
class FileScreenshotStrategy:
    """Analyzer-style file hardcopy with best-effort cleanup."""

    instrument_path: str = _FSW_SCREENSHOT_PATH

    def capture(self, inst: RsInstrument, *, opc_timeout: int) -> bytes:
        inst.opc_timeout = opc_timeout
        path = self.instrument_path
        inst.write("HCOPy:DEVice:LANGuage PNG")
        inst.write(f"MMEMory:NAME '{path}'")
        inst.write_with_opc("HCOPy:IMMediate", timeout=opc_timeout)
        try:
            return inst.query_bin_block(f"MMEMory:DATA? '{path}'")
        finally:
            try:
                inst.write(f"MMEMory:DELete '{path}'")
            except RsInstrException as exc:
                logger.warning(
                    "Screenshot cleanup failed for %s: %s",
                    path,
                    exc,
                )


@dataclass(frozen=True)
class FallbackScreenshotStrategy:
    """Generic configurable instrument-side path without cleanup."""

    screenshot_path: str = "/var/screenshot.png"

    def capture(self, inst: RsInstrument, *, opc_timeout: int) -> bytes:
        inst.opc_timeout = opc_timeout
        path = self.screenshot_path
        inst.write("HCOPy:DEVice:LANGuage PNG")
        inst.write("HCOPy:IMMediate")
        return inst.query_bin_block(f"MMEM:DATA? '{path}'")


@dataclass(frozen=True)
class DeviceIoProfileRegistry:
    """Ordered profile lookup; first match wins; fallback always last."""

    profiles: tuple[DeviceIoProfile, ...]

    @classmethod
    def defaults(
        cls,
        additional_profiles: Collection[DeviceIoProfile] = (),
    ) -> DeviceIoProfileRegistry:
        builtin = (
            DeviceIoProfile(
                name="siggen",
                model_pattern=_SIGGEN_PATTERN,
                screenshot_strategy=DirectDataScreenshotStrategy(),
                interaction_commands=("&NREN",),
            ),
            DeviceIoProfile(
                name="mxo",
                model_pattern=_MXO_PATTERN,
                screenshot_strategy=MxoScreenshotStrategy(),
                interaction_commands=("&NREN",),
            ),
            DeviceIoProfile(
                name="analyzer",
                model_pattern=_ANALYZER_PATTERN,
                screenshot_strategy=FileScreenshotStrategy(),
                interaction_commands=("SYST:DISP:UPD ON",),
            ),
            DeviceIoProfile(
                name="fallback",
                model_pattern=re.compile(r".*"),
                screenshot_strategy=FallbackScreenshotStrategy(),
                interaction_commands=(),
            ),
        )
        return cls(profiles=tuple(additional_profiles) + builtin)

    def for_model(self, model: str) -> DeviceIoProfile:
        for profile in self.profiles:
            if profile.model_pattern.search(model or ""):
                return profile
        return self.profiles[-1]


def go_to_local(resource: str, *, mixed_mode: bool = True) -> None:
    """Restore local front-panel control (shared by GTL and Enable-User-Interaction)."""
    try:
        with RsInstrument(resource) as inst:
            try:
                inst.go_to_local(mixed_mode)
            except RsInstrException:
                try:
                    inst.go_to_local()
                except RsInstrException:
                    inst.write("@LOC")
    except RsInstrException as exc:
        logger.warning(
            "Local front-panel control restore (GTL) skipped for %s: %s",
            resource,
            exc,
        )


def _idn_model(resource: str) -> str:
    with RsInstrument(resource) as inst:
        idn = inst.query("*IDN?").strip()
    parts = idn.split(",")
    return parts[1].strip() if len(parts) > 1 else idn


@safe_tool
async def instrument_go_to_local(resource: str) -> str:
    """Send instrument to local front-panel control (GTL)."""
    await asyncio.to_thread(go_to_local, resource, mixed_mode=True)
    return "Local front-panel control restored."


def make_instrument_get_screenshot(
    device_profiles: DeviceIoProfileRegistry | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build profile-aware ``Instrument-Get-Screenshot``."""
    registry = device_profiles or DeviceIoProfileRegistry.defaults()

    @safe_tool
    async def instrument_get_screenshot(
        resource: str,
        opc_timeout: int = 10000,
        screenshot_path: str = "/var/screenshot.png",
    ) -> str:
        """Capture a PNG screenshot from the instrument display."""

        def _get_screenshot() -> tuple[bytes, str | None]:
            model = _idn_model(resource)
            profile = registry.for_model(model)
            strategy = profile.screenshot_strategy
            warning: str | None = None
            if isinstance(strategy, FallbackScreenshotStrategy):
                strategy = FallbackScreenshotStrategy(screenshot_path=screenshot_path)
            with RsInstrument(resource) as inst:
                data = strategy.capture(inst, opc_timeout=opc_timeout)
            return data, warning

        img_data, warning = await asyncio.to_thread(_get_screenshot)
        payload: dict[str, typing.Any] = {
            "mime_type": "image/png",
            "data": base64.b64encode(img_data).decode("ascii"),
        }
        if warning:
            payload["warning"] = warning
        return json.dumps(payload)

    return instrument_get_screenshot


def make_instrument_enable_user_interaction(
    device_profiles: DeviceIoProfileRegistry | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build ``Instrument-Enable-User-Interaction``."""
    registry = device_profiles or DeviceIoProfileRegistry.defaults()

    @safe_tool
    async def instrument_enable_user_interaction(
        resource: str,
        release_local: bool = False,
        opc_timeout: int = 5000,
    ) -> str:
        """Enable front-panel/display interaction while keeping remote SCPI usable."""

        def _enable() -> str:
            model = _idn_model(resource)
            profile = registry.for_model(model)
            with RsInstrument(resource) as inst:
                inst.opc_timeout = opc_timeout
                for command in profile.interaction_commands:
                    inst.write(command)
            if release_local or not profile.interaction_commands:
                go_to_local(resource, mixed_mode=True)
            if profile.interaction_commands:
                return (
                    f"User interaction enabled via profile {profile.name!r} "
                    f"({', '.join(profile.interaction_commands)})."
                )
            return "User interaction: fallback go-to-local applied (no profile SCPI)."

        return await asyncio.to_thread(_enable)

    return instrument_enable_user_interaction
