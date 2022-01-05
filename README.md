RsInstrument module provides convenient way of communicating with R&S instruments.

Check out the full documentation here: https://rsinstrument.readthedocs.io/

Examples: https://github.com/Rohde-Schwarz/Examples/tree/main/Misc/Python/RsInstrument

Version history:

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
        - Fixed calling SYST:ERR? even if *STB? returned 0
        - Replaced @ni backend with @ivi for resource manager - this is necessary for the future pyvisa version 1.12+

    Version 1.13.0.63 (09.06.2021)
        - added methods reconnect(), is_connection_active()

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