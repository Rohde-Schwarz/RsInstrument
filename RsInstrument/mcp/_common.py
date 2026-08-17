"""Shared MCP tool decorator and annotation hints."""

from __future__ import annotations

import functools
import inspect
import logging
import typing

logger = logging.getLogger(__name__)

# MCP ToolAnnotations hints (openWorldHint=True: all tools reach VISA instruments).
ANN_READONLY: dict[str, typing.Any] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}
ANN_WRITE: dict[str, typing.Any] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True,
}
ANN_DESTRUCTIVE_IDEMPOTENT: dict[str, typing.Any] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": True,
}
ANN_STATE_CHANGE: dict[str, typing.Any] = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def safe_tool(fn: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    """Decorate MCP tools by converting exceptions to ``Error: ...`` strings.

    Works for sync and async callables: the wrapper is always async and awaits
    the result when it is awaitable. Call with ``await`` / ``asyncio.run`` from
    plain Python; FastMCP awaits registered tools automatically.
    """

    @functools.wraps(fn)
    async def _wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        try:
            result = fn(*args, **kwargs)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Exception in tool %s", getattr(fn, "__name__", repr(fn)))
            return f"Error: {exc}"

    return _wrapper
