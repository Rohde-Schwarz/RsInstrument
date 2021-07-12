.. code-block:: python

    """
    Querying binary float arrays
    """
    
    from RsInstrument import *
    from time import time
    
    rto = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    # Initiate a single acquisition and wait for it to finish
    rto.write_str_with_opc("SINGle", 20000)
    
    # Query array of floats in Binary format
    t = time()
    # This tells the RsInstrument in which format to expect the binary float data
    rto.bin_float_numbers_format = BinFloatFormat.Single_4bytes
    # If your instrument sends the data with the swapped endianness, use the following format:
    # rto.bin_float_numbers_format = BinFloatFormat.Single_4bytes_swapped
    waveform = rto.query_bin_or_ascii_float_list('FORM REAL,32;:CHAN1:DATA?')
    print(f'Instrument returned {len(waveform)} points, query duration {time() - t:.3f} secs')
    
    # Close the RTO session
    rto.close()
