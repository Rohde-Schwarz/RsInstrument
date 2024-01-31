.. code-block:: python

    """
    How to deal with RsInstrument exceptions
    """
    
    from RsInstrument import *
    
    instr = None
    # Try-catch for initialization. If an error occurs, the ResourceError is raised
    try:
        instr = RsInstrument('TCPIP::10.112.1.179::HISLIP', True, True)
    except ResourceError as e:
        print(e.args[0])
        print('Your instrument is probably OFF...')
        # Exit now, no point of continuing
        exit(1)
    
    # Dealing with commands that potentially generate errors OPTION 1:
    # Switching the status checking OFF temporarily
    instr.instrument_status_checking = False
    instr.write_str('MY:MISSpelled:COMMand')
    # Clear the error queue
    instr.clear_status()
    # Status checking ON again
    instr.instrument_status_checking = True
    
    # Dealing with queries that potentially generate errors OPTION 2:
    try:
        # You might want to reduce the VISA timeout to avoid long waiting
        instr.visa_timeout = 1000
        instr.query_str('MY:OTHEr:WRONg:QUERy?')
    
    except StatusException as e:
        # Instrument status error
        print(e.args[0])
        print('Nothing to see here, moving on...')
    
    except TimeoutException as e:
        # Timeout error
        print(e.args[0])
        print('That took a long time...')
    
    except RsInstrException as e:
        # RsInstrException is a base class for all the RsInstrument exceptions
        print(e.args[0])
        print('Some other RsInstrument error...')
    
    finally:
        instr.visa_timeout = 5000
        # Close the session in any case
        instr.close()
