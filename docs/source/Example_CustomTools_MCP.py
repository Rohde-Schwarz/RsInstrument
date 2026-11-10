"""Add custom tools on top of the default built-in set.

For registering built-ins on an existing FastMCP server, use
``add_builtin_tools(server, BuiltinToolSettings.create(...))``.
For filtering / merging the built-in list yourself (with write policy bound),
see ``Example_ComposeBuiltinTools_MCP.py``.
"""

from RsInstrument import RsInstrument
from RsInstrument.mcp import ToolSpec, run, safe_tool


@safe_tool  # Bare form: exceptions only, no post-call GTL restore
def instrument_fancy_function(resource: str, opc_timeout: int = 5000) -> str:
    """My fancy function for RsInstrument MCP.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for the operation complete (OPC) query.
            Default is 5000 ms.

    Returns:
        The response from the instrument.
    """
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        # your logic goes here
        return "RsInstrument is awesome."


@safe_tool
def instrument_with_local_restore(resource: str, opc_timeout: int = 5000) -> str:
    """Example tool controlled via explicit ``Instrument-Go-To-Local`` when needed.

    Args:
        resource: The VISA resource string of the instrument.
        opc_timeout: Timeout in milliseconds for OPC.

    Returns:
        A short status string.
    """
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        inst.write("*IDN?")
        return "Done."


if __name__ == "__main__":
    custom_tools = [
        (
            "Instrument-Fancy-SCPI",  # Tool name
            "This is an awesome function",  # Tool description
            instrument_fancy_function,  # Tool function
        ),
        ToolSpec(
            name="Instrument-With-Local-Restore",
            description="Example tool and optional annotations.",
            fn=instrument_with_local_restore,
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
        ),
    ]
    # Default: built-ins (default policies) + custom; same-name custom tools replace built-ins.
    run(
        host="localhost",
        port=8000,
        transport="streamable-http",
        tools=custom_tools,
    )
