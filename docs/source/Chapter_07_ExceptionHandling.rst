7. Exception Handling
========================================
The base class for all the exceptions raised by the RsInstrument is ``RsInstrException``. Inherited exception classes:

- ``ResourceError`` raised in the constructor by problems with initiating the instrument, for example wrong or non-existing resource name
- ``StatusException`` raised if a command or a query generated error in the instrument's error queue
- ``TimeoutException`` raised if a visa timeout or an opc timeout is reached

In this example we show usage of all of them:

.. include:: Example_Exceptions.py

.. tip::
    General rules for exception handling:

    - If you are sending commands that might generate errors in the instrument, for example deleting a file which does not exist, use the **OPTION 1** - temporarily disable status checking, send the command, clear the error queue and enable the status checking again.
    - If you are sending queries that might generate errors or timeouts, for example querying measurement that cannot be performed at the moment, use the **OPTION 2** - try/except with optionally adjusting timeouts.