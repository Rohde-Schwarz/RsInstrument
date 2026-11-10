"""
Logging example with:
 - Logging to the console.
 - Initialization in the constructor.
 - Time will be relative to the first log entry.
 - Time statistics at the end.
"""
import time

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument(
    'TCPIP::192.168.1.101::hislip0',
    options='LoggingToConsole=True, LoggingMode=On, LoggingRelativeTimeOfFirstEntry=True')

print('\nEntries above come from the constructor.\n')
idn = instr.query('*IDN?')
# Pause for 1 second, to amplify the difference between
# simple time delta get_total_time() and the get_total_execution_time().
time.sleep(1.0)
instr.reset()

print('\nCommunication time spent: ' + str(instr.get_total_execution_time()))
print('Program time spent:       ' + str(instr.get_total_time()))

instr.reset_time_statistics()
print('\nWe can reset the time stats to start from 0 again:\n')

# Also, the next log entry will have the start time set to 00:00:00.000
instr.logger.set_time_offset_zero_on_first_entry()

# Again, pause for 500 milliseconds to see
# the difference between the get_total_time() and the get_total_execution_time().
time.sleep(0.5)
instr.check_status()

# Close the session
instr.close()

print('\nCommunication time spent: ' + str(instr.get_total_execution_time()))
print('Program time spent:       ' + str(instr.get_total_time()))
