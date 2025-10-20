"""
Basic logging example to the console.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::192.168.1.101::INSTR')

# Switch ON logging to the console.
instr.logger.log_to_console = True
instr.logger.start()
instr.reset()

# Close the session
instr.close()
