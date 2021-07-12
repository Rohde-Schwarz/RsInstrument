.. code-block:: python

    """
    Event handlers by reading
    """
    
    from RsInstrument import *
    import time
    
    
    def my_transfer_handler(args):
        """Function called each time a chunk of data is transferred"""
        # Total size is not always known at the beginning of the transfer
        total_size = args.total_size if args.total_size is not None else "unknown"
    
        print(f"Context: '{args.context}{'with opc' if args.opc_sync else ''}', "
                f"chunk {args.chunk_ix}, "
                f"transferred {args.transferred_size} bytes, "
                f"total size {total_size}, "
                f"direction {'reading' if args.reading else 'writing'}, "
                f"data '{args.data}'")
    
        if args.end_of_transfer:
            print('End of Transfer')
        time.sleep(0.2)
    
    
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, True)
    
    instr.events.on_read_handler = my_transfer_handler
    # Switch on the data to be included in the event arguments
    # The event arguments args.data will be updated
    instr.events.io_events_include_data = True
    # Set data chunk size to 2 bytes
    instr.data_chunk_size = 2
    instr.query_str('*IDN?')
    # Unregister the event handler
    instr.events.on_read_handler = None
    
    # Close the session
    instr.close()
