.. _GettingStarted_Logging:

15. Logging
========================================

Yes, the logging again. This one is tailored for instrument communication. You will appreciate such handy feature when you troubleshoot your program, or just want to protocol the SCPI communication for your test reports.

What can you do with the logger?

- Write SCPI communication to a stream-like object, for example console or file, or both simultaneously
- Log only errors and skip problem-free parts; this way you avoid going through thousands lines of texts
- Investigate duration of certain operations to optimize your program's performance
- Log custom messages from your program


The logged information can be sent to these targets (one or more):

- **Console**: this is the most straight-forward target, but it mixes up with other program outputs...
- **Stream**: the most universal one, see the examples below.
- **UDP Port**: if you wish to send it to another program, or a universal UDP listener. This option is used for example by our **Instrument Control Pycharm Plugin** (coming in the near future).

Logging to console
""""""""""""""""""""""""""""""""""""""""""

.. include:: Example_LoggingBasic.py

Console output:

.. code-block:: console

    10:29:10.819     TCPIP::192.168.1.101::INSTR     0.976 ms  Write: *RST
    10:29:10.819     TCPIP::192.168.1.101::INSTR  1884.985 ms  Status check: OK
    10:29:12.704     TCPIP::192.168.1.101::INSTR     0.983 ms  Query OPC: 1
    10:29:12.705     TCPIP::192.168.1.101::INSTR     2.892 ms  Clear status: OK
    10:29:12.708     TCPIP::192.168.1.101::INSTR     3.905 ms  Status check: OK
    10:29:12.712     TCPIP::192.168.1.101::INSTR     1.952 ms  Close: Closing session
    
The columns of the log are aligned for better reading. Columns meaning:

- (1) Start time of the operation
- (2) Device resource name (you can set an alias)
- (3) Duration of the operation
- (4) Log entry

.. tip::
    You can customize the logging format with ``set_format_string()``, and set the maximum log entry length with the properties:
    
    - ``abbreviated_max_len_ascii``
    - ``abbreviated_max_len_bin``
    - ``abbreviated_max_len_list``

    See the full logger help :ref:`here <Logger>`.


Notice the SCPI communication starts from the line ``instr.reset()``. If you want to log the initialization of the session as well, you have to switch the logging ON already in the constructor:

.. code-block:: python

    instr = RsInstrument('TCPIP::192.168.56.101::HISLIP', options='LoggingMode=On')

Logging to files
""""""""""""""""""""""""""""""""""""""""""

Parallel to the console logging, you can log to a general stream. Do not fear the programmer's jargon'... under the term **stream** you can just imagine a file. To be a little more technical, a stream in Python is any object that has two methods: ``write()`` and ``flush()``. This example opens a file and sets it as logging target:

.. include:: Example_LoggingFile.py


Integration with Python's logging module
""""""""""""""""""""""""""""""""""""""""""

Commonly used Python's logging can be used with RsInstrument too:

.. include:: Example_LoggingPythonLogger.py

Logging from multiple sessions
""""""""""""""""""""""""""""""""""""""""""

We hope you are a happy Rohde & Schwarz customer, and hence you use more than one of our instruments. In such case, you probably want to log from all the instruments into a single target (file). Therefore, you open one log file for writing (or appending) and the set is as the logging target for all your sessions:

.. include:: Example_LoggingMultipleSessions.py

Console output:

.. code-block:: console

    11:43:42.657            SMW    10.712 ms  Session init: Device 'TCPIP::192.168.1.101::INSTR' IDN: Rohde&Schwarz,SMW200A,1412.0000K02/0,4.70.026 beta
    11:43:42.668            SMW     2.928 ms  Status check: OK
    11:43:42.686           SMCV     1.952 ms  Session init: Device 'TCPIP::192.168.1.102::INSTR' IDN: Rohde&Schwarz,SMCV100B,1432.7000K02/0,4.70.060.41 beta
    11:43:42.688           SMCV     1.981 ms  Status check: OK
    > Custom log from SMW session
    11:43:42.690            SMW     0.973 ms  Write: *RST
    11:43:42.690            SMW  1874.658 ms  Status check: OK
    11:43:44.565            SMW     0.976 ms  Query OPC: 1
    11:43:44.566            SMW     1.952 ms  Clear status: OK
    11:43:44.568            SMW     2.928 ms  Status check: OK
    > Custom log from SMCV session
    11:43:44.571           SMCV     0.975 ms  Query string: *IDN? Rohde&Schwarz,SMCV100B,1432.7000K02/0,4.70.060.41 beta
    11:43:44.571           SMCV     1.951 ms  Status check: OK
    11:43:44.573            SMW     0.977 ms  Close: Closing session
    11:43:44.574           SMCV     0.976 ms  Close: Closing session

.. tip::
    To make the log more compact, you can skip all the lines with ``Status check: OK``:

    .. code-block:: python

        smw.logger.log_status_check_ok = False

Logging to UDP
""""""""""""""""""""""""""""""""""""""""""

For logging to a UDP port in addition to other log targets, use one of the lines:

.. code-block:: python

    smw.logger.log_to_udp = True
    smw.logger.log_to_console_and_udp = True

You can select the UDP port to log to, the default is 49200:

.. code-block:: python

    smw.logger.udp_port = 49200

Logging from all instances
""""""""""""""""""""""""""""""""""""""""""

In Python everything is an object. Even class definition is an object that can have attributes. Starting with RsInstrument version 1.40.0, we take advantage of that. We introduce the logging target as a class variable (class attribute). The interesting effect of a class variable is, that it has immediate effect for all its instances. Let us rewrite the example above for multiple sessions and use the class variable not only for the log target, but also a relative timestamp, which gives us the log output starting from relative time 00:00:00:000. The created log file will have the same name as the script, but with the extension .ptc (dedicated to those who still worship R&S Forum :-)

.. include:: Example_LoggingMultipleSessionsGlobal.py

Console output and the file content:

.. code-block:: console

    00:00:00.000                  SMW  1107.736 ms  Session init: Device 'TCPIP::192.168.1.101::HISLIP' IDN: Rohde&Schwarz,SMW200A,1412.0000K02/0,4.70.026 beta
    00:00:01.107                  SMW    82.962 ms  Status check: OK
    00:00:01.190                 SMCV   960.414 ms  Session init: Device 'TCPIP::192.168.1.102::HISLIP' IDN: Rohde&Schwarz,SMCV100B,1432.7000K02/0,5.00.122.24
    00:00:02.151                 SMCV    81.994 ms  Status check: OK
    > Custom log entry from SMW session
    00:00:02.233                  SMW    40.989 ms  Write: *RST
    00:00:02.233                  SMW  1910.007 ms  Status check: OK
    00:00:04.143                  SMW    82.013 ms  Query OPC: 1
    00:00:04.225                  SMW   124.933 ms  Clear status: OK
    00:00:04.350                  SMW    81.984 ms  Status check: OK
    > Custom log entry from SMCV session
    00:00:04.432                 SMCV    81.978 ms  Query string: *IDN? Rohde&Schwarz,SMCV100B,1432.7000K02/0,5.00.122.24
    00:00:04.432                 SMCV   163.935 ms  Status check: OK
    00:00:04.595                  SMW   144.479 ms  Close: Closing session
    00:00:04.740                 SMCV   144.457 ms  Close: Closing session
    > SMW execution time: 0:00:03.451152
    > SMCV execution time: 0:00:01.268806


For the completion, here are all the global time functions:

.. code-block:: python

    RsInstrument.set_global_logging_relative_timestamp(timestamp: datetime)
    RsInstrument.get_global_logging_relative_timestamp() -> datetime
    RsInstrument.set_global_logging_relative_timestamp_now()
    RsInstrument.clear_global_logging_relative_timestamp()

and the session-specific time and statistic methods:

.. code-block:: python

    smw.logger.set_relative_timestamp(timestamp: datetime)
    smw.logger.set_relative_timestamp_now()
    smw.logger.get_relative_timestamp() -> datetime
    smw.logger.clear_relative_timestamp()

    smw.get_total_execution_time() -> timedelta
    smw.get_total_time() -> timedelta
    smw.get_total_time_startpoint() -> datetime
    smw.reset_time_statistics()
	
Logging only errors
""""""""""""""""""""""""""""""""""""""""""

Another cool feature is logging only errors. To make this mode useful for troubleshooting, you also want to see the circumstances which lead to the errors. Each RsInstrument elementary operation, for example, ``write_str()``, can generate a group of log entries - let us call them **Segment**. In the logging mode ``Errors``, a whole segment is logged only if at least one entry of the segment is an error.

The script below demonstrates this feature. We deliberately misspelled a SCPI command *CLS, which leads to instrument status error:

.. include:: Example_LoggingError.py

Console output:

.. code-block:: console

    12:11:02.879 TCPIP::192.168.1.101::INSTR     0.976 ms  Write string: *CLaS
    12:11:02.879 TCPIP::192.168.1.101::INSTR     6.833 ms  Status check: StatusException:
                                                 Instrument error detected: Undefined header;*CLaS

Notice the following:

- Although the operation **Write string: *CLaS** finished without an error, it is still logged, because it provides the context for the actual error which occurred during the status checking right after.
- No other log entries are present, including the session initialization and close, because they went error-free.