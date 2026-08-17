"""Singleton instrumentor providing OTEL tracer, histogram, and span helpers for SCPI commands."""

from __future__ import annotations

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

_NOOP = object()
"""Sentinel yielded by ``scpi_span`` when OTEL is inactive."""


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
        self._extra_attributes: dict[str, str] = self._load_extra_attributes()

        if self._enabled and _OTEL_AVAILABLE:
            self._tracer = otel_trace.get_tracer(
                "rs_instrument",
                schema_url="https://opentelemetry.io/schemas/1.21.0",
            )
            meter: Meter = otel_metrics.get_meter("rs_instrument")
            self._latency_histogram = meter.create_histogram(
                name="instrument.scpi.latency",
                description="SCPI command round-trip time",
                unit="s",
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

        attributes = {
            "instrument.scpi.command": command,
            "instrument.scpi.direction": direction,
            "instrument.firmware_version": firmware_version,
            "instrument.resource_name": resource_name,
            "instrument.model": instrument_model,
            "instrument.serial_number": serial_number,
            "instrument.material_number": material_number,
            **self._extra_attributes,
            **(extra_attributes or {}),
        }

        with self._tracer.start_as_current_span(
            name=operation,
            kind=SpanKind.CLIENT,
            attributes=attributes,
        ) as span:
            start = time.perf_counter()
            try:
                yield span
            except Exception as exc:
                span.set_status(StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                raise
            finally:
                elapsed = time.perf_counter() - start
                if self._latency_histogram is not None:
                    self._latency_histogram.record(
                        elapsed,
                        attributes={
                            "command": command.split(maxsplit=1)[0] if command else "",
                            "direction": direction,
                            "firmware_version": firmware_version,
                            "instrument.model": instrument_model,
                            "instrument.material_number": material_number,
                        },
                    )
