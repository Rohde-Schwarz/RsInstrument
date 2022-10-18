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

    instr = RsInstrument('TCPIP::192.168.56.101::HISLIP', id_query=True, reset=True)
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

    Version 1.53.0.96 (18.10.2022)
        - Improved mode where the instrument works with a session from another object.
        - Silently ignoring invalid \*IDN? string.
        - Added new options profile 'Minimal' for non-SCPI-99 instruments.

    Version 1.52.0.94 (28.09.2022)
        - Fixed DisableOpcQuery=True settings effect.
        - Increased DataChunkSize from 1E6 to 1E7 bytes.
        - Improved robustness of the TerminationCharacter option value entry.
        - Added new options profile for CMQ500: 'Profile=CMQ'

    Version 1.51.1.93 (09.09.2022)
        - Fixed go_to_local() / go_to_remote() for VXI-capable sessions.

    Version 1.51.0.92 (08.09.2022)
        - Changed the accepted IDN? response to more permissive.
        - Removed build number from the package version.
        - Added constructor options boolean token VxiCapable. Example: VxiCapable=False. Default: True (coerced later to false based on a session type)
        - added methods go_to_remote() and go_to_local()
        - added methods file_exists() and get_file_size()

    Version 1.50.0.90 (23.06.2022)
        - Added relative timestamp to the logger.
        - Added RsInstrument class variables for logging making it possible to define common target and reference timestamp for all instances.
        - Logger stream entries are by default immediately flushed, making sure that the log is complete.
        - Added time statistic methods get_total_execution_time(), get_total_time(), reset_time_statistics().

    Version 1.24.0.83 (03.06.2022)
        - Changed parsing of SYST:ERR? response to tolerate +0,"No Error" response.
        - Added constructor options integer token OpenTimeout. Example: OpenTimeout=5000. Default: 0
        - Added constructor options boolean token ExclusiveLock. Example: ExclusiveLock=True. Default: False

    Version 1.23.0.82 (25.05.2022)
        - Added stripping of trailing commas when parsing the idn response.
        - If the Resource Manager does not find any default VISA implementation, it falls back to R&S VISA - relevant for LINUX and MacOS
        - Other typos and formatting corrections.
        - Changed parsing of SYST:ERR? response to tolerate +0,"No Error" response.

    Version 1.22.0.80 (21.04.2022)
        - Added optional parameter timeout to reset()
        - Added query list methods: query_str_list, query_str_list_with_opc, query_bool_list, query_bool_list_with_opc
        - Added query_str_stripped for stripping string responses of quotes.

    Version 1.21.0.78 (15.03.2022)
        - Added logging to UDP port (49200) to integrate with new R&S Instrument Control plugin for Pycharm
        - Improved documentation for logging and Simulation mode sessions.
    
    Version 1.20.0.76 (19.11.2021)
        - Fixed logging strings when device name was a substring of the resource name

    Version 1.19.0.75 (08.11.2021)
        - Added setting profile for non-standard instruments. Example of the options string: options='Profile=hm8123'

    Version 1.18.0.73 (15.10.2021)
        - Added correct conversion of strings with SI suffixes (e.g.: MHz, KHz, THz, GHz, ms, us) to float and integer

    Version 1.17.0.72 (31.08.2021)
        - Changed default encoding of string<=>bin from utf-8 to charmap.
        - Added settable encoding for the session. Property: RsInstrument.encoding
        - Fixed logging to console when switched on after init - the cached init entries are now properly flushed and displayed.

    Version 1.16.0.69 (17.07.2021)
        - Improved exception handling in cases where the instrument session is closed.

    Version 1.15.0.68 (12.07.2021)
        - Scpi logger time entries now support not only datetime tuples, but also float timestamps
        - Added query_all_errors_with_codes() - returning list of tuples (message: str, code: int)
        - Added logger.log_status_check_ok property. This allows for skipping lines with 'Status check: OK'

    Version 1.14.0.65 (28.06.2021)
        - Added SCPI Logger
        - Simplified constructor's options string format - removed DriverSetup=() syntax. Instead of "DriverSetup=(TerminationCharacter='\n')", you use "TerminationCharacter='\n'". The original format is still supported.
        - Fixed calling SYST:ERR? even if STB? returned 0
        - Replaced @ni backend with @ivi for resource manager - this is necessary for the future pyvisa version 1.12+

    Version 1.13.0.63 (09.06.2021)
        - Added methods reconnect(), is_connection_active()

    Version 1.12.1.60 (01.06.2021)
        - Fixed bug with error checking when events are defined

    Version 1.12.0.58 (03.05.2021)
        - Changes in Core only

    Version 1.11.0.57 (18.04.2021)
        - Added aliases for the write_str... and query_str... methods:
        - write() = write_str()
        - query() = query_str()
        - write_with_opc() = write_str_with_opc()
        - query_with_opc() = query_str_with_opc()

    Version 1.9.1.54 (20.01.2021)
        - query_opc() got additional non-mandatory parameter 'timeout'
        - Code changes only relevant for the auto-generated drivers

    Version 1.9.0.52 (29.11.2020)
        - Added Thread-locking for sessions. Related new methods: get_lock(), assign_lock(), clear_lock()
        - Added read-only property 'resource_name'

    Version 1.8.4.49 (13.11.2020)
        - Changed Authors and copyright
        - Code changes only relevant for the auto-generated drivers
        - Extended Conversions method str_to_str_list() by parameter 'clear_one_empty_item' with default value False

    Version 1.8.3.46 (09.11.2020)
        - Fixed parsing of the instrument errors when an error message contains two double quotes

    Version 1.8.2.45 (21.10.2020)
        - Code changes only relevant for the auto-generated drivers
        - Added 'UND' to the list of float numbers that are represented as NaN

    Version 1.8.1.41 (11.10.2020)
        - Fixed Python 3.8.5+ warnings
        - Extended documentation, added offline installer
        - Filled package's __init__ file with the exposed API. This simplifies the import statement
	
    Version 1.7.0.37 (01.10.2020)
        - Replaced 'import visa' with 'import pyvisa' to remove Python 3.8 pyvisa warnings
        - Added option to set the termination characters for reading and writing. Until now, it was fixed to '\\n' (Linefeed). Set it in the constructor 'options' string: DriverSetup=(TerminationCharacter = '\\r'). Default value is still '\\n'
        - Added static method RsInstrument.assert_minimum_version() raising assertion exception if the RsInstrument version does not fulfill at minimum the entered version
        - Added 'Hameg' to the list of supported instruments

    Version 1.6.0.32 (21.09.2020)
        - Added documentation on readthedocs.org
        - Code changes only relevant for the auto-generated drivers

    Version 1.5.0.30 (17.09.2020)
        - Added recognition of RsVisa library location for linux when using options string 'SelectVisa=rs'
        - Fixed bug in reading binary data 16 bit

    Version 1.4.0.29 (04.09.2020)
        - Fixed error for instruments that do not support \*OPT? query

    Version 1.3.0.28 (18.08.2020)
        - Implemented SocketIO plugin which allows the remote-control without any VISA installation
        - Implemented finding resources as a static method of the RsInstrument class

    Version 1.2.0.25 (03.08.2020)
        - Fixed reading of long strings for NRP-Zxx sessions

    Version 1.1.0.24 (16.06.2020)
        - Fixed simulation mode switching
        - Added Repeated capability

    Version 1.0.0.21
        - First released version