"""MCP write authorization: IDN cache, gate JSON, dual-path elicitation."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
from collections.abc import Sequence
from typing import Any

from RsInstrument.Internal.Discovery import parse_idn
from RsInstrument.mcp.scpi_write_policy import (
    ScpiWritePolicy,
    WriteGateResult,
    evaluate_write,
    iter_write_segments,
)

try:
    from fastmcp import Context
except ImportError:
    Context = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

WRITE_CONFIRM_KEY = "write_confirm"

_idn_cache: dict[str, tuple[str, float]] = {}
_IDN_CACHE_TTL_S = 30.0
# An unknown model triggers conservative evaluation (all model-scoped rules apply),
# so it is cached only briefly: once identity is resolved the policy may relax
# restrictions, and we must not stay over-gated for the full 30 s.
_IDN_UNKNOWN_CACHE_TTL_S = 2.0
_idn_cache_lock = threading.Lock()


def _resource_key(resource: str) -> str:
    """Canonical cache key for a VISA resource string."""
    return resource.strip().casefold()


_PROTOCOL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INPUT_REQUIRED_MIN_PROTOCOL = "2026-07-28"

try:
    from mcp import types as _mcp_types

    ElicitRequest = getattr(_mcp_types, "ElicitRequest", None)
    ElicitRequestFormParams = getattr(_mcp_types, "ElicitRequestFormParams", None)
    InputRequiredResult = getattr(_mcp_types, "InputRequiredResult", None)
    _HAS_INPUT_REQUIRED = all(
        item is not None
        for item in (ElicitRequest, ElicitRequestFormParams, InputRequiredResult)
    )
except ImportError:
    _HAS_INPUT_REQUIRED = False
    InputRequiredResult = None
    ElicitRequest = None
    ElicitRequestFormParams = None


def clear_idn_cache() -> None:
    """Clear the process-local IDN model cache (for tests)."""
    with _idn_cache_lock:
        _idn_cache.clear()


def _gate_dict(status: str, gate: WriteGateResult) -> dict[str, Any]:
    """Build a terminal gate result dict from a WriteGateResult."""
    payload: dict[str, Any] = {
        "gate": status,
        "rule_id": gate.rule_id,
        "command": gate.command,
        "model": gate.model,
        "reason": (
            gate.reason
            if status != "cancelled"
            else "User declined or cancelled the confirmation prompt."
        ),
    }
    if status == "needs_confirmation":
        payload["hint"] = (
            "This write needs user approval through MCP elicitation, "
            "which the client did not provide. The write was not executed."
        )
    return payload


def _gate_json(status: str, gate: WriteGateResult) -> str:
    """Build a terminal gate JSON string from a WriteGateResult.

    Kept for backwards compatibility with external code that calls this directly.
    Internal tool implementations now use :func:`_gate_dict`.
    """
    return json.dumps(_gate_dict(status, gate))


def _query_idn(resource: str, session: Any = None) -> str:
    """Query *IDN? and return the raw string.

    With *session* (an instrument session the caller already has open), the query
    reuses it. Otherwise a short session is opened. Opening a second session while
    one is open can fail on instruments that allow only one, so callers pass their
    open session when they have one.
    """
    if session is not None:
        return session.query("*IDN?").strip()
    from RsInstrument import RsInstrument

    with RsInstrument(resource) as inst:
        return inst.query("*IDN?").strip()


def _idn_cache_ttl(model: str) -> float:
    """TTL for a cached model: short while the model is unknown."""
    return _IDN_CACHE_TTL_S if model else _IDN_UNKNOWN_CACHE_TTL_S


async def _get_idn_model(
    resource: str, *, refresh: bool = False, session: Any = None
) -> str:
    """Return model string for resource using a TTL cache.

    ``refresh=True`` bypasses the cached entry; the post-approval re-check uses
    it so the policy is evaluated against the instrument as it is now.
    """
    key = _resource_key(resource)
    with _idn_cache_lock:
        entry = _idn_cache.get(key)
        if not refresh and entry is not None:
            model, stored_at = entry
            if (time.monotonic() - stored_at) <= _idn_cache_ttl(model):
                return model

    try:
        idn_raw = await asyncio.to_thread(_query_idn, resource, session)
        model = parse_idn(idn_raw).get("model", "")
    except Exception:
        logger.warning(
            "IDN query failed for %s; model-scoped write rules cannot be applied",
            resource,
            exc_info=True,
        )
        model = ""

    now = time.monotonic()
    with _idn_cache_lock:
        _idn_cache[key] = (model, now)
        _prune_idn_cache(now)
    return model


def _prune_idn_cache(now: float) -> None:
    """Drop expired entries. Caller must hold ``_idn_cache_lock``."""
    expired = [
        key
        for key, (model, stored_at) in _idn_cache.items()
        if (now - stored_at) > _idn_cache_ttl(model)
    ]
    for key in expired:
        del _idn_cache[key]


def _is_modern_protocol(ctx: Any) -> bool:
    """Return True when the negotiated protocol supports InputRequiredResult."""
    if not _HAS_INPUT_REQUIRED:
        return False
    try:
        version = getattr(ctx.request_context, "protocol_version", None)
    except Exception:
        return False
    if version is None:
        return False
    text = str(version)
    if not _PROTOCOL_DATE.match(text):
        return False
    return text >= _INPUT_REQUIRED_MIN_PROTOCOL


def _ask_write_confirm(
    message: str,
    request_state: str | None = None,
    *,
    response_key: str = WRITE_CONFIRM_KEY,
) -> Any:
    """Build an InputRequiredResult that elicits a boolean approval."""
    if not _HAS_INPUT_REQUIRED:
        raise RuntimeError("InputRequiredResult is not available in this mcp package")
    assert ElicitRequestFormParams is not None
    assert InputRequiredResult is not None
    assert ElicitRequest is not None
    params = ElicitRequestFormParams(
        message=message,
        requestedSchema={
            "type": "object",
            "properties": {
                "approved": {
                    "type": "boolean",
                    "title": "Approve write",
                    "description": "True to execute the SCPI write",
                }
            },
            "required": ["approved"],
        },
    )
    return InputRequiredResult(
        result_type="input_required",
        input_requests={
            response_key: ElicitRequest(method="elicitation/create", params=params)
        },
        request_state=request_state,
    )


def _read_approval(answer: Any) -> bool | None:
    """Return True only when explicitly approved; None if decline/cancel."""
    action = getattr(answer, "action", None)
    if action != "accept":
        return None
    content = getattr(answer, "content", None)
    if isinstance(content, dict):
        approved = content.get("approved", content.get("value"))
        return approved is True
    return content is True


_APPROVE_MAX_STMTS = 25
_APPROVE_MAX_STMT_CHARS = 500
_APPROVE_TOO_LARGE_REASON = (
    "Too many or too long statements to review safely in one approval; split the request."
)


def _build_elicit_message(gate: WriteGateResult, resource: str, command: str) -> str:
    """Build the approval text: the exact command, its resolved statements, and the reason.

    The command is what the instrument receives, so it is shown verbatim. Resource,
    command, reason and each statement are JSON-encoded so that control characters
    and Unicode line separators cannot inject extra lines.
    """
    stmts = iter_write_segments(command)
    lines = "\n".join(f"- {json.dumps(s, ensure_ascii=True)}" for s in stmts)
    return (
        f"Reason: {json.dumps(gate.reason, ensure_ascii=True)}\n"
        f"Resource: {json.dumps(resource, ensure_ascii=True)}\n"
        f"Command: {json.dumps(command, ensure_ascii=True)}\n"
        f"Statements:\n{lines}"
    )


_APPROVAL_TTL_S = 300.0
_BATCH_STATE_TTL_S = 600.0

_pending_approvals: dict[str, tuple[str, float]] = {}
"""Approvals this process issued and has not consumed: nonce -> (prefix, expires_at)."""
_pending_lock = threading.Lock()


def _now() -> float:
    """Monotonic clock for approval and batch-state expiry; tests patch this."""
    return time.monotonic()


def approval_key_prefix(base_key: str, resource: str, command: str) -> str:
    """Deterministic part of an approval key, bound to the resource and exact command text.

    The exact text is what the prompt shows and what the instrument receives. A
    normalized digest would let an approval for one spelling (for example
    ``'a  b.txt'``) also cover a different quoted value that normalizes the same.
    The prefix alone never approves anything; :func:`_issue_approval_key` adds a nonce.
    """
    payload = json.dumps([resource.strip().casefold(), command.strip()])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{base_key}:{digest}"


def _issue_approval_key(base_key: str, resource: str, command: str) -> str:
    """Mint a single-use approval key for a prompt this process is about to show.

    The nonce is created here, so a client cannot answer a prompt before it is
    issued, and an approval for one prompt cannot be pre-computed for a later entry.
    """
    prefix = approval_key_prefix(base_key, resource, command)
    nonce = secrets.token_urlsafe(16)
    now = _now()
    with _pending_lock:
        _prune_pending_approvals(now)
        _pending_approvals[nonce] = (prefix, now + _APPROVAL_TTL_S)
    return f"{prefix}:{nonce}"


def _prune_pending_approvals(now: float) -> None:
    """Drop expired approvals. Caller must hold ``_pending_lock``."""
    expired = [nonce for nonce, (_, expires_at) in _pending_approvals.items() if now > expires_at]
    for nonce in expired:
        del _pending_approvals[nonce]


def _claim_approval(responses: Any, prefix: str) -> str | None:
    """Return the response key that answers a live approval for *prefix*, consuming it.

    A key that was never issued, has expired, was already used, or belongs to
    another prefix is ignored. The caller then asks again with a fresh key.
    """
    for key in responses:
        if not isinstance(key, str) or not key.startswith(f"{prefix}:"):
            continue
        nonce = key[len(prefix) + 1 :]
        with _pending_lock:
            entry = _pending_approvals.pop(nonce, None)
        if entry is not None and entry[0] == prefix and _now() <= entry[1]:
            return key
    return None


def clear_pending_approvals() -> None:
    """Forget every issued approval (for tests)."""
    with _pending_lock:
        _pending_approvals.clear()


async def _recheck_after_approval(
    *,
    command: str,
    resource: str,
    policy: ScpiWritePolicy | None,
    approved_rule_id: str,
    session: Any = None,
) -> None | dict[str, Any]:
    """Re-evaluate the approved write against the instrument's current identity.

    The model is queried again without the cache, because the approval may be
    given long after the first query. The write proceeds if it is now allowed, or
    if it still needs confirmation under the same rule the user approved. Any
    other result fails closed, so a changed instrument cannot inherit an approval
    it was not shown.
    """
    model = await _get_idn_model(resource, refresh=True, session=session)
    re_gate = evaluate_write(command, model=model, resource=resource, policy=policy)
    if re_gate.outcome == "allowed":
        return None
    if re_gate.outcome == "needs_confirmation" and re_gate.rule_id == approved_rule_id:
        return None
    return _gate_dict(re_gate.outcome, re_gate)


async def _authorize_write(
    ctx: Context | None,
    *,
    command: str,
    resource: str,
    response_key: str = WRITE_CONFIRM_KEY,
    request_state: str | None = None,
    policy: ScpiWritePolicy | None = None,
    session: Any = None,
) -> None | dict[str, Any] | Any:
    """None = proceed; dict = terminal gate result; InputRequiredResult = modern ask.

    *session* is an instrument session the caller already holds for *resource*; the
    identity lookups reuse it instead of opening a second session.
    """
    model = await _get_idn_model(resource, session=session)
    gate = evaluate_write(command, model=model, resource=resource, policy=policy)

    if gate.outcome == "allowed":
        return None
    if gate.outcome == "forbidden":
        return _gate_dict("forbidden", gate)

    # needs_confirmation — guard against oversized approval payloads.
    stmts = iter_write_segments(command)
    if len(stmts) > _APPROVE_MAX_STMTS or any(
        len(s) > _APPROVE_MAX_STMT_CHARS for s in stmts
    ):
        too_large = WriteGateResult(
            outcome="forbidden",
            reason=_APPROVE_TOO_LARGE_REASON,
            rule_id="approval_request_too_large",
            command=command,
            model=model,
        )
        return _gate_dict("forbidden", too_large)

    message = _build_elicit_message(gate, resource, command)

    # needs_confirmation — modern InputRequiredResult path
    if _is_modern_protocol(ctx):
        # An answer counts only when it carries a nonce this process issued for
        # this exact resource and command, and it is consumed on first use.
        responses = getattr(ctx, "input_responses", None) or {}
        answered = _claim_approval(
            responses, approval_key_prefix(response_key, resource, command)
        )
        if answered is not None:
            if _read_approval(responses[answered]) is True:
                return await _recheck_after_approval(
                    command=command,
                    resource=resource,
                    policy=policy,
                    approved_rule_id=gate.rule_id,
                    session=session,
                )
            return _gate_dict("cancelled", gate)
        return _ask_write_confirm(
            message,
            request_state=request_state,
            response_key=_issue_approval_key(response_key, resource, command),
        )

    # Legacy elicitation path — fail closed if ctx is absent or elicit unavailable
    if ctx is None:
        return _gate_dict("needs_confirmation", gate)

    try:
        result = await ctx.elicit(
            message=message,
            response_type=bool,
            response_title="Confirm instrument write",
            response_description=gate.reason,
        )
    except Exception:
        logger.debug("Elicitation unsupported; returning needs-confirmation gate", exc_info=True)
        return _gate_dict("needs_confirmation", gate)

    action = getattr(result, "action", None)
    data = getattr(result, "data", None)
    if action == "accept" and data is True:
        return await _recheck_after_approval(
            command=command,
            resource=resource,
            policy=policy,
            approved_rule_id=gate.rule_id,
            session=session,
        )
    return _gate_dict("cancelled", gate)


_KNOWN_OUTCOME_CODES: frozenset[str] = frozenset(
    {"ok", "query", "forbidden", "cancelled", "needs_confirmation"}
)


def batch_confirm_key(index: int) -> str:
    """Response key for batch entry confirmation."""
    return f"batch_confirm_{index}"


_STATE_KEY: bytes = secrets.token_bytes(32)
"""Per-process key that authenticates batch continuation state.

The key is process-local on purpose: state issued before a server restart is
rejected, and the client restarts the batch, so gated writes are asked again.
"""


class InvalidBatchStateError(ValueError):
    """``request_state`` is unsigned, tampered with, or does not match the batch."""


def commands_prefix_digest(commands: Sequence[object], count: int) -> str:
    """Digest of the first *count* batch entries, bound into the continuation state."""
    text = json.dumps([str(entry) for entry in commands[:count]])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _state_mac(payload: str) -> str:
    return hmac.new(_STATE_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def encode_batch_state(outcomes: list[str], next_index: int, prefix_digest: str) -> str:
    """Return continuation state as ``<json>.<hmac>``, signed with the process key.

    The HMAC stops a client from editing ``outcomes`` or ``next`` to skip gates
    or to re-run writes. The prefix digest stops it from swapping commands
    between requests. The issue time ``iat`` lets :func:`decode_batch_state`
    expire the state after ``_BATCH_STATE_TTL_S``.
    """
    payload = json.dumps(
        {
            "outcomes": outcomes,
            "next": next_index,
            "prefix": prefix_digest,
            "iat": _now(),
        },
        separators=(",", ":"),
    )
    return f"{payload}.{_state_mac(payload)}"


def decode_batch_state(
    raw: str | None,
    *,
    total: int | None = None,
    commands: Sequence[object] | None = None,
) -> tuple[list[str], int]:
    """Verify and parse continuation state. Returns outcomes and the next index.

    No state means a fresh batch. Any other state must carry a valid signature,
    and when *commands* is given it must describe exactly those commands; otherwise
    :class:`InvalidBatchStateError` is raised and the caller must fail closed.

    Outcome codes not in the known set (or the ``error:`` prefix) are dropped.
    ``next`` is clamped to ``[0, total]`` when *total* is given, and always to
    ``>= 0``.
    """
    if not raw or not isinstance(raw, str):
        # A non-string value is not a state this server issued. Starting fresh
        # re-applies every gate, so it is the safe default.
        return [], 0
    payload, separator, mac = raw.rpartition(".")
    if not separator or not hmac.compare_digest(mac, _state_mac(payload)):
        raise InvalidBatchStateError("request_state signature is invalid")
    try:
        data = json.loads(payload)
        raw_outcomes: list[Any] = list(data.get("outcomes", []))
        prefix = str(data.get("prefix", ""))
        issued_at = float(data["iat"])
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise InvalidBatchStateError("request_state payload is malformed") from exc
    if _now() - issued_at > _BATCH_STATE_TTL_S:
        raise InvalidBatchStateError("request_state has expired")
    try:
        next_index = int(data.get("next", 0))
    except (TypeError, ValueError):
        next_index = 0
    outcomes = [
        o
        for o in raw_outcomes
        if isinstance(o, str) and (o in _KNOWN_OUTCOME_CODES or o.startswith("error:"))
    ]
    next_index = max(next_index, 0)
    if total is not None:
        next_index = min(next_index, total)
    if commands is not None and prefix != commands_prefix_digest(commands, next_index):
        raise InvalidBatchStateError("request_state does not match the batch commands")
    return outcomes, next_index
