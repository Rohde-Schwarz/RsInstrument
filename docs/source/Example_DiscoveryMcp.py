"""
Instrument-Discovery MCP tool usage patterns.

These snippets show how an MCP client would call the built-in tool.
Run the server with: RsInstrument-mcp --transport streamable-http
"""

# Default: TTL-cached find-only snapshot (source="cache" on hit)
# await session.call_tool("Instrument-Discovery", {})

# Live identification with model filter (source="live")
# await session.call_tool(
#     "Instrument-Discovery",
#     {
#         "identify": True,
#         "model": "FSW",
#         "manufacturer": "Rohde&Schwarz",
#     },
# )

# Custom VISA selection forces a live scan
# await session.call_tool(
#     "Instrument-Discovery",
#     {
#         "visa_select": "rs",
#         "expression": "TCPIP?*::INSTR",
#         "refresh": True,
#     },
# )

# Direct Python equivalent of the MCP tool (requires RsInstrument[mcp])
if __name__ == "__main__":
    import asyncio

    from RsInstrument.mcp.basic_tools import instrument_discovery

    print(asyncio.run(instrument_discovery()))
    print(asyncio.run(instrument_discovery(identify=True, model="FSW")))
