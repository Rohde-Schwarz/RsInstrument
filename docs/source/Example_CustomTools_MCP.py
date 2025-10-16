from RsInstrument import RsInstrument
from RsInstrument.mcp import run, safe_tool


@safe_tool  # Decorator to catch and log exceptions and return them as error messages to the agent
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


if __name__ == "__main__":
    run(
        host="localhost",
        port=8000,
        transport="streamable-http",
        tools=[
            (
                "Instrument-Fancy-SCPI",  # Tool name
                "This is an awesome function",  # Tool description
                instrument_fancy_function,  # Tool function
            )
        ],
    )
