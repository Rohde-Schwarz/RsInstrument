"""Compose policy-bound built-ins with custom tools, then start the server.

Use this pattern when you need the built-in ToolSpec list yourself (filter,
reorder, or merge) instead of only calling ``add_builtin_tools``.
"""

from RsInstrument import RsInstrument
from RsInstrument.mcp import (
    BuiltinToolSettings,
    ScpiWritePolicy,
    ToolSpec,
    create_builtin_tool_specs,
    merge_tool_specs,
    run,
    safe_tool,
)


@safe_tool
def instrument_product_overlay(resource: str, opc_timeout: int = 5000) -> str:
    """Example product-specific tool alongside the RsInstrument built-ins."""
    with RsInstrument(resource) as inst:
        inst.opc_timeout = opc_timeout
        return inst.query("*IDN?").strip()


if __name__ == "__main__":
    settings = BuiltinToolSettings.create(
        write_policy=ScpiWritePolicy.from_file("write-rules.json"),
        excluded_tools={"Instrument-Discovery"},
    )
    # Fresh callables closed over ``settings.write_policy`` (and other policies).
    # Do not register ``basic_tools.instrument_write_scpi`` here — that alias
    # always uses ScpiWritePolicy.defaults() and ignores ``settings``.
    builtins = create_builtin_tool_specs(settings)
    custom = [
        ToolSpec(
            name="Instrument-Product-Overlay",
            description="Product MCP overlay example.",
            fn=instrument_product_overlay,
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
        ),
    ]
    run(
        host="localhost",
        port=8000,
        transport="streamable-http",
        tools=merge_tool_specs(builtins, custom),
        include_builtin_tools=False,
    )
