5. Basic I/O communication
========================================

Now we have opened the session, it's time to do some work. RsInstrument provides two basic methods for communication:

- ``write_str()`` - writing a command without an answer e.g.: **\*RST**
- ``query_str()`` - querying your instrument, for example with the **\*IDN?** query

Here, you may ask a question... Actually, two questions:

- **Q1**: Why there are not called ``write()`` and ``query()`` ?
- **Q2**: Where is the ``read()`` ?

**A1**: There are - the ``write_str() / write()`` and ``query_str() / query()`` are aliases. We promote the ``_str`` names, to clearly show you want to work with strings. Strings in Python3 are Unicode, the *bytes* and *string* objects are not interchangeable, since one character might be represented by more than 1 byte.
To avoid mixing string and binary communication, all the method names for binary transfer contain ``_bin`` in the name.

**A2**: Short answer - you do not need it. Long answer - your instrument never sends unsolicited responses. If you send a set-command, you use ``write_str()``. For a query-command, you use ``query_str()``. So, you really do not need it...

Enough with the theory, let us look at an example. Basic write, and query:

.. include:: Example_SimpleStringIoUniversity.py

This example is so-called "*University-Professor-Example*" - good to show a principle, but never used in praxis. The previously mentioned commands are already a part of the driver's API. Here is another example, achieving the same goal:

.. include:: Example_SimpleStringIo.py

One additional feature we need to mention here: **VISA timeout**. To simplify, VISA timeout plays a role in each ``query_xxx()``, where the controller (your PC) has to prevent waiting forever for an answer from your instrument. VISA timeout defines that maximum waiting time. You can set/read it with the ``visa_timeout`` property:

.. code-block:: python

    # Timeout in milliseconds
    instr.visa_timeout = 3000

After this time, RsInstrument raises an exception. Speaking of exceptions, an important feature of the RsInstrument is **Instrument Status Checking**. Check out the next chapter that describes the error checking in details.

For completion, we mention other string-based ``write_xxx()`` and ``query_xxx()`` methods, all in one example. They are convenient extensions providing type-safe float/boolean/integer setting/querying features:

.. include:: Example_SimpleStringIoOtherTypes.py

Lastly, a method providing basic synchronization: ``query_opc()``. It sends **\*OPC?** to your instrument. The instrument waits with the answer until all the tasks it currently has in the execution queue are finished. This way your program waits too, and it is synchronized with actions in the instrument. Remember to have the VISA timeout set to an appropriate value to prevent the timeout exception. Here's a snippet:

.. code-block:: python

    instr.visa_timeout = 3000
    instr.write_str("INIT")
    instr.query_opc()
    
    # The results are ready now to fetch
    results = instr.query_str('FETCH:MEASUREMENT?')

You can define the VISA timeout directly in the ``query_opc``, which is valid only for that call. Afterwards, the VISA timeout is set to the previous value:

.. code-block:: python

    instr.write_str("INIT")
    instr.query_opc(3000)

.. tip::
    Wait, there's more: you can send the **\*OPC?** after each ``write_xxx()`` automatically:

    .. code-block:: python

        # Default value after init is False
        instr.opc_query_after_write = True
