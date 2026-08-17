"""Basic OTEL setup for RsInstrument SCPI tracing."""

from RsInstrument import RsInstrument
from RsInstrument.otel import setup_otel

setup_otel(
    traces_exporter="otlp",
    otlp_endpoint="http://localhost:4318",
)

instr = RsInstrument("TCPIP::192.168.1.1::INSTR")
print(instr.query("*IDN?"))
instr.write("*RST")
instr.close()
