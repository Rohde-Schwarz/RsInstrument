"""Tools for calling an instrument via SCPI commands."""

import argparse
import functools
import json
import logging
import sys
import typing

try:
    from mcp.server.fastmcp import FastMCP

    MCP_INSTALLED = True
except ImportError:
    MCP_INSTALLED = False

from RsInstrument import RsInstrument, __version__

logger = logging.getLogger(__name__)


def safe_tool(fn):
    """Decorator converting any raised Exception to standardized 'Error: <msg>' string.

    Applied to MCP-exposed functions so they never raise.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.error("Exception in tool %s: %s", fn.__name__, e)
            return f"Error: {e}"

    return wrapper


@safe_tool
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
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        response = inst.query(command)
        return response.strip()


@safe_tool
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
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        inst.write(command)
        return "Write command executed successfully."


@safe_tool
def instrument_fetch_errors(resource: str, opc_timeout: int = 5000) -> str:
    """Fetch errors from an instrument via RsInstrument.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        errors = inst.query_all_errors_with_codes()
        if not errors:
            return "No errors."

        return json.dumps([{"code": code, "message": msg} for code, msg in errors])


@safe_tool
def instrument_reset(resource: str, opc_timeout: int = 5000) -> str:
    """Reset an instrument via RsInstrument.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        inst.reset()
        return "Instrument reset successfully."


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
    logger.info("Starting RsInstrument MCP server...")
    mcp.run(transport=transport, mount_path=mount_path)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the Test Intelligence Agent server."
    )
    parser.add_argument(
        "-V",
        "--version",
        help="Show version number and exit",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        help="Increase output (Option is additive to increase verbosity)",
        action="count",
        default=0,
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        help="Reduce output (Option is additive to decrease verbosity)",
        action="count",
        default=0,
    )
    parser.add_argument(
        "--host",
        dest="host",
        default="localhost",
        help="FastMCP Hostname/IP to bind (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        dest="port",
        type=int,
        default=8000,
        help="FastMCP port to bind (default: %(default)s)",
    )
    parser.add_argument(
        "--transport",
        dest="transport",
        type=str,
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="FastMCP transport protocol (default: %(default)s)",
    )
    parser.add_argument(
        "--mount-path",
        dest="mount_path",
        type=str,
        help="FastMCP mount path (default: %(default)s)",
    )
    return parser


def main(argv: typing.Sequence[str] | None = None):
    """Main entry point for command line execution."""
    args = create_parser().parse_args(argv)

    logging.basicConfig(
        format="{asctime} [{levelname:^8}] ({filename}:{lineno}) {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    default_log_level = logging.WARNING
    verbosity = default_log_level - ((args.verbose - args.quiet) * 10)
    log_level = min(logging.CRITICAL, max(logging.DEBUG, verbosity))
    logger.setLevel(log_level)
    try:
        run(transport=args.transport, host=args.host, port=args.port, mount_path=args.mount_path)
    except (
        Exception
    ) as error:  # pragma: no cover - exercised in tests with forced exception
        if verbosity < default_log_level or default_log_level <= logging.DEBUG:
            logger.exception(error)
        else:
            logger.error(error)
            logger.warning("Hint: Rerun with '--verbose' to show exception traceback.")
        sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover - exercised in tests
        logger.warning("Aborted by user")
        sys.exit(1)


if __name__ == "__main__":
    main()
