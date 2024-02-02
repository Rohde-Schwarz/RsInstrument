.. code-block:: python

    """
    Basic string write / query
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    instr.reset()
    print(instr.idn_string)
    
    # Close the session
    instr.close()
