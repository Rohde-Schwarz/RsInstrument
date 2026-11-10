"""Batch SCPI policy, parsing, and Instrument-Batch-SCPI factory."""

from __future__ import annotations

import asyncio
import typing
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from RsInstrument import RsInstrument
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.scpi_write_policy import (
    ScpiWritePolicy,
    contains_query_marker,
    evaluate_write,
    iter_write_segments,
)
from RsInstrument.mcp.write_elicitation import (
    InvalidBatchStateError,
    _authorize_write,
    _gate_dict,
    _get_idn_model,
    batch_confirm_key,
    commands_prefix_digest,
    decode_batch_state,
    encode_batch_state,
)

try:
    from fastmcp import Context
except ImportError:
    Context = None  # type: ignore[assignment,misc]

_IEEE_OPC_HEADERS: frozenset[str] = frozenset({"*RST", "*RCL"})


@dataclass(frozen=True)
class BatchScpiCommand:
    """Single batch SCPI command with optional per-item timeout and resource overrides."""

    command: str
    opc_timeout: int | None = None
    resource: str | None = None


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
    """Return True when any statement in the message is a query.

    A mixed message such as ``OUTP ON;FREQ?`` must be read, or its response stays on
    the bus and the next query reads stale data. Quoted text is ignored, so paths
    like ``'a?.bin'`` do not force query mode.
    """
    return contains_query_marker(command)


def _normalize_opc_header(header: str) -> str:
    normalized = " ".join(header.strip().upper().split())
    normalized = normalized.removeprefix(":")
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
    normalized = normalized.removeprefix(":")
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
        return BatchScpiCommand(command=entry.command, opc_timeout=timeout, resource=entry.resource)
    if isinstance(entry, dict):
        if "command" not in entry:
            raise ValueError("Missing key 'command' in batch command object")
        timeout = (
            default_timeout if "opc_timeout" not in entry else int(entry["opc_timeout"])
        )
        res = entry.get("resource") or None
        return BatchScpiCommand(command=str(entry["command"]), opc_timeout=timeout, resource=res)
    raise TypeError(
        "Each batch entry must be a string, BatchScpiCommand, or object "
        "{'command': '...', 'opc_timeout': ..., 'resource': '...'}",
    )


def _entry_resource(
    entry: str | BatchScpiCommand | dict[str, typing.Any],
    default_resource: str | None,
) -> str | None:
    """Return the resource for an entry without full parsing."""
    per_entry: str | None = None
    if isinstance(entry, BatchScpiCommand):
        per_entry = entry.resource
    elif isinstance(entry, dict):
        per_entry = entry.get("resource") or None
    return per_entry or default_resource or None


def _validate_resources(
    commands: list[str | BatchScpiCommand | dict[str, typing.Any]],
    default_resource: str | None,
) -> None:
    """Raise ValueError listing entry indices that have no resolved resource."""
    missing = [i for i, e in enumerate(commands) if not _entry_resource(e, default_resource)]
    if missing:
        raise ValueError(
            f"Entries at index {missing} have no resource: set a per-entry 'resource' "
            "or the top-level resource parameter"
        )



def _close_sessions(sessions: dict[str, typing.Any]) -> None:
    """Close all pooled instrument sessions, ignoring individual errors."""
    for inst in sessions.values():
        try:
            inst.close()
        except Exception:  # noqa: BLE001, S110
            pass


def _query_session(inst: typing.Any, command: str, timeout_ms: int) -> str:
    inst.opc_timeout = timeout_ms
    return inst.query(command).strip()


def _write_session(
    inst: typing.Any,
    command: str,
    timeout_ms: int,
    *,
    with_opc: bool,
) -> str:
    if with_opc:
        inst.write_with_opc(command, timeout=timeout_ms)
    else:
        inst.opc_timeout = timeout_ms
        inst.write(command)
    return {"status": "ok"}


def _drain_error_queue(
    resource: str, timeout_ms: int, session: typing.Any = None
) -> dict[str, typing.Any]:
    """Read and clear the error queue, reusing *session* when the batch holds one."""
    if session is not None:
        session.opc_timeout = timeout_ms
        errors = session.query_all_errors_with_codes() or []
    else:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = timeout_ms
            errors = inst.query_all_errors_with_codes() or []
    return {
        "errors": [{"code": code, "message": msg} for code, msg in errors],
        "drained": True,
    }


def _invalid_state_result(resource: str | None, detail: str) -> dict[str, typing.Any]:
    """Result for a batch that cannot resume safely; nothing in the batch runs."""
    return {
        "results": [
            {
                "command": "<request_state>",
                "resource": resource or "",
                "result": f"Error: {detail}; restart the batch",
            }
        ]
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
        ctx: Context,
        commands: list[str | BatchScpiCommand | dict[str, typing.Any]],
        resource: str | None = None,
        opc_timeout: int = 5000,
        continue_on_blocked: bool = False,
    ) -> typing.Any:
        """Batch SCPI with per-write gating, OPC sync, and dual-path elicitation."""
        _validate_resources(commands, resource)

        drain_resources: set[str] = set()
        if resource:
            drain_resources.add(resource)
        for entry in commands:
            r = _entry_resource(entry, resource)
            if r:  # pragma: no branch  (validated above — every entry has a resource)
                drain_resources.add(r)

        raw_state = getattr(ctx, "request_state", None)
        approvals = getattr(ctx, "input_responses", None)
        if isinstance(approvals, Mapping) and approvals and not isinstance(raw_state, str):
            # Approvals without the state they were issued for could replay entries
            # that already ran, so the batch stops instead of starting over.
            return _invalid_state_result(
                resource, "approvals were sent without a request_state"
            )
        try:
            outcomes, start_index = decode_batch_state(
                raw_state,
                total=len(commands),
                commands=commands,
            )
        except InvalidBatchStateError as exc:
            return _invalid_state_result(resource, str(exc))
        results: list[dict[str, typing.Any]] = []

        sessions: dict[str, typing.Any] = {}

        def _open(res: str) -> typing.Any:
            if res not in sessions:
                cm = RsInstrument(res)
                sessions[res] = cm.__enter__()
            return sessions[res]

        try:
            for i in range(min(start_index, len(commands))):
                entry = commands[i]
                entry_resource = _entry_resource(entry, resource) or resource or ""
                code = outcomes[i] if i < len(outcomes) else "error"

                try:
                    parsed = parse_batch_entry(entry, opc_timeout)
                    cmd = parsed.command
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        {
                            "command": str(entry),
                            "resource": entry_resource,
                            "result": f"Error: {exc}",
                        }
                    )
                    continue

                if code == "ok":
                    results.append(
                        {
                            "command": cmd,
                            "resource": entry_resource,
                            "result": {"status": "ok"},
                        }
                    )
                elif code == "query":
                    if iter_write_segments(cmd):
                        # Approved write-bearing query already ran; never run it again.
                        results.append(
                            {
                                "command": cmd,
                                "resource": entry_resource,
                                "result": {"status": "already_executed"},
                            }
                        )
                        continue
                    inst = _open(entry_resource)
                    try:
                        out = await asyncio.to_thread(
                            _query_session, inst, cmd, parsed.opc_timeout or opc_timeout
                        )
                        results.append({"command": cmd, "resource": entry_resource, "result": out})
                    except Exception as exc:  # noqa: BLE001
                        results.append(
                            {
                                "command": cmd,
                                "resource": entry_resource,
                                "result": f"Error: {exc}",
                            }
                        )
                elif code.startswith("error:"):
                    results.append(
                        {
                            "command": cmd,
                            "resource": entry_resource,
                            "result": f"Error: {code[6:]}",
                        }
                    )
                elif code in ("forbidden", "cancelled", "needs_confirmation"):
                    model = await _get_idn_model(
                        entry_resource, session=sessions.get(entry_resource)
                    )
                    gate = evaluate_write(cmd, model=model, policy=policy)
                    results.append(
                        {
                            "command": cmd,
                            "resource": entry_resource,
                            "result": _gate_dict(code, gate),
                        }
                    )
                else:
                    results.append(
                        {
                            "command": cmd,
                            "resource": entry_resource,
                            "result": f"Error: {code}",
                        }
                    )

            blocked = False
            for index in range(start_index, len(commands)):
                entry = commands[index]
                entry_resource = _entry_resource(entry, resource) or resource or ""
                cmd = ""

                if blocked:
                    try:
                        blocked_cmd = parse_batch_entry(entry, opc_timeout).command
                    except Exception:  # noqa: BLE001
                        blocked_cmd = str(entry)
                    results.append(
                        {
                            "command": blocked_cmd,
                            "resource": entry_resource,
                            "status": "not_executed",
                            "reason": "previous entry blocked",
                        }
                    )
                    continue

                try:
                    parsed = parse_batch_entry(entry, opc_timeout)
                    cmd = parsed.command

                    if is_scpi_query(cmd):
                        writes = iter_write_segments(cmd)
                        if writes:
                            decision = await _authorize_write(
                                ctx,
                                command=cmd,
                                resource=entry_resource,
                                session=sessions.get(entry_resource),
                                response_key=batch_confirm_key(index),
                                request_state=encode_batch_state(
                                    outcomes, index, commands_prefix_digest(commands, index)
                                ),
                                policy=policy,
                            )
                            if decision is not None and not isinstance(decision, dict):
                                return decision
                            if isinstance(decision, dict):
                                results.append(
                                    {
                                        "command": cmd,
                                        "resource": entry_resource,
                                        "result": decision,
                                    }
                                )
                                outcomes.append(decision.get("gate", "error"))
                                if not continue_on_blocked:
                                    blocked = True
                                continue

                        inst = _open(entry_resource)
                        out = await asyncio.to_thread(
                            _query_session, inst, cmd, parsed.opc_timeout or opc_timeout
                        )
                        results.append(
                            {"command": cmd, "resource": entry_resource, "result": out}
                        )
                        outcomes.append("query")
                        continue

                    decision = await _authorize_write(
                        ctx,
                        command=cmd,
                        resource=entry_resource,
                        session=sessions.get(entry_resource),
                        response_key=batch_confirm_key(index),
                        request_state=encode_batch_state(
                                    outcomes, index, commands_prefix_digest(commands, index)
                                ),
                        policy=policy,
                    )
                    if decision is not None and not isinstance(decision, dict):
                        return decision
                    if isinstance(decision, dict):
                        results.append(
                            {"command": cmd, "resource": entry_resource, "result": decision}
                        )
                        outcomes.append(decision.get("gate", "error"))
                        if not continue_on_blocked:
                            blocked = True
                        continue

                    with_opc = sync_policy.needs_opc(cmd)
                    inst = _open(entry_resource)
                    out = await asyncio.to_thread(
                        _write_session,
                        inst,
                        cmd,
                        parsed.opc_timeout or opc_timeout,
                        with_opc=with_opc,
                    )
                    results.append({"command": cmd, "resource": entry_resource, "result": out})
                    outcomes.append("ok")
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        {
                            "command": cmd or str(entry),
                            "resource": entry_resource,
                            "result": f"Error: {exc}",
                        }
                    )
                    outcomes.append(f"error:{exc}")

            if sync_policy.collect_errors:
                for res in drain_resources:
                    try:
                        drained = await asyncio.to_thread(
                            _drain_error_queue, res, opc_timeout, sessions.get(res)
                        )
                        results.append(
                            {"command": "<error-queue>", "resource": res, "result": drained}
                        )
                    except Exception as exc:  # noqa: BLE001
                        results.append(
                            {
                                "command": "<error-queue>",
                                "resource": res,
                                "result": f"Error: {exc}",
                            }
                        )

        finally:
            _close_sessions(sessions)

        return {"results": results}

    return instrument_batch_scpi
