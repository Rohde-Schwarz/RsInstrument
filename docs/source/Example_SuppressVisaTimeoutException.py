.. code-block:: python

    """
    Suppress VISA Timeout exception for certain commands with the Suppress Context-manager.
    """
    
    from RsInstrument import *
    
    RsInstrument.assert_minimum_version('1.70.0')
    instr = RsInstrument('TCPIP::10.99.2.12::HISLIP', True, True)
    
    with instr.visa_tout_suppressor(visa_tout_ms=500) as supp:
        instr.query('*IDaN?')
    
    if supp.get_timeout_occurred():
        print("Timeout occurred inside the context")
