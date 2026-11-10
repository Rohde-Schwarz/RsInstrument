"""Tools for calling an instrument via SCPI commands.

Public extension API of the MCP package: everything needed to run a server or to
add RsInstrument's built-in tools to your own. The tools themselves live in the
focused submodules (``basic_tools``, ``batch``, ``device_io``, ``file_transfer``,
``state_storage``).
"""

from __future__ import annotations

from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.batch import BatchScpiCommand, ScpiBatchPolicy
from RsInstrument.mcp.cli import main
from RsInstrument.mcp.device_io import DeviceIoProfile, DeviceIoProfileRegistry
from RsInstrument.mcp.file_transfer import FileTransferPolicy
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.server import create_fastmcp_server, run
from RsInstrument.mcp.tool_specs import (
    BuiltinToolSettings,
    ToolSpec,
    add_builtin_tools,
    create_builtin_tool_specs,
    merge_tool_specs,
)

__all__ = [
    "BatchScpiCommand",
    "BuiltinToolSettings",
    "DeviceIoProfile",
    "DeviceIoProfileRegistry",
    "FileTransferPolicy",
    "ScpiBatchPolicy",
    "ScpiWritePolicy",
    "ToolSpec",
    "add_builtin_tools",
    "create_builtin_tool_specs",
    "create_fastmcp_server",
    "main",
    "merge_tool_specs",
    "run",
    "safe_tool",
]
