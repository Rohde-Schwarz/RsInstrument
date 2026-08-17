"""FastMCP server creation and run entry points."""

from __future__ import annotations

import logging
import typing

if typing.TYPE_CHECKING:
    from fastmcp import FastMCP
    from starlette.responses import JSONResponse

    MCP_INSTALLED: bool
else:
    try:
        from fastmcp import FastMCP
        from starlette.responses import JSONResponse

        MCP_INSTALLED = True
    except ImportError:
        MCP_INSTALLED = False
        FastMCP = None
        JSONResponse = None

from RsInstrument import __version__
from RsInstrument.mcp.tool_specs import (
    BuiltinToolSettings,
    ToolInput,
    create_builtin_tool_specs,
    merge_tool_specs,
    register_one_tool,
)
from RsInstrument.otel import setup_otel

logger = logging.getLogger(__name__)

DEFAULT_MCP_HEALTH_ENDPOINT = "/healthz"


def create_fastmcp_server(
    *args: typing.Any,
    tools: typing.Sequence[ToolInput] | None = None,
    include_builtin_tools: bool = True,
    builtin_settings: BuiltinToolSettings | None = None,
    health_endpoint: str = DEFAULT_MCP_HEALTH_ENDPOINT,
    **kwargs: typing.Any,
):
    """Create a FastMCP server for SCPI commands."""
    if not MCP_INSTALLED:
        raise ImportError(
            "mcp is required for this module. Please install with 'pip install RsInstrument[mcp]'",
        )
    if FastMCP is None or JSONResponse is None:
        raise RuntimeError(
            "MCP dependencies are not initialized correctly. "
            "Please reinstall RsInstrument with the 'mcp' extra.",
        )
    _json_response = JSONResponse
    name = f"{__package__}-mcp"
    kwargs.setdefault("name", name)
    # noinspection PyCallingNonCallable
    fastmcp = FastMCP(*args, **kwargs)

    @fastmcp.custom_route(health_endpoint, methods=["GET"])
    async def health_check(_: typing.Any) -> typing.Any:
        """Health check endpoint."""
        # noinspection PyCallingNonCallable
        return _json_response(
            {"status": "healthy", "service": name, "version": __version__},
        )

    settings = builtin_settings or BuiltinToolSettings.create()
    specs = merge_tool_specs(
        create_builtin_tool_specs(settings) if include_builtin_tools else None,
        tools,
    )
    for spec in specs:
        register_one_tool(fastmcp, spec)
    return fastmcp


def run(
    *args: typing.Any,
    host: str = "localhost",
    port: int = 8000,
    transport: typing.Literal["stdio", "sse", "streamable-http"] = "stdio",
    tools: typing.Sequence[ToolInput] | None = None,
    include_builtin_tools: bool = True,
    builtin_settings: BuiltinToolSettings | None = None,
    health_endpoint: str = DEFAULT_MCP_HEALTH_ENDPOINT,
    show_fastmcp_banner: bool = False,
    **kwargs: typing.Any,
):
    """Run the MCP server."""
    setup_otel()
    mcp = create_fastmcp_server(
        *args,
        tools=tools,
        include_builtin_tools=include_builtin_tools,
        builtin_settings=builtin_settings,
        health_endpoint=health_endpoint,
        **kwargs,
    )
    if transport != "stdio":
        run_kwargs = {"host": host, "port": port}
    else:
        run_kwargs = {}
    if not show_fastmcp_banner:
        logger.info("Starting RsInstrument-mcp server...")
    mcp.run(transport=transport, show_banner=show_fastmcp_banner, **run_kwargs)
