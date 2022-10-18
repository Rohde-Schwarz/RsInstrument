.. code-block:: python

    """
    Basic string write_str / query_str
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    instr.write_str('*RST')
    response = instr.query_str('*IDN?')
    print(response)
    
    # Close the session
    instr.close()
