"""Tools for calling an instrument via SCPI commands."""

import json
import logging
import typing

try:
    from mcp.server.fastmcp import FastMCP

    MCP_INSTALLED = True
except ImportError:
    MCP_INSTALLED = False

from RsInstrument import RsInstrument, __version__

logger = logging.getLogger(__name__)


def instrument_query_scpi(command: str, resource: str, opc_timeout: int = 5000) -> str:
    """Query a command from an instrument via RsInstrument.

    Args:
        command: The SCPI query command to send to the instrument.
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    try:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            response = inst.query(command)
            return response.strip()
    except Exception as e:
        return f"Error: {e}"


def instrument_write_scpi(command: str, resource: str, opc_timeout: int = 5000) -> str:
    """Write a command to an instrument via RsInstrument.

    Args:
        command: The SCPI write command to send to the instrument.
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    try:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            inst.write(command)
            return "Write command executed successfully."
    except Exception as e:
        return f"Error: {e}"


def instrument_fetch_errors(resource: str, opc_timeout: int = 5000) -> str:
    """Fetch errors from an instrument via RsInstrument.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    try:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            errors = inst.query_all_errors_with_codes()
            if not errors:
                return "No errors."
            return json.dumps(errors)
    except Exception as e:
        return f"Error: {e}"


def instrument_reset(resource: str, opc_timeout: int = 5000) -> str:
    """Reset an instrument via RsInstrument.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    try:
        with RsInstrument(resource) as inst:
            inst.opc_timeout = opc_timeout
            inst.reset()
            return "Instrument reset successfully."
    except Exception as e:
        return f"Error: {e}"


def create_fastmcp_server(
    *args,
    tools: typing.Sequence[typing.Tuple[str, str, typing.Callable]] | None = None,
    **kwargs,
):
    """Create a FastMCP tool for SCPI commands.

    Args:
        *args: Positional arguments to pass to FastMCP.
        tools: Register a sequence of tuples containing tool names, descriptions and their corresponding callables.
        **kwargs: Keyword arguments to pass to FastMCP.
    """
    if not MCP_INSTALLED:
        raise ImportError(
            "mcp is required for this module. Please install with 'pip install RsInstrument[mcp]'"
        )
    if tools is None:
        tools = []
    kwargs.setdefault("name", f"{__package__}-mcp")
    kwargs.setdefault("version", __version__)
    fastmcp = FastMCP(*args, **kwargs)

    fastmcp.tool(
        name="Instrument-Query-SCPI",
        description="Query a command from an instrument via RsInstrument.",
    )(instrument_query_scpi)
    fastmcp.tool(
        name="Instrument-Write-SCPI",
        description="Write a command to an instrument via RsInstrument.",
    )(instrument_write_scpi)
    fastmcp.tool(
        name="Instrument-Fetch-Errors",
        description="Fetch errors from an instrument via RsInstrument.",
    )(instrument_fetch_errors)
    fastmcp.tool(name="Instrument-Reset", description="Reset the instrument")(
        instrument_reset
    )
    for tool_name, tool_description, tool_callable in tools:
        fastmcp.tool(name=tool_name, description=tool_description)(tool_callable)
    return fastmcp


def run(
    *args,
    transport: typing.Literal["stdio", "sse", "streamable-http"] = "stdio",
    mount_path: str | None = None,
    **kwargs,
):
    """Run the MCP server."""
    mcp = create_fastmcp_server(*args, **kwargs)
    logger.info("Starting Instrument MCP server...")
    mcp.run(transport=transport, mount_path=mount_path)


if __name__ == "__main__":
    run()
