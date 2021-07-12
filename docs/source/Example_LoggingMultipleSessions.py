.. code-block:: python

    """
    Example of logging to a file shared by multiple sessions
    """
    
    from RsInstrument import *
    
    # Make sure you have the RsInstrument version 1.14.0 and newer
    RsInstrument.assert_minimum_version('1.14.0')
    
    # log file common for all the instruments
    file = open(r'c:\temp\my_file.txt', 'w')
    
    # Setting of the SMW
    smw = RsInstrument('TCPIP::192.168.1.101::INSTR', options='LoggingMode=On, LoggingName=SMW')
    smw.logger.set_logging_target(file, console_log=True)  # Log to file and the console
    
    # Setting of the SMCV
    smcv = RsInstrument('TCPIP::192.168.1.102::INSTR', options='LoggingMode=On, LoggingName=SMCV')
    smcv.logger.set_logging_target(file, console_log=True)  # Log to file and the console
    
    smw.logger.info_raw("Custom log from SMW session")
    smw.reset()
    smcv.logger.info_raw("Custom log from SMCV session")
    idn = smcv.query('*IDN?')
    
    # Close the sessions
    smw.close()
    smcv.close()
    
    # Close the log file
    file.close()
