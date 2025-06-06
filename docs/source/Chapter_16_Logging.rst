.. _GettingStarted_Logging:

Logging
========================================

Yes, the logging again. This one is tailored for instrument communication. You will appreciate such handy feature when you troubleshoot your program, or just want to protocol the SCPI communication for your test reports.

What can you do with the logger?

- Write SCPI communication to a stream-like object, for example console or file, or both simultaneously
- Log only errors and skip problem-free parts; this way you avoid going through thousands lines of texts
- Investigate duration of certain operations to optimize your program's performance
- Log custom messages from your program


The logged information can be sent to these targets (one or multiple):

- **Console**: this is the most straight-forward target, but it mixes up with other program outputs...
- **Stream**: the most universal one, see the examples below.
- **UDP Port**: if you wish to send it to another program, or a universal UDP listener. This option is used for example by our `Instrument Control Pycharm Plugin <https://rsicpycharmplugin.readthedocs.io>`_.

Logging to console
""""""""""""""""""""""""""""""""""""""""""

.. literalinclude:: Example_LoggingBasic.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

    10:29:10.819     TCPIP::192.168.1.101::INSTR     0.976 ms  Write: *RST
    10:29:10.819     TCPIP::192.168.1.101::INSTR  1884.985 ms  Status check: OK
    10:29:12.704     TCPIP::192.168.1.101::INSTR     0.983 ms  Query OPC: 1
    10:29:12.705     TCPIP::192.168.1.101::INSTR     2.892 ms  Clear status: OK
    10:29:12.708     TCPIP::192.168.1.101::INSTR     3.905 ms  Status check: OK
    10:29:12.712     TCPIP::192.168.1.101::INSTR     1.952 ms  Close: Closing session
    
The columns of the log are aligned for better reading. Columns meaning:

(1) Start time of the operation.
(2) Device resource name. You can set an alias.
(3) Duration of the operation.
(4) Log entry.

.. tip::
    You can customize the logging format with ``set_format_string()``, and set the maximum log entry length with these properties:
    
    - ``abbreviated_max_len_ascii``
    - ``abbreviated_max_len_bin``
    - ``abbreviated_max_len_list``

    See the full logger help :ref:`here <Logger>`.


Notice the SCPI communication starts from the line ``instr.reset()``. If you want to log the initialization of the session as well, you have to switch the logging ON already in the constructor:

.. code-block:: python

    instr = RsInstrument('TCPIP::192.168.56.101::hislip0', options='LoggingMode=On')
	
.. note::
    ``instr.logger.start()`` and ``instr.logger.mode = LoggingMode=On`` have the same effect. However, in the constructor's options string, you can only use the ``LoggingMode=On`` format.

Logging to files
""""""""""""""""""""""""""""""""""""""""""

Parallel to the console logging, you can log to a general stream. Do not fear the programmer's jargon'... under the term **stream** you can just imagine a file. To be a little more technical, a stream in Python is any object that has two methods: ``write()`` and ``flush()``. This example opens a file and sets it as logging target:

.. literalinclude:: Example_LoggingFile.py
   :language: python
   :linenos:


Logging with 00:00:00.000 start time
""""""""""""""""""""""""""""""""""""""""""

Very often, you do not need the absolute time in logging, but rather the relative times from the beginning. This way you quickly see the duration of you procedure. To set this up, use the constructor's option string ``LoggingRelativeTimeOfFirstEntry=True`` or the method ``set_time_offset_zero_on_first_entry()``. Another nice feature is time statistic - instrument execution time and total time. These work independent from the fact, whether the logger is running or not:

.. literalinclude:: Example_LoggingRelativeAndStats.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

    00:00:00.000  TCPIP::192.168.1.101::hislip0   137.704 ms  Session init: Device 'TCPIP::192.168.1.101::hislip0' IDN: Rohde&Schwarz,SMA100B,1419.8888K02/0,5.30.132.68
    00:00:00.137  TCPIP::192.168.1.101::hislip0     2.002 ms  Status check: OK
    
    Entries above come from the constructor.
    
    00:00:00.139  TCPIP::192.168.1.101::hislip0     2.922 ms  Query: *IDN? Rohde&Schwarz,SMA100B,1419.8888K02/0,5.30.132.68
    00:00:00.142  TCPIP::192.168.1.101::hislip0     1.510 ms  Status check: OK
    00:00:01.145  TCPIP::192.168.1.101::hislip0    32.979 ms  Write: *RST
    00:00:01.178  TCPIP::192.168.1.101::hislip0  1879.281 ms  Status check: OK
    00:00:03.057  TCPIP::192.168.1.101::hislip0   129.349 ms  Query OPC: 1
    00:00:03.186  TCPIP::192.168.1.101::hislip0     5.432 ms  Clear status: OK
    00:00:03.192  TCPIP::192.168.1.101::hislip0     1.982 ms  Status check: OK
    
    Communication time spent: 0:00:02.191159
    Program time spent:       0:00:03.194408
    
    We can reset the time stats to start from 0 again:
    
    00:00:00.000  TCPIP::192.168.1.101::hislip0    33.615 ms  Status check: OK
    00:00:00.033  TCPIP::192.168.1.101::hislip0     1.952 ms  Close: Closing session
    
    Communication time spent: 0:00:00.001952
    Program time spent:       0:00:00.536126

Integration with Python's logging module
""""""""""""""""""""""""""""""""""""""""""

Commonly used Python's logging can be used with RsInstrument too:

.. literalinclude:: Example_LoggingPythonLogger.py
   :language: python
   :linenos:

Logging from multiple sessions
""""""""""""""""""""""""""""""""""""""""""

We hope you are a happy Rohde & Schwarz customer, and hence you use more than one of our instruments. In such case, you probably want to log from all the instruments into a single target (file). Therefore, you open one log file for writing (or appending) and the set is as the logging target for all your sessions:

.. literalinclude:: Example_LoggingMultipleSessions.py
   :language: python
   :linenos:

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
    11:43:44.571           SMCV     0.975 ms  Query: *IDN? Rohde&Schwarz,SMCV100B,1432.7000K02/0,4.70.060.41 beta
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

In Python everything is an object. Even class definition is an object that can have attributes. We can habe logging target as a class variable (class attribute). The interesting effect of a class variable is, that it has immediate effect on all its instances. Let us rewrite the example above for multiple sessions and use the class variable not only for the log target, but also a relative timestamp, which gives us the log output starting from relative time **00:00:00:000**. The created log file will have the same name as the script, but with the extension .ptc (dedicated to those who still remember R&S Forum :-)

.. literalinclude:: Example_LoggingMultipleSessionsGlobal.py
   :language: python
   :linenos:

Console output and the file content:

.. code-block:: console

	00:00:00.000                            SMW   117.739 ms  Session init: Device 'TCPIP::192.168.1.101::hislip0' IDN: Rohde&Schwarz,SMW200A,1412.0000K02/0,5.30.305.44
	00:00:00.119                            SMW     0.982 ms  Status check: OK
	00:00:00.120                           SMCV    54.835 ms  Session init: Device 'TCPIP::192.168.1.102::hislip0' IDN: Rohde&Schwarz,SMCV100B,1432.7000K02/0,5.30.175.95
	00:00:00.175                           SMCV     0.984 ms  Status check: OK
	> Custom log entry from SMW session
	00:00:00.176                            SMW     0.000 ms  Write: *RST
	00:00:00.176                            SMW  1633.359 ms  Status check: OK
	00:00:01.809                            SMW     7.391 ms  Query OPC: 1
	00:00:01.816                            SMW    10.337 ms  Clear status: OK
	00:00:01.827                            SMW     1.952 ms  Status check: OK
	> Custom log entry from SMCV session
	00:00:01.829                           SMCV    42.493 ms  Query: *IDN? Rohde&Schwarz,SMCV100B,1432.7000K02/0,5.30.175.95
	00:00:01.871                           SMCV     1.953 ms  Status check: OK
	00:00:01.873                            SMW    22.739 ms  Close: Closing session
	00:00:01.896                           SMCV    23.160 ms  Close: Closing session
	> SMW execution time: 0:00:01.793517
	> SMCV execution time: 0:00:00.122441

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

Another neat feature is errors-only logging. To make this mode useful for troubleshooting, you also want to see the circumstances which lead to the errors. Each RsInstrument elementary operation, for example, ``write()``, can generate a group of log entries - let us call them **Segment**. In the logging mode ``Errors``, a whole segment is logged only if at least one entry of the segment is an error.

The script below demonstrates this feature. We deliberately misspelled a SCPI command \*CLS, which leads to instrument status error:

.. literalinclude:: Example_LoggingError.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

    12:11:02.879 TCPIP::192.168.1.101::INSTR     0.976 ms  Write: *CLaS
    12:11:02.879 TCPIP::192.168.1.101::INSTR     6.833 ms  Status check: StatusException:
                                                 Instrument error detected: Undefined header;*CLaS

Notice the following:

- Although the operation **Write: *CLaS** finished without an error, it is still logged, because it provides the context for the actual error which occurred during the status checking right after.
- No other log entries are present, including the session initialization and close, because they ran error-free.

Setting the logging format
""""""""""""""""""""""""""""""""""""""""""
You can adjust the logging to your liking by setting the format string. The default format string:

``PAD_LEFT12(%START_TIME%) PAD_LEFT25(%DEVICE_NAME%) PAD_LEFT12(%DURATION%)  %LOG_STRING_INFO%: %LOG_STRING%``

Here's an example for you minimalists, who only want to see the start, duration, and the SCPI command:

.. literalinclude:: Example_LoggingOnlyScpi.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

	09:31:54.146    40.991 ms *RST
	09:31:54.146  1939.319 ms *STB?
	09:31:56.086    81.984 ms *OPC?
	09:31:56.168   124.930 ms *CLS
	09:31:56.293    82.015 ms *STB?
	09:31:56.375   144.447 ms @CLOSE_SESSION
	
You can also initiate the logging and change its format in the constructor options string.
The console output logs everything including the session intialization commands:

.. literalinclude:: Example_LoggingOnlyScpiFromConstuctor.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

	09:36:47.983  1210.274 ms @INIT_SESSION
	09:36:49.193    81.984 ms *STB?
	09:36:49.275    40.988 ms *RST
	09:36:49.275  1929.529 ms *STB?
	09:36:51.205    82.990 ms *OPC?
	09:36:51.288   124.899 ms *CLS
	09:36:51.413    81.987 ms *STB?
	09:36:51.495   144.480 ms @CLOSE_SESSION

Another possible customization is keeping the %LOG_STRING_INFO%, but replacing its content with your own strings.
Let us make more compact output that way:

.. literalinclude:: Example_LoggingOnlyScpiWithInfoReplacer.py
   :language: python
   :linenos:

Console output:

.. code-block:: console

	12:19:37.025     0.975 ms         W:  *RST
	12:19:37.025  1879.123 ms     Q_err:  *STB?
	12:19:38.905     0.976 ms     Q_OPC:  *OPC?
	12:19:38.906     1.951 ms       Cls:  *CLS
	12:19:38.908     0.000 ms     Q_err:  *STB?
	12:19:38.908     1.007 ms         Q:  *IDN?
	12:19:38.908     1.952 ms     Q_err:  *STB?
	12:19:38.910     1.002 ms Q_integer:  *STB?
	12:19:38.910     1.984 ms     Q_err:  *STB?
	12:19:38.912    23.392 ms     Close:  @CLOSE_SESSION