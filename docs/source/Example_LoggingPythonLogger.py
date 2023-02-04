.. code-block:: python

    """
    Example of logging to a python standard logger object.
    """
    
    import logging
	
    from RsInstrument import *
    
    # Make sure you have the RsInstrument version 1.50.0 and newer
    RsInstrument.assert_minimum_version('1.50.0')
    
    
    class LoggerStream:
        """Class to wrap the python's logging into a stream interface."""
    
        @staticmethod
        def write(log_entry: str) -> None:
            """Method called by the RsInstrument to add the log_entry.
            Use it to do your custom operation, in our case calling python's logging function."""
            logging.info('RsInstrument: ' + log_entry.rstrip())
    
        def flush(self) -> None:
            """Do the operations at the end. In our case, we do nothing."""
            pass
    
    
    # Setting of the SMW
    smw = RsInstrument('TCPIP::10.99.2.10::hislip0', options='LoggingMode=On, LoggingName=SMW')
    
    # Create a logger stream object
    target = LoggerStream()
    logging.getLogger().setLevel(logging.INFO)
    
    # Adjust the log string to not show the start time
    smw.logger.set_format_string('PAD_LEFT25(%DEVICE_NAME%) PAD_LEFT12(%DURATION%)  %LOG_STRING_INFO%: %LOG_STRING%')
    smw.logger.set_logging_target(target)  # Log to my target
    
    smw.logger.info_raw("> Custom log from SMW session")
    smw.reset()
    
    # Close the sessions
    smw.close()
