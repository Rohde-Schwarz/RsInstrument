.. code-block:: python

    """
    Basic string write_xxx / query_xxx
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    instr.visa_timeout = 5000
    instr.instrument_status_checking = True
    instr.write_int('SWEEP:COUNT ', 10)  # sending 'SWEEP:COUNT 10'
    instr.write_bool('SOURCE:RF:OUTPUT:STATE ', True)  # sending 'SOURCE:RF:OUTPUT:STATE ON'
    instr.write_float('SOURCE:RF:FREQUENCY ', 1E9)  # sending 'SOURCE:RF:FREQUENCY 1000000000'
    
    sc = instr.query_int('SWEEP:COUNT?')  # returning integer number sc=10
    out = instr.query_bool('SOURCE:RF:OUTPUT:STATE?')  # returning boolean out=True
    freq = instr.query_float('SOURCE:RF:FREQUENCY?')  # returning float number freq=1E9
    
    # Close the session
    instr.close()
