"""
Suppress VISA Timeout exception for certain commands with the Suppress Context-manager.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::192.168.1.110::hislip0', True, True)

with instr.visa_tout_suppressor(visa_tout_ms=500) as supp:
    instr.query('*IDaN?')

if supp.get_timeout_occurred():
    print("Timeout occurred inside the context")
