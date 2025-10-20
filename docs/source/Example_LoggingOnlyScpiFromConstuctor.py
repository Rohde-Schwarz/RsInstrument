"""
Logging only the SCPI commands to the console.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::10.102.52.53::hislip0',
             options='LoggingMode=On, '
                     'LoggingToConsole=True, '
                     'LoggingFormat = "PAD_LEFT12(%START_TIME%) PAD_LEFT12(%DURATION%) %SCPI_COMMAND%"')
instr.reset()

# Close the session
instr.close()
