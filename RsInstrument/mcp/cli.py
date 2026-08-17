"""CLI for RsInstrument MCP server."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import typing
from pathlib import Path

from pydantic import ValidationError

from RsInstrument import __version__
from RsInstrument.mcp.file_transfer import FileTransferPolicy
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.server import DEFAULT_MCP_HEALTH_ENDPOINT, run
from RsInstrument.mcp.tool_specs import BuiltinToolSettings

logger = logging.getLogger(__name__)


class LoadWriteRulesAction(argparse.Action):
    """Load ``--write-rules`` PATH into a :class:`ScpiWritePolicy`, or leave ``None``."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | typing.Sequence[typing.Any] | None,
        option_string: str | None = None,
    ) -> None:
        if values is None:
            setattr(namespace, self.dest, None)
            return
        path = Path(str(values))
        try:
            policy = ScpiWritePolicy.from_file(path)
        except FileNotFoundError:
            parser.error(f"Write-rules file not found: {path}")
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid JSON in write-rules file {path}: {exc}")
        except ValidationError as exc:
            parser.error(f"Invalid write-rules schema in {path}: {exc}")
        setattr(namespace, self.dest, policy)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Run the RsInstrument MCP server.")
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
        default="streamable-http",
        help="FastMCP transport protocol (default: %(default)s)",
    )
    parser.add_argument(
        "--health-endpoint",
        dest="health_endpoint",
        type=str,
        default=DEFAULT_MCP_HEALTH_ENDPOINT,
        help="FastMCP health endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--show-fastmcp-banner",
        dest="show_fastmcp_banner",
        action="store_true",
        help="Show FastMCP banner on startup",
    )
    parser.add_argument(
        "--write-rules",
        dest="write_policy",
        action=LoadWriteRulesAction,
        default=None,
        metavar="PATH",
        help="Path to a JSON write-rules file (omit for built-in defaults)",
    )
    parser.add_argument(
        "--file-root",
        dest="file_root",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Local sandbox root for Instrument-File (requires --transport stdio "
            "and at least one --instrument-file-root)"
        ),
    )
    parser.add_argument(
        "--instrument-file-root",
        dest="instrument_file_roots",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Allowed instrument-side directory for Instrument-File "
            "(repeatable; requires --file-root and --transport stdio)"
        ),
    )
    return parser


def _build_settings_from_args(args: argparse.Namespace) -> BuiltinToolSettings:
    file_root = args.file_root
    instrument_roots = tuple(args.instrument_file_roots or ())
    if file_root or instrument_roots:
        if args.transport != "stdio":
            raise SystemExit(
                "--file-root / --instrument-file-root require --transport stdio"
            )
        if not file_root or not instrument_roots:
            raise SystemExit(
                "Both --file-root and at least one --instrument-file-root are required"
            )
        file_transfer = FileTransferPolicy(
            enabled=True,
            local_root=Path(file_root).resolve(),
            instrument_allowed_dirs=instrument_roots,
        )
    else:
        file_transfer = FileTransferPolicy.disabled()

    return BuiltinToolSettings.create(
        write_policy=args.write_policy,
        file_transfer=file_transfer,
    )


def main(argv: typing.Sequence[str] | None = None):
    """Run the MCP server from the command line."""
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
        settings = _build_settings_from_args(args)
        run(
            transport=args.transport,
            host=args.host,
            port=args.port,
            health_endpoint=args.health_endpoint,
            show_fastmcp_banner=args.show_fastmcp_banner,
            builtin_settings=settings,
        )
    except SystemExit:
        raise
    except (
        Exception
    ) as error:  # pragma: no cover - exercised in tests with forced exception
        if verbosity < default_log_level or default_log_level <= logging.DEBUG:
            logger.exception("%s", error)
        else:
            logger.exception("%s", error)
            logger.warning("Hint: Rerun with '--verbose' to show exception traceback.")
        sys.exit(1)
    except KeyboardInterrupt:  # pragma: no cover - exercised in tests
        logger.warning("Aborted by user")
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
