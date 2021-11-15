.. code-block:: python

    """
    Using RsInstrument without VISA for LAN Raw socket communication
    """
    
    from RsInstrument import *
    
    instr = RsInstrument('TCPIP::192.168.56.101::5025::SOCKET', True, True, "SelectVisa='socket'")
    print(f'Visa manufacturer: {instr.visa_manufacturer}')
    print(f"\nHello, I am: '{instr.idn_string}'")
    print(f"\nNo VISA has been harmed or even used in this example.")
    
    # Close the session
    instr.close()
