"""Pytest integration with OTEL-traced RsInstrument."""

import pytest
from RsInstrument import RsInstrument
from RsInstrument.otel import setup_otel, teardown_otel


@pytest.fixture(scope="session", autouse=True)
def _enable_scpi_tracing():
    """Enable OTEL tracing for all SCPI commands in this test session."""
    setup_otel(extra_attributes={"test.suite": "integration"})
    yield
    teardown_otel()


@pytest.fixture
def instrument():
    """Create a simulated instrument for testing."""
    instr = RsInstrument("TCPIP::192.168.1.1::INSTR", options="Simulate=True")
    yield instr
    instr.close()


def test_instrument_identity(instrument):
    """Every query automatically produces an OTEL span."""
    idn = instrument.query("*IDN?")
    assert "Rohde" in idn
