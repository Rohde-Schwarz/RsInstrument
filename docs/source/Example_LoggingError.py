"""
Logging example to the console with only errors logged.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::192.168.1.101::INSTR', options='LoggingMode=Errors')

# Switch ON logging to the console.
instr.logger.log_to_console = True

# Reset will not be logged, since no error occurred there
instr.reset()

# Now a misspelled command.
instr.write('*CLaS')

# A good command again, no logging here
idn = instr.query('*IDN?')

# Close the session
instr.close()
