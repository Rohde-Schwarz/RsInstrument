Error Checking
========================================
RsInstrument has a built-in mechanism that after each command/query checks the instrument's status subsystem, and raises an exception if it detects an error. For those who are already screaming: **Speed Performance Penalty!!!**, don't worry, you can disable it.

Instrument status checking is very useful since in case your command/query caused an error, you are immediately informed about it. Status checking has in most cases no practical effect on the speed performance of your program. However, if for example, you do many repetitions of short write/query sequences, it might make a difference to switch it off:

.. code-block:: python

    # Default value after init is True
    instr.instrument_status_checking = False

To clear the instrument status subsystem of all errors, call this method:

.. code-block:: python

    instr.clear_status()

Instrument's status system error queue is clear-on-read. It means, if you query its content, you clear it at the same time. To query and clear list of all the current errors, use the following:

.. code-block:: python

    errors_list = instr.query_all_errors()

See the next chapter on how to react on write/query errors.