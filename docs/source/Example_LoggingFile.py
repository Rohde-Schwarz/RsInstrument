"""
Example of logging to a file.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::192.168.1.101::INSTR')

# We also want to log to the console.
instr.logger.log_to_console = True

# Logging target is our file
file = open(r'c:\temp\my_file.txt', 'w')
instr.logger.set_logging_target(file)
instr.logger.start()

# Instead of the 'TCPIP::192.168.1.101::INSTR', show 'MyDevice'
instr.logger.device_name = 'MyDevice'

# Custom user entry
instr.logger.info_raw('----- This is my custom log entry. ---- ')

instr.reset()

# Close the session
instr.close()

# Close the log file
file.close()
