.. code-block:: python

    """
    Multiple threads are accessing one RsInstrument object
    """
    
    import threading
    from RsInstrument import *
    
    
    def execute(session: RsInstrument) -> None:
        """Executed in a separate thread."""
        session.query_str('*IDN?')
    
    
    # Make sure you have the RsInstrument version 1.9.0 and newer
    RsInstrument.assert_minimum_version('1.9.0')
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR')
    threads = []
    for i in range(10):
        t = threading.Thread(target=execute, args=(instr, ))
        t.start()
        threads.append(t)
    print('All threads started')
    
    # Wait for all threads to join this main thread
    for t in threads:
        t.join()
    print('All threads ended')
    
    instr.close()
