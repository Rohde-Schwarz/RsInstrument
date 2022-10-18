.. code-block:: python

    """
    Querying ASCII and binary integer arrays
    """
    
    from RsInstrument import *
    from time import time
    
    rto = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    # Initiate a single acquisition and wait for it to finish
    rto.write_str_with_opc("SINGle", 20000)
    
    # Query array of integers in ASCII format
    t = time()
    waveform = rto.query_bin_or_ascii_int_list('FORM ASC;:CHAN1:DATA?')
    print(f'Instrument returned {len(waveform)} points in ASCII format, query duration {time() - t:.3f} secs')
    
    
    # Query array of integers in Binary format
    t = time()
    # This tells the RsInstrument in which format to expect the binary integer data
    rto.bin_int_numbers_format = BinIntFormat.Integer32_4bytes
    # If your instrument sends the data with the swapped endianness, use the following format:
    # rto.bin_int_numbers_format = BinIntFormat.Integer32_4bytes_swapped
    waveform = rto.query_bin_or_ascii_int_list('FORM INT,32;:CHAN1:DATA?')
    print(f'Instrument returned {len(waveform)} points in binary format, query duration {time() - t:.3f} secs')
    
    # Close the rto session
    rto.close()
