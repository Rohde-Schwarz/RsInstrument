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
    
You can also check + clear the errors and raise exception if some errors occurred:

.. code-block:: python

    # Check for errors and raise exception in case of one or more errors
    instr.check_status()

.. _SelectiveStatusErrorSuppression:

Selective Status-Error Suppression
""""""""""""""""""""""""""""""""""""

In special cases, you can configure error suppression rules for the session.
This is useful when your setup produces known, non-critical error messages that can be safely ignored.
The suppression is performed by the driver (client-side): the instrument still reports the error, but once it
matches a suppression rule, the driver filters it out and it never propagates to your application.
Suppressed errors are therefore also excluded from ``query_all_errors()`` and ``query_all_errors_with_codes()``.

You can filter on:

- ``(code, pattern)`` - suppress the error if the error code AND the message match
- ``pattern`` - match by message only (regex), regardless of code
- ``code`` - match only by the error code, the message is not considered

Each ``pattern`` can be a regex string or a compiled ``re.Pattern``.
Message matching uses ``re.search()`` semantics. It means,
it does not have to match the full message string, just a substring of it. Let us look at the snippet below:

.. code-block:: python

    import re

    # Add the suppression rules one by one. Every add_rule() call accepts ONE
    # of the following data types (add_rule() returns the created rule object):

    # 1) (code, regex_string): suppress only if the error CODE equals -113 AND
    #    the message contains the regex (re.search, so a substring match is enough).
    #    This is the rule that suppresses the -113, "Undefined header" error demonstrated below.
    instr.status_error_suppression_add_rule((-113, r"Undefined header"))

    # 2) (code, compiled_pattern): same as above, but the message pattern is a
    #    pre-compiled re.Pattern (here made case-insensitive).
    instr.status_error_suppression_add_rule((-200, re.compile(r"background calibration", re.IGNORECASE)))

    # 3) regex_string: message-only rule - suppress any error whose message
    #    contains this regex, regardless of the error code.
    instr.status_error_suppression_add_rule(r"query interrupted")

    # 4) compiled_pattern: message-only rule using a pre-compiled re.Pattern.
    instr.status_error_suppression_add_rule(re.compile(r"queue overflow", re.IGNORECASE))

    # 5) code (int): code-only rule - suppress any error carrying this code,
    #    regardless of the message text.
    instr.status_error_suppression_add_rule(-222)

    # You can also add several rules at once. The list can mix all the types above:
    instr.status_error_suppression_add_rules([
        (-100, r"Command error"),      # (code, regex string)
        r"self-test.*,",               # string, is compiled to regex pattern, message-only
        re.compile(r"self-test"),      # compiled pattern, message-only
        -410,                          # code-only (int)
    ])

    # add_rule() returns the created rule, which you can later remove selectively:
    rule = instr.status_error_suppression_add_rule(-222)
    instr.status_error_suppression_remove_rule(rule)
    # the rule object also has a remove() method, which does the same:
    rule.remove()

    # Read back the currently active rules (list of normalized rule objects):
    active_rules = instr.status_error_suppression_get_rules()
    # The printed list of the currently active rules looks like this
    # (shown on multiple lines for readability, the real print is one line):
    print(active_rules)
    # print output:
    #     [
    #      InstrumentStatusErrorRule(code=-113, pattern='Undefined header'),
    #      InstrumentStatusErrorRule(code=-200, pattern='background calibration'),
    #      InstrumentStatusErrorRule(pattern='query interrupted'),
    #      InstrumentStatusErrorRule(pattern='queue overflow'),
    #      InstrumentStatusErrorRule(code=-100, pattern='Command error'),
    #      InstrumentStatusErrorRule(pattern='self-test.*,'),
    #      InstrumentStatusErrorRule(pattern='self-test'),
    #      InstrumentStatusErrorRule(code=-410)
    #     ]

    # From now on, only unsuppressed status errors raise StatusException.

    # Non-supported command, would raise exception -113, "Undefined header", but we suppress it.
    instr.write("PRODUCE:UNDEF HEADER")
    # Misspelled command, no exception raised, because the -113, "Undefined header" is suppressed.
    instr.query_str("*IDxN?")

    # Remove one rule if it fits the code:
    # Iterate through the currently active rules and remove the one(s) with code -222.
    # status_error_suppression_get_rules() returns a copy, so it is safe to remove
    # rules while iterating over it.
    for rule in instr.status_error_suppression_get_rules():
        if rule.code == -222:
            rule.remove()  # same effect as instr.status_error_suppression_remove_rule(rule)

    # Remove all rules again - every error is reported from now on:
    instr.status_error_suppression_clear_all_rules()

    # Now the exception is raised again
    instr.query_str("*IDxN?")

See the next chapter on how to react on write/query errors.

Optimized Error Checking
""""""""""""""""""""""""""""""""""""""""""""""""""""

As mentioned at the beginning of this chapter, there is a small performance penalty for checking errors after each command. This might play a bigger role if you are using many commands with short execution time, or repeat some measurement/setting in a loop. To benefit from error checking with minimal performance loss, try to follow this pattern:

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