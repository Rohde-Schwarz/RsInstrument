.. code-block:: python

    """
    Example of logging to a file shared by multiple sessions.
    The log file and the reference timestamp is set to the RsInstrument class variable,
    which makes it available to all the instances immediately.
    Each instance must set the LogToGlobalTarget=True in the constructor,
    or later io.logger.set_logging_target_global()
    """
    
    from RsInstrument import *
    import os
    from pathlib import Path
    from datetime import datetime
    
    # Make sure you have the RsInstrument version 1.50.0 and newer
    RsInstrument.assert_minimum_version('1.50.0')
    
    # Log file common for all the RsInstrument instances, saved in the same folder as this script,
    # with the same name as this script, just with the suffix .ptc
    # The previous file content is discarded.
    log_file = open(Path(os.path.realpath(__file__)).stem + ".ptc", 'w')
    RsInstrument.set_global_logging_target(log_file)
    # Here you can set relative timestamp if you do now worry about the absolute times.
    RsInstrument.set_global_logging_relative_timestamp(datetime.now())
    
    # Setting of the SMW: log to the global target and to the console
    smw = RsInstrument(
        resource_name='TCPIP::192.168.1.101::HISLIP',
        options=f'LoggingMode=On, LoggingToConsole=True, LoggingName=SMW, LogToGlobalTarget=On')
    
    # Setting of the SMCV: log to the global target and to the console
    smcv = RsInstrument(
        resource_name='TCPIP::192.168.1.101::HISLIP',
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
