"""Structured result types and JSON output schemas for RsInstrument MCP tools.

Tools return Python dicts (subclasses of TypedDict for IDE support).  FastMCP
serialises them as ``structuredContent`` and also emits a JSON text mirror in
``content`` for older clients.
"""

from __future__ import annotations

import sys
from typing import Any, TypedDict

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:  # pragma: no cover - exercised only on Python 3.10
    from typing_extensions import NotRequired

# ---------------------------------------------------------------------------
# TypedDicts — used for type-checking and documentation; not enforced at
# runtime (dicts returned by tools are plain dicts, not instances).
# ---------------------------------------------------------------------------


class GateResult(TypedDict):
    """Terminal write-gate result (forbidden / cancelled / needs_confirmation)."""

    gate: str
    rule_id: str
    command: str
    model: str
    reason: str
    hint: NotRequired[str]


class ErrorResult(TypedDict):
    """Structured error returned by safe_tool when a tool raises an exception."""

    status: str  # always "error"
    error: str


class QueryResult(TypedDict):
    """Successful SCPI query response."""

    value: str


class WriteResult(TypedDict):
    """Successful SCPI write."""

    status: str  # always "ok"


class FetchErrorsResult(TypedDict):
    """Instrument error-queue drain result."""

    errors: list[dict[str, Any]]


class GoToLocalResult(TypedDict):
    """Go-to-local result."""

    status: str
    message: str


class UserInteractionResult(TypedDict):
    """Enable-user-interaction result."""

    status: str
    message: str


class ScreenshotResult(TypedDict):
    """Screenshot capture result."""

    mime_type: str
    data: str  # base64-encoded PNG
    warning: NotRequired[str]


class SaveRecallResult(TypedDict):
    """Save/recall slot operation result."""

    status: str
    action: str
    slot: int
    message: str


class BatchResult(TypedDict):
    """Batch SCPI execution result."""

    results: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# JSON output schemas — passed to FastMCP tool() as ``output_schema``.
# All top-level schemas carry ``"type": "object"`` (required by MCP spec /
# FastMCP).  When a tool can return more than one object shape (success,
# write-gate, or structured error), the root schema also uses ``oneOf`` to
# list the discriminated alternatives.
# ---------------------------------------------------------------------------

# Subschema fragments (no top-level ``type`` — used inside ``oneOf`` only)
_GATE_PROPS: dict[str, Any] = {
    "description": (
        "Write-gate dict emitted when a command is forbidden, cancelled, "
        "or needs confirmation. Keys: gate, rule_id, command, model, reason "
        "(and hint for needs_confirmation)."
    ),
    "properties": {
        "gate": {"type": "string"},
        "rule_id": {"type": "string"},
        "command": {"type": "string"},
        "model": {"type": "string"},
        "reason": {"type": "string"},
        "hint": {"type": "string"},
    },
    "required": ["gate", "rule_id", "command", "model", "reason"],
}

_ERROR_PROPS: dict[str, Any] = {
    "description": "Structured error dict returned by safe_tool when an exception is raised.",
    "properties": {
        "status": {"type": "string", "const": "error"},
        "error": {"type": "string"},
    },
    "required": ["status", "error"],
}

# Standalone schema used where a single gate dict is the primary reference:
_GATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": _GATE_PROPS["description"],
    "properties": _GATE_PROPS["properties"],
    "required": _GATE_PROPS["required"],
}

QUERY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "SCPI query result. One of: successful query {value}, "
        "write-gate dict {gate, rule_id, command, model, reason, ?hint}, "
        "or structured error dict {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "description": "Successful query response.",
        },
        _GATE_PROPS,
        _ERROR_PROPS,
    ],
}

WRITE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "SCPI write result. One of: success {status='ok'}, "
        "write-gate dict, or structured error dict {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {"status": {"type": "string", "const": "ok"}},
            "required": ["status"],
            "description": "Successful SCPI write or reset.",
        },
        _GATE_PROPS,
        _ERROR_PROPS,
    ],
}

FETCH_ERRORS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Instrument error-queue drain result or structured error. "
        "Success: {errors: [{code, message}, ...]}. "
        "Error: {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {
                "errors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "integer"},
                            "message": {"type": "string"},
                        },
                        "required": ["code", "message"],
                    },
                },
            },
            "required": ["errors"],
            "description": "Successful error-queue drain.",
        },
        _ERROR_PROPS,
    ],
}

GO_TO_LOCAL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Go-to-local result. "
        "Success: {status='ok', message}. Error: {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {
                "status": {"type": "string", "const": "ok"},
                "message": {"type": "string"},
            },
            "required": ["status", "message"],
            "description": "Go-to-local success.",
        },
        _ERROR_PROPS,
    ],
}

SCREENSHOT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "PNG screenshot capture result or structured error. "
        "Success: {mime_type='image/png', data, ?warning}. "
        "Error: {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {
                "mime_type": {"type": "string", "const": "image/png"},
                "data": {"type": "string", "description": "Base64-encoded PNG bytes."},
                "warning": {"type": "string"},
            },
            "required": ["mime_type", "data"],
            "description": "Successful screenshot capture.",
        },
        _ERROR_PROPS,
    ],
}

USER_INTERACTION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "User-interaction enable result or structured error. "
        "Success: {status='ok', message}. Error: {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {
                "status": {"type": "string", "const": "ok"},
                "message": {"type": "string"},
            },
            "required": ["status", "message"],
            "description": "Successful user-interaction enable.",
        },
        _ERROR_PROPS,
    ],
}

BATCH_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Batch SCPI execution result or structured error. "
        "Success: {results: [per-entry outcome, ...]}. "
        "Each result item has 'command' and 'resource'; 'result' is a query-response "
        "string, write-success dict, gate dict, or error string. "
        "not_executed items carry 'status' and 'reason' instead of 'result'."
    ),
    "oneOf": [
        {
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "resource": {"type": "string"},
                            "result": {
                                "description": (
                                    "Query string, write-success dict, gate dict, or error string."
                                ),
                            },
                            "status": {
                                "type": "string",
                                "description": "Present on not_executed entries.",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Present on not_executed entries.",
                            },
                        },
                        "required": ["command", "resource"],
                    },
                },
            },
            "required": ["results"],
            "description": "Successful batch execution.",
        },
        _ERROR_PROPS,
    ],
}

SAVE_RECALL_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Save/recall result. One of: success {status='ok', action, slot, message}, "
        "write-gate dict, or structured error dict {status='error', error}."
    ),
    "oneOf": [
        {
            "properties": {
                "status": {"type": "string", "const": "ok"},
                "action": {"type": "string"},
                "slot": {"type": "integer"},
                "message": {"type": "string"},
            },
            "required": ["status", "action", "slot", "message"],
            "description": "Successful save/recall.",
        },
        _GATE_PROPS,
        _ERROR_PROPS,
    ],
}

SCPI_EXISTS_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "SCPI command existence check result or structured error. "
        "Success: {exists, matched_header, matches, match_type, truncated, supported}."
    ),
    "oneOf": [
        {
            "properties": {
                "exists": {"type": "boolean"},
                "matched_header": {"oneOf": [{"type": "string"}, {"type": "null"}]},
                "matches": {"type": "array", "items": {"type": "string"}},
                "match_type": {"type": "string"},
                "truncated": {"type": "boolean"},
                "supported": {"type": "boolean"},
            },
            "required": ["exists", "matched_header", "matches", "match_type", "truncated", "supported"],
            "description": "Existence check result.",
        },
        _ERROR_PROPS,
    ],
}

DISCOVERY_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "VISA instrument discovery snapshot or structured error. "
        "Success: {source, timestamp, expression, count, instruments, ...}."
    ),
    "oneOf": [
        {
            "properties": {
                "source": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "expression": {"type": "string"},
                "visa_select": {},
                "method_notes": {},
                "count": {"type": "integer"},
                "instruments": {"type": "array"},
            },
            "required": ["source", "timestamp", "expression", "count", "instruments"],
            "description": "Discovery snapshot.",
        },
        _ERROR_PROPS,
    ],
}

FILE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "MMEM file operation result (shape depends on action). "
        "May return a write-gate dict (keys: gate, rule_id, command, model, reason) "
        "or a structured error dict (keys: status='error', error) "
        "instead of the normal success shape."
    ),
    "additionalProperties": True,
}
