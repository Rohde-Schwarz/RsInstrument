"""MCP write authorization: IDN cache, gate JSON, dual-path elicitation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from typing import Any

from RsInstrument.Internal.Discovery import parse_idn
from RsInstrument.mcp.scpi_write_policy import (
    ScpiWritePolicy,
    WriteGateResult,
    evaluate_write,
)

logger = logging.getLogger(__name__)

WRITE_CONFIRM_KEY = "write_confirm"

_idn_cache: dict[str, tuple[str, float]] = {}
_IDN_CACHE_TTL_S = 30.0
# An unknown model disables every model-scoped policy rule, so it is cached only
# briefly: a transient *IDN? failure must not leave writes under-gated for 30 s.
_IDN_UNKNOWN_CACHE_TTL_S = 2.0
_idn_cache_lock = threading.Lock()

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


def _gate_json(status: str, gate: WriteGateResult) -> str:
    """Build a terminal gate JSON string from a WriteGateResult."""
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
        payload["confirm_hint"] = "Re-call this tool with confirm=true to approve."
    return json.dumps(payload)


def _query_idn(resource: str) -> str:
    """Open a short session, query *IDN?, return raw string."""
    from RsInstrument import RsInstrument

    with RsInstrument(resource) as inst:
        return inst.query("*IDN?").strip()


def _idn_cache_ttl(model: str) -> float:
    """TTL for a cached model: short while the model is unknown."""
    return _IDN_CACHE_TTL_S if model else _IDN_UNKNOWN_CACHE_TTL_S


async def _get_idn_model(resource: str) -> str:
    """Return model string for resource using a TTL cache."""
    with _idn_cache_lock:
        entry = _idn_cache.get(resource)
        if entry is not None:
            model, stored_at = entry
            if (time.monotonic() - stored_at) <= _idn_cache_ttl(model):
                return model

    try:
        idn_raw = await asyncio.to_thread(_query_idn, resource)
        model = parse_idn(idn_raw).get("model", "")
    except Exception:
        logger.warning(
            "IDN query failed for %s; model-scoped write rules cannot be applied",
            resource,
            exc_info=True,
        )
        model = ""

    with _idn_cache_lock:
        _idn_cache[resource] = (model, time.monotonic())
    return model


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
    """Return True/False from an elicit answer, or None if decline/cancel."""
    action = getattr(answer, "action", None)
    if action != "accept":
        return None
    content = getattr(answer, "content", None)
    if isinstance(content, dict):
        return bool(content.get("approved", content.get("value", False)))
    return bool(content)


async def _authorize_write(
    ctx: Any,
    *,
    command: str,
    resource: str,
    confirm: bool = False,
    response_key: str = WRITE_CONFIRM_KEY,
    request_state: str | None = None,
    policy: ScpiWritePolicy | None = None,
) -> None | str | Any:
    """None = proceed; str = terminal gate JSON; InputRequiredResult = modern ask."""
    model = await _get_idn_model(resource)
    gate = evaluate_write(command, model=model, policy=policy)

    if gate.outcome == "allowed":
        return None
    if gate.outcome == "forbidden":
        return _gate_json("forbidden", gate)

    if confirm:
        re_gate = evaluate_write(command, model=model, policy=policy)
        if re_gate.outcome == "forbidden":
            return _gate_json("forbidden", re_gate)
        return None

    responses = getattr(ctx, "input_responses", None)
    if _is_modern_protocol(ctx):
        if responses and response_key in responses:
            approved = _read_approval(responses[response_key])
            if approved is True:
                re_gate = evaluate_write(command, model=model, policy=policy)
                if re_gate.outcome == "forbidden":
                    return _gate_json("forbidden", re_gate)
                return None
            return _gate_json("cancelled", gate)
        return _ask_write_confirm(
            gate.reason, request_state=request_state, response_key=response_key
        )

    try:
        result = await ctx.elicit(
            message=gate.reason,
            response_type=bool,
            response_title="Confirm instrument write",
            response_description=gate.reason,
        )
    except Exception:
        logger.debug("Elicitation unsupported; returning confirm hint", exc_info=True)
        return _gate_json("needs_confirmation", gate)

    action = getattr(result, "action", None)
    data = getattr(result, "data", None)
    if action == "accept" and data:
        return None
    return _gate_json("cancelled", gate)


def batch_confirm_key(index: int) -> str:
    """Response key for batch entry confirmation."""
    return f"batch_confirm_{index}"


def encode_batch_state(outcomes: list[str], next_index: int) -> str:
    """Compact JSON for sealed request_state."""
    return json.dumps({"outcomes": outcomes, "next": next_index}, separators=(",", ":"))


def decode_batch_state(raw: str | None) -> tuple[list[str], int]:
    """Parse sealed request_state into outcomes + next index."""
    if not raw:
        return [], 0
    try:
        data = json.loads(raw)
        outcomes = list(data.get("outcomes", []))
        next_index = int(data.get("next", 0))
        return outcomes, next_index
    except (TypeError, ValueError, json.JSONDecodeError):
        return [], 0
