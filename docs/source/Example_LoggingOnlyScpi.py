"""
Logging only the SCPI commands to the console.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::10.102.52.53::hislip0')

# Switch ON logging to the console.
instr.logger.log_to_console = True
instr.logger.set_format_string('PAD_LEFT12(%START_TIME%) PAD_LEFT12(%DURATION%) %SCPI_COMMAND%')
instr.logger.start()
instr.reset()

# Close the session
instr.close()
