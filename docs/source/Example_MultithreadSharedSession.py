.. code-block:: python

    """
    Multiple threads are accessing two RsInstrument objects with shared session
    """
    
    import threading
    from RsInstrument import *
    
    
    def execute(session: RsInstrument, session_ix, index) -> None:
        """Executed in a separate thread."""
        print(f'{index} session {session_ix} query start...')
        session.query_str('*IDN?')
        print(f'{index} session {session_ix} query end')
    
    
    # Make sure you have the RsInstrument version 1.50.0 and newer
    RsInstrument.assert_minimum_version('1.50.0')
    instr1 = RsInstrument('TCPIP::192.168.56.101::INSTR')
    instr2 = RsInstrument.from_existing_session(instr1)
    instr1.visa_timeout = 200
    instr2.visa_timeout = 200
    # To see the effect of crosstalk, uncomment this line
    # instr2.clear_lock()
    
    threads = []
    for i in range(10):
        t = threading.Thread(target=execute, args=(instr1, 1, i,))
        t.start()
        threads.append(t)
        t = threading.Thread(target=execute, args=(instr2, 2, i,))
        t.start()
        threads.append(t)
    print('All threads started')
    
    # Wait for all threads to join this main thread
    for t in threads:
        t.join()
    print('All threads ended')
    
    instr2.close()
    instr1.close()
