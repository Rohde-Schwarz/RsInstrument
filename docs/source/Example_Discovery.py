"""
Discover instruments with RsInstrument.discovery().
"""

from RsInstrument import RsInstrument

# Find only — no *IDN? traffic
snapshot = RsInstrument.discovery()
for instr in snapshot.instruments:
    print(instr.resource)

# Optional identification
snapshot = RsInstrument.discovery(identify=True, identify_timeout_ms=5000)
for instr in snapshot.instruments:
    if instr.identified:
        print(f"{instr.model} (S/N {instr.serial}) @ {instr.resource}")
    else:
        print(f"[not identified] {instr.resource}")

# Filter after identify
for smw in snapshot.filter(model="SMW"):
    print(f"Found SMW: {smw.resource} — FW {smw.firmware}")
