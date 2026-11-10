"""Singleton instrumentor providing OTEL tracer, histogram, and span helpers for SCPI commands."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

try:
    # noinspection PyUnusedImports
    from opentelemetry import metrics as otel_metrics

    # noinspection PyUnusedImports
    from opentelemetry import trace as otel_trace

    # noinspection PyUnusedImports
    from opentelemetry.metrics import Meter

    # noinspection PyUnusedImports
    from opentelemetry.trace import SpanKind, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

log = logging.getLogger(__name__)

_NOOP = object()
"""Sentinel yielded by ``scpi_span`` when OTEL is inactive."""

SCPI_LATENCY_METRIC = "instrument.scpi.latency"
"""Name of the SCPI round-trip latency histogram."""

SCPI_ERRORS_METRIC = "instrument.scpi.errors"
"""Name of the SCPI error counter. Its presence allows feature detection."""


def host_from_resource(resource_name: str) -> str:
    """Extract the lowercase host from a TCPIP VISA resource string.

    Examples:
        ``TCPIP0::SMBV100B-104445::inst0::INSTR`` gives ``smbv100b-104445``,
        ``TCPIP::[fe80::1]::5025::SOCKET`` gives ``fe80::1``.

    Non-TCPIP resources (USB, GPIB, ASRL), unbracketed IPv6 and malformed
    names give an empty string.  This function never raises.
    """
    try:
        if not isinstance(resource_name, str):
            return ""
        scheme, separator, rest = resource_name.strip().partition("::")
        if not separator or not scheme.upper().startswith("TCPIP"):
            return ""
        if rest.startswith("["):
            closing = rest.find("]")
            if closing < 0:
                return ""
            host = rest[1:closing]
        else:
            parts = rest.split("::")
            if len(parts) > 3:
                # VISA TCPIP grammar allows at most host, LAN device or port, and
                # an INSTR/SOCKET suffix. More tokens mean an unbracketed IPv6 address.
                return ""
            host = parts[0]
        return host.strip().lower()
    except Exception:  # pragma: no cover - defensive, must never raise
        return ""


class ScpiInstrumentor:
    """Singleton that provides a tracer and latency histogram for SCPI instrumentation.

    When OTEL is not configured the ``scpi_span`` context manager is a
    zero-cost noop so call-sites never need conditional guards.
    """

    _instance: ScpiInstrumentor | None = None

    def __new__(cls) -> ScpiInstrumentor:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        # noinspection PyTypeChecker
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._enabled: bool = self._detect_enabled()
        self._tracer: Any = None
        self._latency_histogram: Any = None
        self._error_counter: Any = None
        self._extra_attributes: dict[str, str] = self._load_extra_attributes()

        if self._enabled and _OTEL_AVAILABLE:
            self._tracer = otel_trace.get_tracer(
                "rs_instrument",
                schema_url="https://opentelemetry.io/schemas/1.21.0",
            )
            meter: Meter = otel_metrics.get_meter("rs_instrument")
            self._latency_histogram = meter.create_histogram(
                name=SCPI_LATENCY_METRIC,
                description="SCPI command round-trip time",
                unit="s",
            )
            self._error_counter = meter.create_counter(
                name=SCPI_ERRORS_METRIC,
                description="Number of failed SCPI operations",
                unit="{error}",
            )

    @staticmethod
    def _detect_enabled() -> bool:
        """Determine whether OTEL tracing should be active.

        Priority:
        1. ``RS_INSTRUMENT_OTEL_ENABLED`` explicit override (``true`` / ``false``)
        2. Presence of ``OTEL_TRACES_EXPORTER`` or ``OTEL_EXPORTER_OTLP_ENDPOINT``
        3. Default to ``False``
        """
        if not _OTEL_AVAILABLE:
            return False
        explicit = os.environ.get("RS_INSTRUMENT_OTEL_ENABLED", "")
        if explicit.lower() == "false":
            return False
        if explicit.lower() == "true":
            return True
        return bool(
            os.environ.get("OTEL_TRACES_EXPORTER", "")
            or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        )

    @staticmethod
    def _load_extra_attributes() -> dict[str, str]:
        """Parse ``RS_INSTRUMENT_OTEL_ATTRIBUTES`` into a dict.

        Expected format: ``key1=value1,key2=value2``.
        Malformed pairs (missing ``=``) are silently skipped.
        """
        raw = os.environ.get("RS_INSTRUMENT_OTEL_ATTRIBUTES", "")
        attrs: dict[str, str] = {}
        for pair in raw.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                attrs[key.strip()] = value.strip()
        return attrs

    @property
    def enabled(self) -> bool:
        """Return ``True`` when OTEL tracing is active."""
        return self._enabled

    @contextmanager
    def scpi_span(
        self,
        *,
        operation: str,
        command: str,
        direction: str,
        firmware_version: str,
        resource_name: str,
        instrument_model: str,
        serial_number: str,
        material_number: str,
        extra_attributes: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Context manager wrapping an SCPI operation with a span and histogram.

        Yields the OTEL span when active or ``_NOOP`` when tracing is
        disabled.  Elapsed time is always recorded in the
        ``instrument.scpi.latency`` histogram.

        Args:
            operation: Human-readable span name (e.g. ``"SCPI write"``).
            command: The SCPI command string.
            direction: ``"write"`` or ``"query"``.
            firmware_version: Instrument firmware version from ``*IDN?``.
            resource_name: VISA resource string.
            instrument_model: Full instrument model from
                ``full_instrument_model_name`` (e.g. ``"SMBV100B"``).
            serial_number: Pure unit serial (e.g. ``"100012"``), split
                from ``instrument_serial_number``.
            material_number: Material / part number (e.g.
                ``"1423.1003K02"``), split from ``instrument_serial_number``.
            extra_attributes: Additional key-value pairs merged into the span.
        """
        if not self._enabled or self._tracer is None:
            yield _NOOP
            return

        host = host_from_resource(resource_name)
        attributes = {
            "instrument.scpi.command": command,
            "instrument.scpi.direction": direction,
            "instrument.firmware_version": firmware_version,
            "instrument.resource_name": resource_name,
            "instrument.model": instrument_model,
            "instrument.serial_number": serial_number,
            "instrument.material_number": material_number,
            "instrument.host": host,
            **self._extra_attributes,
            **(extra_attributes or {}),
        }

        with self._tracer.start_as_current_span(
            name=operation,
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ) as span:
            start = time.perf_counter()
            error_type: str = ""
            try:
                yield span
            except Exception as exc:
                error_type = type(exc).__name__
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            finally:
                elapsed = time.perf_counter() - start
                metric_attributes = {
                    "command": command.split(maxsplit=1)[0] if command else "",
                    "direction": direction,
                    "firmware_version": firmware_version,
                    "instrument.model": instrument_model,
                    "instrument.material_number": material_number,
                    "instrument.host": host,
                }
                # OpenTelemetry convention: error.type is only present on failure.
                if error_type:
                    metric_attributes["error.type"] = error_type
                # Metric failures must never replace the caller's own exception.
                if self._latency_histogram is not None:
                    try:
                        self._latency_histogram.record(elapsed, attributes=metric_attributes)
                    except Exception:
                        log.debug(
                            "Failed to record SCPI latency histogram",
                            exc_info=True,
                        )
                # ``error_type`` is set by the except block above; ty cannot see that.
                if error_type and self._error_counter is not None:  # ty: ignore[redundant-condition]
                    try:
                        self._error_counter.add(1, attributes=metric_attributes)
                    except Exception:
                        log.debug(
                            "Failed to record SCPI error counter",
                            exc_info=True,
                        )
