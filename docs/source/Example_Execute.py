"""
The execute() method - auto-dispatch to write / query / OPC-synced I/O.
The SCPI commands syntax is for demonstration only.
"""

from RsInstrument import *

instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
instr.visa_timeout = 3000
instr.opc_timeout = 20000

# Plain query -> query('*IDN?'), returns the response string
idn = instr.execute('*IDN?')
print(f'Instrument: {idn}')

# Plain write -> write('*CLS'), returns None
instr.execute('*CLS')

# Trailing ;*OPC -> write_with_opc('INIT'), waits until the instrument is finished
instr.execute('INIT;*OPC')

# Trailing ;*OPC on a query -> query_with_opc('FETCH:MEASUREMENT?')
results = instr.execute('FETCH:MEASUREMENT?;*OPC')
print(f'Results: {results}')

# Default: ;*OPC? is kept and sent as an ordinary compound query
# (the instrument answers with the measurement result followed by '1')
raw = instr.execute('FETCH:MEASUREMENT?;*OPC?')
print(f'Raw compound response: {raw}')

# When optimize_opc_execute is True, ;*OPC? is also treated as an OPC-sync suffix
# and stripped, so the call becomes query_with_opc('FETCH:MEASUREMENT?')
instr.optimize_opc_execute = True
results_opt = instr.execute('FETCH:MEASUREMENT?;*OPC?')
print(f'Optimized OPC results: {results_opt}')

# Close the session
instr.close()
