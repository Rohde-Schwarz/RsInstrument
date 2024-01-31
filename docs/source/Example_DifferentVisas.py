.. code-block:: python

    """
    Choosing VISA implementation
    """
    
    from RsInstrument import *
    
    # Force use of the Rs Visa. For e.g.: NI Visa, use the "SelectVisa='ni'"
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True, "SelectVisa='rs'")
    
    idn = instr.query_str('*IDN?')
    print(f"\nHello, I am: '{idn}'")
    print(f"\nI am using the VISA from: {instr.visa_manufacturer}")
    
    # Close the session
    instr.close()
