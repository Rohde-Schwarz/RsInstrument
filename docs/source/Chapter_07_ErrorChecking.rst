Error Checking
========================================
RsInstrument has a built-in mechanism that after each command/query checks the instrument's status subsystem, and raises an exception if it detects an error. For those who are already screaming: **Speed Performance Penalty!!!**, don't worry, you can disable it.

Instrument status checking is very useful since in case your command/query caused an error, you are immediately informed about it. Status checking has in most cases no practical effect on the speed performance of your program. However, if for example, you do many repetitions of short write/query sequences, it might make a difference to switch it off:

.. code-block:: python

    # Default value after init is True
    instr.instrument_status_checking = False

To clear the instrument status subsystem of all errors, call this method:

.. code-block:: python

    # Clear all the errors in the error queue
	instr.clear_status()

Instrument's status system error queue is clear-on-read. It means, if you query its content, you clear it at the same time. To query and clear list of all the current errors, use the following:

.. code-block:: python

    # Query all the errors in the error queue
	errors_list = instr.query_all_errors()
    
You can also check + clear the errors and raise exception if some errors occured:

.. code-block:: python

    # Check for errors and raise exception in case of one or more errors
    instr.check_status()

See the next chapter on how to react on write/query errors.

Optimized Error Checking
""""""""""""""""""""""""""""""""""""""""""""""""""""

As mentioned at the beginning of this chapter, there is a small performance penalty for checking errors after each command. This might play a bigger role if you are using many commands with short execution time, or repeat some measurement/setting in a loop. To benefit from error checking with minimal performance loss,try to follow this pattern:

	- Keep the status checking ON for single, key commands.
	- Switch the status checking OFF before a group of commands that logically belong together.
	- Perform a group of write/query commands, for example a common configuration of a spectrum analyzer.
	- After that, call ``check_status()``. This method raises the ``StatusException`` (see Exceptions Handling Chapter below) if there are any errors in the error queue.
	- Perform many SCPI write/query call in a loop.
	- After the loop ends, perform ``check_status()`` again.
	
Let us see this in a practical example. Notice the emphasized lines 24, 31 and 45:

.. literalinclude:: Example_ErrorCheckingOptimized.py
   :language: python
   :emphasize-lines: 24,31,45
   :linenos: