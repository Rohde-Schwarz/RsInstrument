.. code-block:: python

    """
    Basic example on how to use the RsInstrument module for remote-controlling your VISA instrument
    Preconditions:
        - Installed RsInstrument Python module Version 1.50.0 or newer from pypi.org
        - Installed VISA e.g. R&S Visa 5.12 or newer
    """
    
    from RsInstrument import *
    
    # A good practice is to assure that you have a certain minimum version installed
    RsInstrument.assert_minimum_version('1.50.0')
    resource_string_1 = 'TCPIP::192.168.2.101::INSTR'  # Standard LAN connection (also called VXI-11)
    resource_string_2 = 'TCPIP::192.168.2.101::hislip0'  # Hi-Speed LAN connection - see 1MA208
    resource_string_3 = 'GPIB::20::INSTR'  # GPIB Connection
    resource_string_4 = 'USB::0x0AAD::0x0119::022019943::INSTR'  # USB-TMC (Test and Measurement Class)
    resource_string_5 = 'RSNRP::0x0095::104015::INSTR'  # R&S Powersensor NRP-Z86
    
    # Initializing the session
    instr = RsInstrument(resource_string_1)
    
    idn = instr.query_str('*IDN?')
    print(f"\nHello, I am: '{idn}'")
    print(f'RsInstrument driver version: {instr.driver_version}')
    print(f'Visa manufacturer: {instr.visa_manufacturer}')
    print(f'Instrument full name: {instr.full_instrument_model_name}')
    print(f'Instrument installed options: {",".join(instr.instrument_options)}')
    
    # Close the session
    instr.close()
