"""
Using Context-Manager for you RsInstrument session.
No matter what happens inside the 'with' section, your session is always closed properly.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
with RsInstrument('TCPIP::192.168.2.101::hislip0') as instr:
    idn = instr.query('*IDN?')
    print(f"\nHello, I am: '{idn}'")

