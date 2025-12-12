"""Tests for tools/instrument.py module using pytest-style approach with proper mocking."""

from unittest.mock import MagicMock, patch

import pytest

from RsInstrument.mcp import (
    create_fastmcp_server,
    instrument_fetch_errors,
    instrument_query_scpi,
    instrument_reset,
    instrument_write_scpi,
    main,
    run,
    safe_tool,
)


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_query_scpi_success(mock_rs_instrument_class):
    """Test successful SCPI query operation."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)
    mock_inst.query.return_value = "  Test Response  "

    result = instrument_query_scpi("*IDN?", "test_resource", 5000)

    assert result == "Test Response"
    mock_inst.query.assert_called_once_with("*IDN?")
    assert mock_inst.opc_timeout == 5000


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_query_scpi_exception(mock_rs_instrument_class):
    """Test SCPI query with exception."""
    mock_rs_instrument_class.side_effect = Exception("Connection failed")

    result = instrument_query_scpi("*IDN?", "test_resource", 5000)

    assert result == "Error: Connection failed"


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_write_scpi_success(mock_rs_instrument_class):
    """Test successful SCPI write operation."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)

    result = instrument_write_scpi("*RST", "test_resource", 5000)

    assert result == "Write command executed successfully."
    mock_inst.write.assert_called_once_with("*RST")
    assert mock_inst.opc_timeout == 5000


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_write_scpi_exception(mock_rs_instrument_class):
    """Test SCPI write with exception."""
    mock_rs_instrument_class.side_effect = Exception("Write failed")

    result = instrument_write_scpi("*RST", "test_resource", 5000)

    assert result == "Error: Write failed"


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_fetch_errors_success_no_errors(mock_rs_instrument_class):
    """Test successful error fetching with no errors."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)
    mock_inst.query_all_errors_with_codes.return_value = []

    result = instrument_fetch_errors("test_resource", 5000)

    assert result == "No errors."
    assert mock_inst.opc_timeout == 5000


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_fetch_errors_success_with_errors(
    mock_rs_instrument_class
):
    """Test successful error fetching with errors present."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)
    errors = [(-113, "Undefined header")]
    mock_inst.query_all_errors_with_codes.return_value = errors

    result = instrument_fetch_errors("test_resource", 5000)

    assert result == '[{"code": -113, "message": "Undefined header"}]'


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_fetch_errors_exception(mock_rs_instrument_class):
    """Test error fetching with exception."""
    mock_rs_instrument_class.side_effect = Exception("Fetch failed")

    result = instrument_fetch_errors("test_resource", 5000)

    assert result == "Error: Fetch failed"


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_reset_success(mock_rs_instrument_class):
    """Test successful instrument reset operation."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)

    result = instrument_reset("test_resource", 5000)

    assert result == "Instrument reset successfully."
    mock_inst.reset.assert_called_once()
    assert mock_inst.opc_timeout == 5000


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_reset_exception(mock_rs_instrument_class):
    """Test instrument reset with exception."""
    mock_rs_instrument_class.side_effect = Exception("Reset failed")

    result = instrument_reset("test_resource", 5000)

    assert result == "Error: Reset failed"


@patch("RsInstrument.mcp.FastMCP")
def test_create_fastmcp_server(mock_fastmcp_class):
    """Test creation of FastMCP server with all instrument tools registered."""
    mock_fastmcp = MagicMock()
    mock_fastmcp_class.return_value = mock_fastmcp
    mock_tool_decorator = MagicMock()
    mock_fastmcp.tool.return_value = mock_tool_decorator

    result = create_fastmcp_server()

    mock_fastmcp_class.assert_called_once()
    assert result == mock_fastmcp

    # Verify that tools are registered (should be 4 tools)
    assert mock_fastmcp.tool.call_count == 4


@pytest.mark.parametrize(
    "command,resource,timeout",
    [
        ("*IDN?", "instrument1", 5000),
        ("SYST:ERR?", "instrument2", 10000),
        (":FREQ 1000", "generator", 3000),
    ],
)
@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_query_scpi_various_inputs(
    mock_rs_instrument_class, command, resource, timeout
):
    """Test SCPI query with various input combinations."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)
    mock_inst.query.return_value = f"Response for {command}"

    result = instrument_query_scpi(command, resource, timeout)

    assert result == f"Response for {command}"
    mock_inst.query.assert_called_once_with(command)
    assert mock_inst.opc_timeout == timeout


@pytest.mark.parametrize(
    "command,resource,timeout",
    [
        ("*RST", "instrument1", 5000),
        (":OUTP ON", "instrument2", 10000),
        ("FREQ 2000", "generator", 3000),
    ],
)
@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_write_scpi_various_inputs(
    mock_rs_instrument_class, command, resource, timeout
):
    """Test SCPI write with various input combinations."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)

    result = instrument_write_scpi(command, resource, timeout)

    assert result == "Write command executed successfully."
    mock_inst.write.assert_called_once_with(command)
    assert mock_inst.opc_timeout == timeout


@patch("RsInstrument.mcp.RsInstrument")
def test_instrument_operations_default_timeout(mock_rs_instrument_class):
    """Test that default timeouts are used correctly."""
    mock_inst = MagicMock()
    mock_rs_instrument_class.return_value.__enter__ = MagicMock(return_value=mock_inst)
    mock_rs_instrument_class.return_value.__exit__ = MagicMock(return_value=None)
    mock_inst.query.return_value = "OK"
    mock_inst.query_all_errors_with_codes.return_value = []

    # Test default timeouts (5000ms for most operations)
    instrument_query_scpi("*IDN?", "test")
    assert mock_inst.opc_timeout == 5000

    instrument_write_scpi("*RST", "test")
    assert mock_inst.opc_timeout == 5000

    instrument_fetch_errors("test")
    assert mock_inst.opc_timeout == 5000

    instrument_reset("test")
    assert mock_inst.opc_timeout == 5000


def test_safe_tool_wraps_exceptions():
    """Ensure safe_tool converts exceptions to standardized error strings."""

    @safe_tool
    def unstable():
        raise RuntimeError("unexpected boom")

    assert unstable() == "Error: unexpected boom"


def test_create_fastmcp_server_requires_fastmcp():
    """create_fastmcp_server should demand FastMCP installation."""
    with patch("RsInstrument.mcp.MCP_INSTALLED", False):
        with pytest.raises(ImportError):
            create_fastmcp_server()


@patch("RsInstrument.mcp.FastMCP")
def test_create_fastmcp_server_registers_custom_tools(mock_fastmcp_class):
    """Custom tools supplied to create_fastmcp_server are registered."""
    mock_fastmcp = MagicMock()
    mock_fastmcp_class.return_value = mock_fastmcp
    mock_tool_decorator = MagicMock()
    mock_fastmcp.tool.return_value = mock_tool_decorator
    mock_fastmcp.custom_route.return_value = lambda fn: fn

    custom_callable = MagicMock()
    result = create_fastmcp_server(
        tools=[("Custom", "desc", custom_callable)], health_endpoint="/ready"
    )

    assert result == mock_fastmcp
    mock_fastmcp_class.assert_called_once()
    mock_fastmcp.custom_route.assert_called_once_with("/ready", methods=["GET"])
    mock_fastmcp.tool.assert_any_call(name="Custom", description="desc")
    assert mock_tool_decorator.call_count == 5  # four built-ins + custom tool
    mock_tool_decorator.assert_any_call(custom_callable)


def test_run_invokes_fastmcp_run():
    """run() should create the server and trigger FastMCP.run()."""
    mock_mcp = MagicMock()
    with patch("RsInstrument.mcp.create_fastmcp_server", return_value=mock_mcp) as mock_create:
        extra_tool = ("Extra", "desc", MagicMock())
        run(
            "arg",
            transport="sse",
            mount_path="/path",
            tools=[extra_tool],
            health_endpoint="/live",
            host="0.0.0.0",
            port=9000,
        )

    mock_create.assert_called_once_with(
        "arg",
        tools=[extra_tool],
        health_endpoint="/live",
        host="0.0.0.0",
        port=9000,
    )
    mock_mcp.run.assert_called_once_with(transport="sse", mount_path="/path")


@patch("RsInstrument.mcp.run")
@patch("RsInstrument.mcp.logging.basicConfig")
def test_main_invokes_run_with_cli_args(mock_basic_config, mock_run):
    """main() should parse CLI args and invoke run() with them."""
    argv = [
        "--transport",
        "sse",
        "--host",
        "0.0.0.0",
        "--port",
        "1234",
        "--mount-path",
        "/mcp",
        "--health-endpoint",
        "/ping",
        "-vv",
    ]

    main(argv)

    mock_basic_config.assert_called_once()
    mock_run.assert_called_once_with(
        transport="sse",
        host="0.0.0.0",
        port=1234,
        mount_path="/mcp",
        health_endpoint="/ping",
    )


def test_main_handles_exception_and_exits():
    """main() should surface non-KeyboardInterrupt errors via SystemExit."""
    with patch("RsInstrument.mcp.run", side_effect=RuntimeError("boom")), patch(
        "RsInstrument.mcp.logger"
    ) as mock_logger:
        with pytest.raises(SystemExit) as excinfo:
            main([])

    assert excinfo.value.code == 1
    mock_logger.error.assert_called_once()
    mock_logger.warning.assert_called_once_with(
        "Hint: Rerun with '--verbose' to show exception traceback."
    )


def test_main_handles_keyboard_interrupt():
    """KeyboardInterrupt is converted to SystemExit with hint."""
    with patch("RsInstrument.mcp.run", side_effect=KeyboardInterrupt), patch(
        "RsInstrument.mcp.logger"
    ) as mock_logger:
        with pytest.raises(SystemExit) as excinfo:
            main([])

    assert excinfo.value.code == 1
    mock_logger.warning.assert_called_once_with("Aborted by user")


