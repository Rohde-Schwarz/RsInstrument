Universal I/O Execution
========================================

So far we picked ``write()`` or ``query()`` ourselves. Sometimes you just have a SCPI string
(from a script, a GUI, or a migration of an old remote-control sequence) and want the driver
to choose the right I/O method for you. That is what ``execute()`` does.

It strips surrounding whitespace from the command string and routes it to one of:

- ``write()`` / ``query()`` - for plain commands
- ``write_with_opc()`` / ``query_with_opc()`` - when an OPC synchronization suffix is detected

The return value follows the same rule as the underlying call: a response ``str`` for queries,
``None`` for writes. Detection of a query vs. write is based on whether the command that is
actually sent contains ``?``.

**OPC synchronization suffix** (controlled by ``optimize_opc_execute``, default ``False``):

- ``optimize_opc_execute = False`` (default): a trailing ``;*OPC`` requests OPC-synchronized
  execution and is stripped from the command. A trailing ``;*OPC?`` is kept, and the whole
  string is sent as an ordinary query.
- ``optimize_opc_execute = True``: both ``;*OPC`` and ``;*OPC?`` request OPC-synchronized
  execution; the suffix is stripped, and the base command is run with ``_with_opc``.

You can also set the flag at construction time with the ``OptimizeOpcExecute`` option token:

.. code-block:: python

    # Same effect as instr.optimize_opc_execute = True after init
    instr = RsInstrument('TCPIP::192.168.56.101::INSTR', True, False, 'OptimizeOpcExecute=True')

A few concrete mappings with the default ``optimize_opc_execute = False``:

.. code-block:: python

    instr.execute('*IDN?')                    # -> query('*IDN?')                -> str
    instr.execute('*RST')                     # -> write('*RST')                 -> None
    instr.execute('INIT;*OPC')                # -> write_with_opc('INIT')        -> None
    instr.execute('READ:MEAS?;*OPC')          # -> query_with_opc('READ:MEAS?')  -> str
    instr.execute('READ:MEAS?;*OPC?')         # -> query('READ:MEAS?;*OPC?')     -> str

And the same last line with optimization enabled:

.. code-block:: python

    instr.optimize_opc_execute = True
    instr.execute('READ:MEAS?;*OPC?')         # -> query_with_opc('READ:MEAS?')  -> str

Here is a complete example putting it together:

.. literalinclude:: Example_Execute.py
   :language: python
   :linenos:

.. note::
    ``execute()`` is a convenience dispatcher. For new code where you already know whether
    you write or query, prefer the dedicated ``write()`` / ``query()`` (or ``_with_opc``)
    methods - they make the intent clearer. Reach for ``execute()`` when the SCPI string
    arrives dynamically, or when you migrate scripts that append ``;*OPC`` / ``;*OPC?``.
