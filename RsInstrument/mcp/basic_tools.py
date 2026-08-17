"""Basic SCPI I/O tools: query, write, reset, fetch-errors, SCPI-exists, discovery."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import typing

from RsInstrument import (
    Discovery,
    DiscoverySnapshot,
    RsInstrException,
    RsInstrument,
)
from RsInstrument.Internal.Discovery import run_discovery
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.scpi_tree_match import (
    match_scpi_command,
    normalize_scpi_header_lines,
)
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.write_elicitation import _authorize_write

DEFAULT_DISCOVERY_EXPRESSION = "?*::INSTR"

_scpi_header_cache: dict[str, list[str] | None] = {}
_mcp_discovery: Discovery | None = None
_mcp_discovery_lock = threading.Lock()


def _get_scpi_headers(resource: str, timeout_ms: int) -> list[str] | None:
    """Load SCPI help headers from the instrument (lazy, once per resource)."""
    if resource in _scpi_header_cache:
        return _scpi_header_cache[resource]
    try:
        with RsInstrument(resource) as inst:
            previous_timeout = inst.visa_timeout
            try:
                inst.visa_timeout = timeout_ms
                raw = inst.query_str("SYST:HELP:HEAD?")
            finally:
                inst.visa_timeout = previous_timeout
        parsed = normalize_scpi_header_lines(raw)
        _scpi_header_cache[resource] = parsed
        return parsed
    except RsInstrException:
        _scpi_header_cache[resource] = None
        return None


@safe_tool
async def instrument_query_scpi(
    command: str,
    resource: str,
    opc_timeout: int = 5000,
) -> str:
    """Query a command from an instrument via RsInstrument."""

    def _query() -> str:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            return inst.query(command).strip()

    return await asyncio.to_thread(_query)


@safe_tool
async def instrument_fetch_errors(
    resource: str,
    opc_timeout: int = 5000,
) -> str:
    """Fetch errors from an instrument via RsInstrument."""

    def _fetch_errors() -> list[tuple[int, str]] | None:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            return inst.query_all_errors_with_codes()

    errors = await asyncio.to_thread(_fetch_errors)
    if not errors:
        return "No errors."
    return json.dumps([{"code": code, "message": msg} for code, msg in errors])


def make_instrument_write_scpi(
    write_policy: ScpiWritePolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build a policy-bound ``Instrument-Write-SCPI`` tool callable."""
    policy = write_policy or ScpiWritePolicy.defaults()

    @safe_tool
    async def instrument_write_scpi(
        ctx: typing.Any,
        command: str,
        resource: str,
        opc_timeout: int = 5000,
        confirm: bool = False,
    ) -> typing.Any:
        """Write SCPI with MCP write-policy gate and optional elicitation."""
        decision = await _authorize_write(
            ctx,
            command=command,
            resource=resource,
            confirm=confirm,
            policy=policy,
        )
        if decision is not None:
            return decision

        def _do_write() -> str:
            with RsInstrument(resource) as inst:
                inst.opc_timeout = opc_timeout
                inst.write(command)
            return "Write command executed successfully."

        return await asyncio.to_thread(_do_write)

    return instrument_write_scpi


def make_instrument_reset(
    write_policy: ScpiWritePolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build a policy-bound ``Instrument-Reset`` tool callable."""
    policy = write_policy or ScpiWritePolicy.defaults()

    @safe_tool
    async def instrument_reset(
        ctx: typing.Any,
        resource: str,
        opc_timeout: int = 5000,
        confirm: bool = False,
    ) -> typing.Any:
        """Reset instrument with MCP write-policy gate (*RST)."""
        decision = await _authorize_write(
            ctx,
            command="*RST",
            resource=resource,
            confirm=confirm,
            policy=policy,
        )
        if decision is not None:
            return decision

        def _do_reset() -> str:
            with RsInstrument(resource) as inst:
                inst.opc_timeout = opc_timeout
                inst.reset()
            return "Instrument reset successfully."

        return await asyncio.to_thread(_do_reset)

    return instrument_reset


@safe_tool
async def instrument_scpi_exists(
    command: str,
    resource: str,
    opc_timeout: int = 10000,
) -> str:
    """Check whether a SCPI command path appears in the instrument help header tree."""
    headers = await asyncio.to_thread(_get_scpi_headers, resource, opc_timeout)
    if headers is None:
        return json.dumps(
            {
                "exists": False,
                "matched_header": None,
                "matches": [],
                "match_type": "none",
                "truncated": False,
                "supported": False,
            },
        )
    result = match_scpi_command(command, headers)
    return json.dumps(result.to_dict())


def _get_mcp_discovery() -> Discovery:
    """Return the module-owned lazy Discovery singleton (created on first use)."""
    global _mcp_discovery
    with _mcp_discovery_lock:
        if _mcp_discovery is None:
            _mcp_discovery = Discovery(
                expression=DEFAULT_DISCOVERY_EXPRESSION,
                identify=False,
                ttl_s=30.0,
                enrich_lxi=True,
                enrich_dns=True,
                mdns_timeout_s=2.0,
            )
        return _mcp_discovery


def _snapshot_to_json(
    snapshot: DiscoverySnapshot,
    *,
    source: str,
    model: str,
    manufacturer: str,
) -> str:
    """Serialize a DiscoverySnapshot to the MCP JSON contract."""
    instruments = snapshot.filter(model=model, manufacturer=manufacturer)
    return json.dumps(
        {
            "source": source,
            "timestamp": snapshot.timestamp.isoformat(),
            "expression": snapshot.expression,
            "visa_select": snapshot.visa_select,
            "method_notes": snapshot.method_notes,
            "count": len(instruments),
            "instruments": [dataclasses.asdict(item) for item in instruments],
        },
    )


@safe_tool
async def instrument_discovery(
    expression: str = DEFAULT_DISCOVERY_EXPRESSION,
    visa_select: str | None = None,
    identify: bool = False,
    refresh: bool = False,
    model: str = "",
    manufacturer: str = "",
) -> str:
    """Return VISA-visible instruments as stable JSON."""
    if (model or manufacturer) and not identify:
        return "Error: model/manufacturer filters require identify=true"

    use_live = (
        identify
        or refresh
        or expression != DEFAULT_DISCOVERY_EXPRESSION
        or visa_select is not None
    )

    if use_live:
        snapshot = await asyncio.to_thread(
            run_discovery,
            expression=expression,
            visa_select=visa_select,
            identify=identify,
            enrich_lxi=True,
            enrich_dns=True,
            mdns_timeout_s=2.0,
        )
        source = "live"
    else:
        result = await asyncio.to_thread(
            _get_mcp_discovery().get,
            use_cache=True,
        )
        snapshot = result.snapshot
        source = result.source

    return _snapshot_to_json(
        snapshot,
        source=source,
        model=model,
        manufacturer=manufacturer,
    )


# Default unbound callables for tests / simple experiments only.
# Production servers must use create_builtin_tool_specs(settings) (or
# add_builtin_tools / run) so write tools close over the caller's policy.
instrument_write_scpi = make_instrument_write_scpi()
instrument_reset = make_instrument_reset()
