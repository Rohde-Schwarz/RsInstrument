=============
 RsInstrument
=============

.. image:: https://img.shields.io/pypi/v/rsinstrument.svg
   :target: https://pypi.org/project/RsInstrument/

.. image:: https://readthedocs.org/projects/sphinx/badge/?version=master
   :target: https://rsinstrument.readthedocs.io/

.. image:: https://img.shields.io/pypi/l/rsinstrument.svg
   :target: https://pypi.python.org/pypi/rsinstrument/

.. image:: https://img.shields.io/pypi/pyversions/pybadges.svg
   :target: https://img.shields.io/pypi/pyversions/pybadges.svg

.. image:: https://img.shields.io/pypi/dm/rsinstrument.svg
   :target: https://pypi.python.org/pypi/rsinstrument/

RsInstrument module provides convenient way of communicating with R&S instruments.

Basic Hello-World code:

.. code-block:: python

    from RsInstrument import *

    instr = RsInstrument('TCPIP::192.168.56.101::hislip0', id_query=True, reset=True)
    idn = instr.query_str('*IDN?')
    print('Hello, I am: ' + idn)

Check out the full documentation on `ReadTheDocs <https://rsinstrument.readthedocs.io/>`_.

Our public `Rohde&Schwarz Github repository <https://github.com/Rohde-Schwarz/Examples/tree/main/Misc/Python/RsInstrument>`_ hosts many examples using this library.
If you're looking for examples with specific instruments, check out the ones for
`Oscilloscopes <https://github.com/Rohde-Schwarz/Examples/tree/main/Oscilloscopes/Python/RsInstrument>`_,
`Powersensors <https://github.com/Rohde-Schwarz/Examples/tree/main/Powersensors/Python/RsInstrument>`_,
`Powersupplies <https://github.com/Rohde-Schwarz/Examples/tree/main/Powersupplies/Python/RsInstrument>`_,
`Spectrum Analyzers <https://github.com/Rohde-Schwarz/Examples/tree/main/SpectrumAnalyzers/Python/RsInstrument>`_,
`Vector Network Analyzers <https://github.com/Rohde-Schwarz/Examples/tree/main/VectorNetworkAnalyzers/Python/RsInstrument>`_.


Version history:
----------------
    Version 1.120.1.118 (27.10.2025)
        - Fixed py.typed file name

    Version 1.120.0.117 (20.10.2025)
        - Added MCP server support.
        - Removed support for Python 3.8 and 3.9

    Version 1.110.0.116 (15.10.2025)
        - Added py.typed file to the top package.
        - Added optional parameter mixed_mode to the method go_to_local().
        - Improved help for is_connection_active() method.
        - Core 1.106.0.
        - New package build process with pyproject.toml.

    Version 1.102.1.113 (16.07.2025)
        - Fixed VisaSession's clear_before_read().
        - Core 1.105.1


    Version 1.102.0.112 (02.06.2025)
        - Corrected duplicate time-statistics methods from logger.
        - Improved help.
        - Core 1.105.0

    Version 1.101.0.111 (27.05.2025)
        - Added settings profile 'RadEsT' for R&S Automotive Radar Tester.
        - Added settings 'EachCmdSuffix' settings option - use it for instruments that require CRLF at the end of each command.
        - Added settings 'StripStringTrailingWhitespaces' - use it to strip white spaces from string query responses.
        - Added settings 'LoggingRelativeTimeOfFirstEntry' (boolean) - set it to true to start the logging with 00:00:00.000 relative time.
        - Added check_status() method for checking instrument errors and throwing exception.
        - Added in ScpiLogger: set_time_offset_zero_on_first_entry() - call it to have the next log entry starting with 00:00:00.000 relative time.
        - Core 1.104.0

    Version 1.100.0.110 (09.04.2025)
        - Changed the minimum Python requirement to 3.8 to assure pyvisa version > 1.13.
        - Fixed Logger end time in relative time mode.
        - Fixed bug with InstrErrorSuppressor for checking errors flag after the context has finished.
        - Extended InstrErrorSuppressor to catch queries Timeout as StatusException.
        - Fixes for backend pyvisa-py.
        - Added method get_option_counts() for getting number of a certain K-option occurrences in the original option string.
        - Fixes for Pycharm 2024.3 checks.
        - Core 1.103.0

    Version 1.90.0.108 (07.10.2024)
        - Changed the minimum Python requirement to 3.7 to avoid SCPI Logger Regex error.
        - Fixed VISA Timeout Error generations for NRP sessions.
        - Added Instrument Options methods: has_instr_option(), has_instr_option_regex(), has_instr_option_k0(), add_instr_option(), remove_instr_option()

    Version 1.82.1.106 (13.06.2024)
        - Fixed failing 'import visa' statement for python > 3.10

    Version 1.82.0.105 (07.06.2024)
        - Changes in ScpiLogger:
            - info(), error() - changed the last parameter 'cmd' to optional
            - info_bin(), info_list() - changed the order of the last two parameters!!! 'cmd' moved to the end and made optional, to be compatible with 1.61.0
            - ContextManager VisaTimeoutSuppressor made more robust in case of exceptions inside the other exceptions.

    Version 1.80.0.103 (27.05.2024)
        - Core 1.90.0 with more robust _flush_junk_data() that tolerates read timeouts.
        - Added Logger.log_info_replacer for customizing the logging info strings.
        - Logger info strings 'Write string' and 'Query string' shortened to 'Write' and 'Query'

    Version 1.70.0.102 (26.04.2024)
        - To all query_str_list_xxx() methods, added non-mandatory parameter 'remove_blank_response'.
        - Logger: added new variable to the format string: %SCPI_COMMAND%, where you can only log SCPI commands to your log data.
        - Added Context-managers for ignoring errors and ignoring VISA Timeouts:

            .. code-block:: python

                # Any Instrument error in the context is ignored
                with io.instr_err_suppressor() as supp:
                    io.write("*RSaT")
                if supp.get_errors_occurred():
                    print("Error(s) suppressed")

                # Any Timeout error in the context is ignored
                with io.visa_tout_suppressor(500) as supp:
                    io.write("*IDaN")
                if supp.get_timeout_occurred():
                    print("VISA Timeout suppressed")


        - Added to Utilities interface: query_str_list(), query_str_list_with_opc(), query_bool_list(), query_bool_list_with_opc().
        - Added Utility functions: value_to_si_string(), size_to_kb_mb_gb_string().
        - Changed behaviour of the Conversion functions to list:
            - str_to_float_list()
            - str_to_float_or_bool_list()
            - str_to_int_list()
            - str_to_int_or_bool_list()
            - str_to_bool_list()

            These functions previously returned a list of one element if the input value was whitespace-only string. Now, in such case they return empty list.

    Version 1.61.0.101 (27.02.2024)
        - Added settings profile 'XK41' for R&S Software Defined Radios.
        - Added settings 'FirstCmds' where you can send the defined commands right after the init. Send more commands in a row with ';;' separator.
        - Added settings 'EachCmdPrefix' - this prefix is added to each command sent to the instrument. Supported values are also 'lf', 'cr', 'tab'.

    Version 1.60.0.100 (31.01.2024)
        - Fixed SocketIo session for cases when the instrument connection is lost in the middle of reading a response.
        - Fixed VisaPluginSocketIo read() method for cases where the session is lost. The method now generates exception in that case.
        - Added settings OpcSyncQueryMechanism with changed default value to 'only_check_mav_err_queue'.
        - Added settings 'OpcSyncQueryMechanism' with values: Standard, AlsoCheckMav, ClsOnlyCheckMavErrQueue, OnlyCheckMavErrQueue.

    Version 1.55.0.99 (29.09.2023)
        - Added logger convenient methods start() and stop().
        - Added lock_resource() and unlock_resource() methods for device-site locking.
        - Added Context-manager interface to the RsInstrument class. Now you can use it as follows:

            .. code-block:: python

                with RsInstrument("TCPIP::192.168.1.101::hislip0") as io:
                    io.reset()


    Version 1.54.0.98 (27.06.2023)
        - Added new options profile for ATS chambers.
        - Added settings boolean token EachCmdAsQuery. Example: EachCmdAsQuery=True. Default: False.

    Version 1.53.1.97 (28.03.2023)
        - Fixed decoding custom Status Register bits.

    Version 1.53.0.96 (18.10.2022)
        - Improved mode where the instrument works with a session from another object.
        - Silently ignoring invalid \*IDN? string.
        - Added new options profile 'Minimal' for non-SCPI-99 instruments.

    Version 1.52.0.94 (28.09.2022)
        - Fixed DisableOpcQuery=True settings effect.
        - Increased DataChunkSize from 1E6 to 1E7 bytes.
        - Improved robustness of the TerminationCharacter option value entry.
        - Added new options profile for CMQ500: 'Profile=CMQ'.

    Version 1.51.1.93 (09.09.2022)
        - Fixed go_to_local() / go_to_remote() for VXI-capable sessions.

    Version 1.51.0.92 (08.09.2022)
        - Changed the accepted IDN? response to more permissive.
        - Removed build number from the package version.
        - Added constructor options boolean token VxiCapable. Example: VxiCapable=False. Default: True (coerced later to false based on a session type).
        - Added methods go_to_remote() and go_to_local().
        - Added methods file_exists() and get_file_size().

    Version 1.50.0.90 (23.06.2022)
        - Added relative timestamp to the logger.
        - Added RsInstrument class variables for logging making it possible to define common target and reference timestamp for all instances.
        - Logger stream entries are by default immediately flushed, making sure that the log is complete.
        - Added time statistic methods get_total_execution_time(), get_total_time(), reset_time_statistics().

    Version 1.24.0.83 (03.06.2022)
        - Changed parsing of SYST:ERR? response to tolerate +0,"No Error" response.
        - Added constructor options integer token OpenTimeout. Example: OpenTimeout=5000. Default: 0.
        - Added constructor options boolean token ExclusiveLock. Example: ExclusiveLock=True. Default: False.

    Version 1.23.0.82 (25.05.2022)
        - Added stripping of trailing commas when parsing the idn response.
        - If the Resource Manager does not find any default VISA implementation, it falls back to R&S VISA - relevant for LINUX and MacOS.
        - Other typos and formatting corrections.
        - Changed parsing of SYST:ERR? response to tolerate +0,"No Error" response.

    Version 1.22.0.80 (21.04.2022)
        - Added optional parameter timeout to reset().
        - Added query list methods: query_str_list, query_str_list_with_opc, query_bool_list, query_bool_list_with_opc.
        - Added query_str_stripped for stripping string responses of quotes.

    Version 1.21.0.78 (15.03.2022)
        - Added logging to UDP port (49200) to integrate with new R&S Instrument Control plugin for Pycharm.
        - Improved documentation for logging and Simulation mode sessions.

    Version 1.20.0.76 (19.11.2021)
        - Fixed logging strings when device name was a substring of the resource name.

    Version 1.19.0.75 (08.11.2021)
        - Added setting profile for non-standard instruments. Example of the options string: options='Profile=hm8123'.

    Version 1.18.0.73 (15.10.2021)
        - Added correct conversion of strings with SI suffixes (e.g.: MHz, KHz, THz, GHz, ms, us) to float and integer.

    Version 1.17.0.72 (31.08.2021)
        - Changed default encoding of string<=>bin from utf-8 to charmap.
        - Added settable encoding for the session. Property: RsInstrument.encoding.
        - Fixed logging to console when switched on after init - the cached init entries are now properly flushed and displayed.

    Version 1.16.0.69 (17.07.2021)
        - Improved exception handling in cases where the instrument session is closed.

    Version 1.15.0.68 (12.07.2021)
        - Scpi logger time entries now support not only datetime tuples, but also float timestamps.
        - Added query_all_errors_with_codes() - returning list of tuples (message: str, code: int).
        - Added logger.log_status_check_ok property. This allows for skipping lines with 'Status check: OK'.

    Version 1.14.0.65 (28.06.2021)
        - Added SCPI Logger.
        - Simplified constructor's options string format - removed DriverSetup=() syntax. Instead of "DriverSetup=(TerminationCharacter='\n')", you use "TerminationCharacter='\n'". The original format is still supported.
        - Fixed calling SYST:ERR? even if STB? returned 0.
        - Replaced @ni backend with @ivi for resource manager - this is necessary for the future pyvisa version 1.12+.

    Version 1.13.0.63 (09.06.2021)
        - Added methods reconnect(), is_connection_active().

    Version 1.12.1.60 (01.06.2021)
        - Fixed bug with error checking when events are defined.

    Version 1.12.0.58 (03.05.2021)
        - Changes in Core only.

    Version 1.11.0.57 (18.04.2021)
        - Added aliases for the write_str... and query_str... methods:
            - write() = write_str()
            - query() = query_str()
            - write_with_opc() = write_str_with_opc()
            - query_with_opc() = query_str_with_opc()

    Version 1.9.1.54 (20.01.2021)
        - query_opc() got additional non-mandatory parameter 'timeout'.
        - Code changes only relevant for the auto-generated drivers.

    Version 1.9.0.52 (29.11.2020)
        - Added Thread-locking for sessions. Related new methods: get_lock(), assign_lock(), clear_lock().
        - Added read-only property 'resource_name'.

    Version 1.8.4.49 (13.11.2020)
        - Changed Authors and copyright.
        - Code changes only relevant for the auto-generated drivers.
        - Extended Conversions method str_to_str_list() by parameter 'clear_one_empty_item' with default value False.

    Version 1.8.3.46 (09.11.2020)
        - Fixed parsing of the instrument errors when an error message contains two double quotes.

    Version 1.8.2.45 (21.10.2020)
        - Code changes only relevant for the auto-generated drivers.
        - Added 'UND' to the list of float numbers that are represented as NaN.

    Version 1.8.1.41 (11.10.2020)
        - Fixed Python 3.8.5+ warnings.
        - Extended documentation, added offline installer.
        - Filled package's __init__ file with the exposed API. This simplifies the import statement.

    Version 1.7.0.37 (01.10.2020)
        - Replaced 'import visa' with 'import pyvisa' to remove Python 3.8 pyvisa warnings.
        - Added option to set the termination characters for reading and writing. Until now, it was fixed to '\\n' (Linefeed). Set it in the constructor 'options' string: DriverSetup=(TerminationCharacter = '\\r'). Default value is still '\\n'.
        - Added static method RsInstrument.assert_minimum_version() raising assertion exception if the RsInstrument version does not fulfill at minimum the entered version.
        - Added 'Hameg' to the list of supported instruments.

    Version 1.6.0.32 (21.09.2020)
        - Added documentation on readthedocs.org.
        - Code changes only relevant for the auto-generated drivers.

    Version 1.5.0.30 (17.09.2020)
        - Added recognition of RsVisa library location for linux when using options string 'SelectVisa=rs'.
        - Fixed bug in reading binary data 16 bit.

    Version 1.4.0.29 (04.09.2020)
        - Fixed error for instruments that do not support \*OPT? query.

    Version 1.3.0.28 (18.08.2020)
        - Implemented SocketIO plugin which allows the remote-control without any VISA installation.
        - Implemented finding resources as a static method of the RsInstrument class.

    Version 1.2.0.25 (03.08.2020)
        - Fixed reading of long strings for NRP-Zxx sessions.

    Version 1.1.0.24 (16.06.2020)
        - Fixed simulation mode switching.
        - Added Repeated capability.

    Version 1.0.0.21
        - First released version.