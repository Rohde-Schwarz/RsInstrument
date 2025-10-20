"""
Sharing the same physical VISA session by two different RsInstrument objects.
"""

from RsInstrument import *

instr1 = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
instr2 = RsInstrument.from_existing_session(instr1)

print(f'instr1: {instr1.idn_string}')
print(f'instr2: {instr2.idn_string}')

# Closing the instr2 session does not close the instr1 session - instr1 is the 'session master'
instr2.close()
print(f'instr2: I am closed now')

print(f'instr1: I am  still opened and working: {instr1.idn_string}')
instr1.close()
print(f'instr1: Only now I am closed.')
