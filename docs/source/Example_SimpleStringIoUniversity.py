.. code-block:: python

    """
    Basic string write / query
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    instr.write('*RST')
    response = instr.query('*IDN?')
    print(response)
    
    # Close the session
    instr.close()
