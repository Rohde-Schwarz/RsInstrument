.. code-block:: python

    """
    Basic logging example to the console
    """
    
    from RsInstrument import *
    
    # Make sure you have the RsInstrument version 1.50.0 and newer
    RsInstrument.assert_minimum_version('1.50.0')
    instr = RsInstrument('TCPIP::192.168.1.101::INSTR')
    
    # Switch ON logging to the console.
    instr.logger.log_to_console = True
    instr.logger.mode = LoggingMode.On
    instr.reset()
    
    # Close the session
    instr.close()
