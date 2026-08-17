"""Monkey-patching logic that wires OTEL spans and histograms into RsInstrument methods.

``setup_otel()`` patches the class; ``teardown_otel()`` restores it.
All method sets, the patching helper, and the ENV-to-kwarg mapping live here
so that ``otel/__init__.py`` stays a thin public re-export surface.
"""

from __future__ import annotations

import functools
import os
from typing import Any

from RsInstrument.RsInstrument import RsInstrument

from .instrumentor import ScpiInstrumentor

_OTEL_ENV_MAP: tuple[tuple[str, str], ...] = (
    ("traces_exporter", "OTEL_TRACES_EXPORTER"),
    ("otlp_endpoint", "OTEL_EXPORTER_OTLP_ENDPOINT"),
    ("otlp_traces_endpoint", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
    ("otlp_protocol", "OTEL_EXPORTER_OTLP_PROTOCOL"),
    ("otlp_headers", "OTEL_EXPORTER_OTLP_HEADERS"),
    ("service_name", "OTEL_SERVICE_NAME"),
    ("resource_attributes", "OTEL_RESOURCE_ATTRIBUTES"),
)
"""Maps ``setup_otel`` keyword arguments to standard OTEL environment variables."""

_WRITE_METHODS: frozenset[str] = frozenset(
    {
        "write",
        "write_str",
        "write_int",
        "write_int_with_opc",
        "write_float",
        "write_float_with_opc",
        "write_bool",
        "write_bool_with_opc",
        "write_str_with_opc",
        "write_with_opc",
        "write_bin_block",
        "write_bin_block_from_file",
    }
)
"""Methods whose first positional arg after ``self`` is ``cmd: str``."""

_QUERY_METHODS: frozenset[str] = frozenset(
    {
        "query",
        "query_str",
        "query_stripped",
        "query_str_stripped",
        "query_bool",
        "query_int",
        "query_float",
        "query_str_list",
        "query_bool_list",
        "query_str_with_opc",
        "query_with_opc",
        "query_str_list_with_opc",
        "query_bool_with_opc",
        "query_bool_list_with_opc",
        "query_int_with_opc",
        "query_float_with_opc",
        "query_bin_block",
        "query_bin_block_with_opc",
        "query_bin_or_ascii_float_list",
        "query_bin_or_ascii_float_list_with_opc",
        "query_bin_or_ascii_int_list",
        "query_bin_or_ascii_int_list_with_opc",
        "query_bin_block_to_file",
        "query_bin_block_to_file_with_opc",
    }
)
"""Methods whose first positional arg after ``self`` is ``query: str``."""

_FIXED_COMMAND_METHODS: dict[str, str] = {
    "query_opc": "*OPC?",
    "reset": "*RST",
    "clear_status": "*CLS",
    "self_test": "*TST?",
    "check_status": "SYST:ERR?",
}
"""Methods where the SCPI command is implicit (not in the argument list)."""

_ORIGINALS: dict[str, Any] = {}
"""Original unbound methods stored before patching; also the idempotency guard."""


def _apply_env_kwargs(otel_locals: dict[str, Any]) -> None:
    """Set OTEL environment variables from the matching ``setup_otel`` kwargs.

    Only non-``None`` values are written.  Values are converted to ``str``
    so callers may pass e.g. ``bool`` for convenience.
    """
    for param, env_key in _OTEL_ENV_MAP:
        value = otel_locals.get(param)
        if value is not None:
            os.environ[env_key] = str(value)


def setup_otel(
    *,
    traces_exporter: str | None = None,
    otlp_endpoint: str | None = None,
    otlp_traces_endpoint: str | None = None,
    otlp_protocol: str | None = None,
    otlp_headers: str | None = None,
    service_name: str | None = None,
    resource_attributes: str | None = None,
    extra_attributes: dict[str, str] | None = None,
    exclude: set[str] | None = None,
) -> None:
    """Patch ``RsInstrument`` to emit OTEL spans and metrics for every SCPI call.

    Idempotent -- subsequent calls are no-ops.
    No-op when OTEL is not configured (no exporter / endpoint ENV vars).

    Any OTEL configuration kwarg (e.g. ``traces_exporter``, ``otlp_endpoint``)
    is written to its corresponding environment variable before the
    instrumentor reads them, so callers don't need to set ``os.environ``
    manually.

    Args:
        traces_exporter: Maps to ``OTEL_TRACES_EXPORTER`` (e.g. ``"otlp"``).
        otlp_endpoint: Maps to ``OTEL_EXPORTER_OTLP_ENDPOINT``.
        otlp_traces_endpoint: Maps to ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``.
        otlp_protocol: Maps to ``OTEL_EXPORTER_OTLP_PROTOCOL`` (e.g. ``"grpc"``).
        otlp_headers: Maps to ``OTEL_EXPORTER_OTLP_HEADERS``.
        service_name: Maps to ``OTEL_SERVICE_NAME``.
        resource_attributes: Maps to ``OTEL_RESOURCE_ATTRIBUTES``.
        extra_attributes: Additional key-value pairs added to every span.
        exclude: Method names to skip when patching.
    """
    if _ORIGINALS:
        return

    _apply_env_kwargs(locals())

    instrumentor = ScpiInstrumentor()
    if not instrumentor.enabled:
        return

    merged_exclude = exclude or set()
    extras = extra_attributes or {}

    for name in _WRITE_METHODS - merged_exclude:
        _patch_method(name, "write", None, instrumentor, extras)

    for name in _QUERY_METHODS - merged_exclude:
        _patch_method(name, "query", None, instrumentor, extras)

    for name, fixed_cmd in _FIXED_COMMAND_METHODS.items():
        if name not in merged_exclude:
            _patch_method(name, "query", fixed_cmd, instrumentor, extras)


def teardown_otel() -> None:
    """Restore all original ``RsInstrument`` methods. Reverses ``setup_otel()``."""
    for name, original in _ORIGINALS.items():
        setattr(RsInstrument, name, original)
    _ORIGINALS.clear()


def _patch_method(
    name: str,
    direction: str,
    fixed_command: str | None,
    instrumentor: ScpiInstrumentor,
    extra_attributes: dict[str, str],
) -> None:
    """Replace a single ``RsInstrument`` method with a traced wrapper.

    The wrapper extracts ``material_number`` and ``serial_number`` by
    splitting ``instrument_serial_number`` on ``/``.  When no ``/`` is
    present (e.g. simulated instruments), both default to the raw value.

    Args:
        name: Method name on the class.
        direction: ``"write"`` or ``"query"`` for span classification.
        fixed_command: If not ``None``, use this as the SCPI command instead
            of extracting from the first positional argument.
        instrumentor: The ``ScpiInstrumentor`` singleton.
        extra_attributes: Extra span attributes forwarded from ``setup_otel``.
    """
    original = getattr(RsInstrument, name, None)
    if original is None or not callable(original):
        return

    @functools.wraps(original)
    def _traced(self: RsInstrument, *args: Any, **kwargs: Any) -> Any:
        if fixed_command is not None:
            cmd = fixed_command
        else:
            # noinspection PyStringConversionWithoutDunderMethod
            cmd = (
                str(args[0])
                if args
                else str(kwargs.get("cmd", kwargs.get("query", "")))
            )

        raw_serial = self.instrument_serial_number
        parts = raw_serial.split("/", 1)
        material_number = parts[0]
        serial_number = parts[1] if len(parts) > 1 else parts[0]

        with instrumentor.scpi_span(
            operation=f"SCPI {direction} {name}",
            command=cmd,
            direction=direction,
            firmware_version=self.instrument_firmware_version,
            resource_name=self.resource_name,
            instrument_model=self.full_instrument_model_name,
            serial_number=serial_number,
            material_number=material_number,
            extra_attributes=extra_attributes,
        ):
            return original(self, *args, **kwargs)

    _ORIGINALS[name] = original
    setattr(RsInstrument, name, _traced)
