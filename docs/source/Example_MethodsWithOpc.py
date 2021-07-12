.. code-block:: python

    """
    Write / Query with OPC
    The SCPI commands syntax is for demonstration only
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    instr.visa_timeout = 3000
    # opc_timeout default value is 10000 ms
    instr.opc_timeout = 20000
    
    # Send Reset command and wait for it to finish
    instr.write_str_with_opc('*RST')
    
    # Initiate the measurement and wait for it to finish, define the timeout 50 secs
    # Notice no changing of the VISA timeout
    instr.write_str_with_opc('INIT', 50000)
    # The results are ready, simple fetch returns the results
    # Waiting here is not necessary
    result1 = instr.query_str('FETCH:MEASUREMENT?')
    
    # READ command starts the measurement, we use query_with_opc to wait for the measurement to finish
    result2 = instr.query_str_with_opc('READ:MEASUREMENT?', 50000)
    
    # Close the session
    instr.close()
