"""Batch SCPI policy, parsing, and Instrument-Batch-SCPI factory."""

from __future__ import annotations

import asyncio
import json
import typing
from collections.abc import Collection
from dataclasses import dataclass

from RsInstrument import RsInstrument
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy, evaluate_write
from RsInstrument.mcp.write_elicitation import (
    _authorize_write,
    _gate_json,
    _get_idn_model,
    batch_confirm_key,
    decode_batch_state,
    encode_batch_state,
)

_IEEE_OPC_HEADERS: frozenset[str] = frozenset({"*RST", "*RCL"})


@dataclass(frozen=True)
class BatchScpiCommand:
    """Single batch SCPI command with optional per-item timeout override."""

    command: str
    opc_timeout: int | None = None


@dataclass(frozen=True)
class ScpiBatchPolicy:
    """Controls auto OPC-sync headers and trailing error-queue collection."""

    opc_command_headers: frozenset[str]
    collect_errors: bool = True

    def __post_init__(self) -> None:
        for header in self.opc_command_headers:
            _validate_opc_header(header)

    @classmethod
    def defaults(
        cls,
        additional_opc_commands: Collection[str] = (),
    ) -> ScpiBatchPolicy:
        """IEEE 488.2 defaults ``*RST`` / ``*RCL``, optionally extended."""
        extras = frozenset(_normalize_opc_header(h) for h in additional_opc_commands)
        return cls(
            opc_command_headers=_IEEE_OPC_HEADERS | extras,
            collect_errors=True,
        )

    def needs_opc(self, command: str) -> bool:
        """Return True when any write statement header should use ``write_with_opc``."""
        for part in command.split(";"):
            header = _first_write_header(part)
            if header in self.opc_command_headers:
                return True
        return False


def is_scpi_query(command: str) -> bool:
    """Return True when the first SCPI statement is a query (header ends with ``?``).

    Quoted string contents are ignored so paths like ``'a?.bin'`` do not force query mode.
    """
    first = command.strip().split(";", 1)[0].strip()
    if not first:
        return False
    in_single = False
    in_double = False
    for ch in first:
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "?" and not in_single and not in_double:
            return True
    return False


def _normalize_opc_header(header: str) -> str:
    normalized = " ".join(header.strip().upper().split())
    if normalized.startswith(":"):
        normalized = normalized[1:]
    _validate_opc_header(normalized)
    return normalized


def _validate_opc_header(header: str) -> None:
    if not header:
        raise ValueError("OPC command header must be non-empty")
    if header != header.upper():
        raise ValueError(f"OPC command header must be uppercase: {header!r}")
    if "?" in header:
        raise ValueError(f"OPC command header must not be a query: {header!r}")
    if any(ch.isspace() for ch in header):
        raise ValueError(f"OPC command header must not contain arguments: {header!r}")


def _first_write_header(command: str) -> str:
    first = command.strip().split(";", 1)[0].strip()
    normalized = " ".join(first.upper().split())
    if normalized.startswith(":"):
        normalized = normalized[1:]
    if normalized.endswith("?"):
        normalized = normalized[:-1].rstrip()
    return normalized.split(None, 1)[0] if normalized else ""


def parse_batch_entry(
    entry: str | BatchScpiCommand | dict[str, typing.Any],
    default_timeout: int,
) -> BatchScpiCommand:
    """Normalize one batch entry to ``BatchScpiCommand``."""
    if isinstance(entry, str):
        return BatchScpiCommand(command=entry, opc_timeout=default_timeout)
    if isinstance(entry, BatchScpiCommand):
        timeout = (
            default_timeout if entry.opc_timeout is None else int(entry.opc_timeout)
        )
        return BatchScpiCommand(command=entry.command, opc_timeout=timeout)
    if isinstance(entry, dict):
        if "command" not in entry:
            raise ValueError("Missing key 'command' in batch command object")
        timeout = (
            default_timeout if "opc_timeout" not in entry else int(entry["opc_timeout"])
        )
        return BatchScpiCommand(command=str(entry["command"]), opc_timeout=timeout)
    raise TypeError(
        "Each batch entry must be a string, BatchScpiCommand, or object "
        "{'command': '...', 'opc_timeout': ...}",
    )


def _execute_write(
    resource: str,
    command: str,
    timeout_ms: int,
    *,
    with_opc: bool,
) -> str:
    with RsInstrument(resource) as inst:
        if with_opc:
            inst.write_with_opc(command, timeout=timeout_ms)
        else:
            inst.opc_timeout = timeout_ms
            inst.write(command)
    return "Write command executed successfully."


def _drain_error_queue(resource: str, timeout_ms: int) -> dict[str, typing.Any]:
    with RsInstrument(resource) as inst:
        inst.opc_timeout = timeout_ms
        errors = inst.query_all_errors_with_codes() or []
    return {
        "errors": [{"code": code, "message": msg} for code, msg in errors],
        "drained": True,
    }


def make_instrument_batch_scpi(
    write_policy: ScpiWritePolicy | None = None,
    batch_policy: ScpiBatchPolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build a policy-bound ``Instrument-Batch-SCPI`` tool callable."""
    policy = write_policy or ScpiWritePolicy.defaults()
    sync_policy = batch_policy or ScpiBatchPolicy.defaults()

    @safe_tool
    async def instrument_batch_scpi(
        ctx: typing.Any,
        commands: list[str | BatchScpiCommand | dict[str, typing.Any]],
        resource: str,
        opc_timeout: int = 5000,
        confirm: bool = False,
    ) -> typing.Any:
        """Batch SCPI with per-write gating, OPC sync, and dual-path elicitation."""
        outcomes, start_index = decode_batch_state(getattr(ctx, "request_state", None))
        results: list[dict[str, typing.Any]] = []

        for i in range(min(start_index, len(commands))):
            parsed = parse_batch_entry(commands[i], opc_timeout)
            code = outcomes[i] if i < len(outcomes) else "error"
            if code == "ok":
                results.append(
                    {
                        "command": parsed.command,
                        "result": "Write command executed successfully.",
                    }
                )
            elif code == "query":

                def _replay_query(
                    cmd: str = parsed.command,
                    tout: int = parsed.opc_timeout or opc_timeout,
                ) -> str:
                    with RsInstrument(resource) as inst:
                        inst.opc_timeout = tout
                        return inst.query(cmd).strip()

                try:
                    out = await asyncio.to_thread(_replay_query)
                    results.append({"command": parsed.command, "result": out})
                except Exception as exc:  # pylint: disable=broad-except
                    results.append(
                        {"command": parsed.command, "result": f"Error: {exc}"}
                    )
            elif code.startswith("error:"):
                results.append(
                    {"command": parsed.command, "result": f"Error: {code[6:]}"}
                )
            elif code in ("forbidden", "cancelled", "needs_confirmation"):
                model = await _get_idn_model(resource)
                gate = evaluate_write(parsed.command, model=model, policy=policy)
                results.append(
                    {
                        "command": parsed.command,
                        "result": json.loads(_gate_json(code, gate)),
                    }
                )
            else:
                results.append({"command": parsed.command, "result": f"Error: {code}"})

        for index in range(start_index, len(commands)):
            entry = commands[index]
            cmd = ""
            try:
                parsed = parse_batch_entry(entry, opc_timeout)
                cmd = parsed.command
                if is_scpi_query(cmd):

                    def _query(
                        c: str = cmd, t: int = parsed.opc_timeout or opc_timeout
                    ) -> str:
                        with RsInstrument(resource) as inst:
                            inst.opc_timeout = t
                            return inst.query(c).strip()

                    out = await asyncio.to_thread(_query)
                    results.append({"command": cmd, "result": out})
                    outcomes.append("query")
                    continue

                decision = await _authorize_write(
                    ctx,
                    command=cmd,
                    resource=resource,
                    confirm=confirm,
                    response_key=batch_confirm_key(index),
                    request_state=encode_batch_state(outcomes, index),
                    policy=policy,
                )
                if decision is not None and not isinstance(decision, str):
                    return decision
                if isinstance(decision, str):
                    payload = json.loads(decision)
                    results.append({"command": cmd, "result": payload})
                    outcomes.append(payload.get("gate", "error"))
                    continue

                with_opc = sync_policy.needs_opc(cmd)

                def _write(
                    c: str = cmd,
                    t: int = parsed.opc_timeout or opc_timeout,
                    opc: bool = with_opc,
                ) -> str:
                    return _execute_write(resource, c, t, with_opc=opc)

                out = await asyncio.to_thread(_write)
                results.append({"command": cmd, "result": out})
                outcomes.append("ok")
            except Exception as exc:  # pylint: disable=broad-except
                shown = cmd or str(entry)
                results.append({"command": shown, "result": f"Error: {exc}"})
                outcomes.append(f"error:{exc}")

        if sync_policy.collect_errors:
            try:
                drained = await asyncio.to_thread(
                    _drain_error_queue, resource, opc_timeout
                )
                results.append({"command": "<error-queue>", "result": drained})
            except Exception as exc:  # pylint: disable=broad-except
                results.append(
                    {
                        "command": "<error-queue>",
                        "result": f"Error: {exc}",
                    }
                )

        return json.dumps(results)

    return instrument_batch_scpi
