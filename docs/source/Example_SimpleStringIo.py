"""
Basic string write_str / query_str.
"""

from RsInstrument import *

instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
instr.reset()
print(instr.idn_string)

# Close the session
instr.close()
