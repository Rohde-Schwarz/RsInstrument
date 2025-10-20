"""
Querying ASCII float arrays.
"""

from time import time
from RsInstrument import *

rto = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
# Initiate a single acquisition and wait for it to finish
rto.write_str_with_opc("SINGle", 20000)

# Query array of floats in ASCII format
t = time()
waveform = rto.query_bin_or_ascii_float_list('FORM ASC;:CHAN1:DATA?')
print(f'Instrument returned {len(waveform)} points, query duration {time() - t:.3f} secs')

# Close the RTO session
rto.close()
