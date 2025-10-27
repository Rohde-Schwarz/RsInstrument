"""
Example of logging to a file shared by multiple sessions.
The log file and the reference timestamp is set to the RsInstrument class variable,
which makes it available to all the instances immediately.
Each instance must set the LogToGlobalTarget=True in the constructor,
or later io.logger.set_logging_target_global().
"""

from RsInstrument import *
import os
from pathlib import Path
from datetime import datetime

RsInstrument.assert_minimum_version('1.102.0')

# Log file common for all the RsInstrument instances, saved in the same folder as this script,
# with the same name as this script, just with the suffix .ptc
# The previous file content is discarded.
log_file = open(Path(os.path.realpath(__file__)).stem + ".ptc", 'w')
RsInstrument.set_global_logging_target(log_file)

# If you do now care about the absolute times,
# here you can set relative timestamp of the first incoming entry.
RsInstrument.set_global_logging_relative_time_of_first_entry()

# Setting of the SMW: log to the global target and to the console
smw = RsInstrument(
    resource_name='TCPIP::10.102.12.13::hislip0',
    options=f'LoggingMode=On, LoggingToConsole=True, LoggingName=SMW, LogToGlobalTarget=On')

# Setting of the SMCV: log to the global target and to the console
smcv = RsInstrument(
    resource_name='TCPIP::10.102.12.14::hislip0',
    options='LoggingMode=On, LoggingToConsole=True, LoggingName=SMCV, LogToGlobalTarget=On')

smw.logger.info_raw("> Custom log entry from SMW session")
smw.reset()
smcv.logger.info_raw("> Custom log entry from SMCV session")
idn = smcv.query('*IDN?')
# Close the sessions
smw.close()
smcv.close()
# Show how much time each instrument needed for its operations.
smw.logger.info_raw("> SMW execution time: " + str(smw.get_total_execution_time()))
smcv.logger.info_raw("> SMCV execution time: " + str(smcv.get_total_execution_time()))

# Close the log file
log_file.close()
