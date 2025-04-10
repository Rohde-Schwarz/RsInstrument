"""Root class for remote-controlling instrument with SCPI commands."""

import threading
from typing import List, Tuple, ClassVar
from datetime import datetime, timedelta

from .Fixed_Files.Events import Events
from .Internal.Core import Core
from .Internal.Conversions import BinFloatFormat, BinIntFormat
from RsInstrument.Internal.InstrumentSettings import OpcSyncQueryMechanism
from .Internal import Conversions as Conv
from .Internal.VisaSession import VisaSession
from .Internal.ScpiLogger import ScpiLogger
from .Internal.Utilities import trim_str_response
from .Internal.GlobalData import GlobalData
from .Internal.ContextManagers import InstrErrorSuppressor, VisaTimeoutSuppressor


class RsInstrument:
	"""Root class for remote-controlling instrument with SCPI commands."""
	_driver_version_const = '1.100.0.110'
	_driver_options_const = "SupportedInstrModels = All Rohde & Schwarz Instruments, SupportedIdnPatterns = Rohde\\s*(-|&)\\s*Schwarz/Hameg, SimulationIdnString = Rohde&Schwarz*SimulationDevice*100001*" + _driver_version_const
	_global_logging_relative_timestamp: ClassVar[datetime] = None
	_global_logging_target_stream: ClassVar = None

	def __init__(
			self, resource_name: str, id_query: bool = True, reset: bool = False, options: str = None, direct_session: object = None):
		"""Initializes new RsInstrument session. \n

		:param resource_name: VISA resource name, e.g. 'TCPIP::192.168.2.1::INSTR'
		:param id_query: if True, the instrument's model name is verified against the models supported by the driver and eventually throws an exception
		:param reset: Resets the instrument (sends *RST) command and clears its status syb-system
		:param direct_session: Another driver object or pyVisa object to reuse the session instead of opening a new session
		:param options: string tokens alternating the driver settings

		Parameter options tokens examples:
			- ``Simulate=True`` - starts the session in simulation mode. Default: ``False``
			- ``SelectVisa=socketio`` - uses no VISA implementation for socket connections - you do not need any VISA-C installation
			- ``SelectVisa=rs`` - forces usage of RohdeSchwarz Visa
			- ``SelectVisa=ni`` - forces usage of National Instruments Visa
			- ``Profile = HM8123`` - setting profile fitting the specific non-standard instruments. Available values: HM8123, CMQ, ATS, Minimal. Default: ``none``
			- ``OpenTimeout=5000`` - sets timeout used at the session opening. This timeout is only used in waiting for a locked session to be freed. Default: ``2000ms``
			- ``ExclusiveLock=True`` - opens the session with exclusive lock on the VISA level. Default: ``False``
			- ``QueryInstrumentStatus = False`` - same as ``driver.utilities.instrument_status_checking = False``. Default: ``True``
			- ``WriteDelay = 20, ReadDelay = 5`` - introduces delay of 20ms before each write and 5ms before each read. Default: ``0ms`` for both
			- ``TerminationCharacter = "\\r"`` - sets the termination character for reading. Default: ``\\n`` (LineFeed or LF)
			- ``AssureWriteWithTermChar = True`` - makes sure each command/query is terminated with termination character. Default: Interface dependent
			- ``AddTermCharToWriteBinBlock = True`` - adds one additional LF to the end of the binary data (some instruments require that). Default: ``False``
			- ``DataChunkSize = 10E3`` - maximum size of one write/read segment. If transferred data is bigger, it is split to more segments. Default: ``1E7`` bytes
			- ``OpcTimeout = 10000`` - same as driver.utilities.opc_timeout = 10000. Default: ``30000ms``
			- ``VisaTimeout = 5000`` - same as driver.utilities.visa_timeout = 5000. Default: ``10000ms``
			- ``ViClearExeMode = Disabled`` - viClear() execution mode. Default: ``execute_on_all``
			- ``OpcQueryAfterWrite = True`` - same as driver.utilities.opc_query_after_write = True. Default: ``False``
			- ``OpcWaitMode = OpcQuery`` - mode for all the opc-synchronised write/reads. Other modes: StbPolling, StbPollingSlow, StbPollingSuperSlow. Default: ``StbPolling``
			- ``StbInErrorCheck = False`` - if true, the driver checks errors with *STB? If false, it uses SYST:ERR?. Default: ``True``
			- ``SkipStatusSystemSettings = False`` - some instruments do not support full status system commands. In such case, set this value to True. Default: ``False``
			- ``SkipClearStatus = True`` - set to True for instruments that do not support *CLS command. Default: ``False``
			- ``DisableOpcQuery = True`` - set to True for instruments that do not support *OPC? query. Default: ``False``
			- ``EachCmdAsQuery = True``, set to True, for instruments that always return answer. Default: ``false``
			- ``CmdIdn = ID?`` - defines which SCPI command to use for identification query. Use '<none>' string to skip identification query at the init. Default: ``*IDN?``
			- ``CmdReset = RT`` - defines which SCPI command to use for reset. Default: ``*RST``
			- ``VxiCapable = false`` - you can force a session to a VXI-incapable. Default: <interface-dependent>
			- ``Encoding = utf-8`` - setting of encoding for strings into bytes and vice versa. Default: ``charmap``
			- ``OpcSyncQueryMechanism = AlsoCheckMav`` - setting of mechanism for OPC-synchronised queries. Default: ``OnlyCheckMavErrQueue``
			- ``FirstCmds = *CLS`` - first command(s) to sent after init. Separated more commands/queries with ';;'. Default: ````
			- ``EachCmdPrefix = lf`` - this prefix is added to each command sent to the instrument. Default: ````
			- ``LoggingMode = On`` - sets the logging status right from the start. Possible values: On | Off | Error. Default: ``Off``
			- ``LoggingName = 'MyDevice'`` - sets the name to represent the session in the log entries. Default: ``<resource_name>``
			- ``LoggingFormat = 'PAD_LEFT12(%START_TIME%) PAD_LEFT25(%DEVICE_NAME%) PAD_LEFT12(%DURATION%) %SCPI_COMMAND%'`` - sets the format of the log entries. Default: ``PAD_LEFT12(%START_TIME%) PAD_LEFT25(%DEVICE_NAME%) PAD_LEFT12(%DURATION%)  %LOG_STRING_INFO%: %LOG_STRING%``
			- ``LogToGlobalTarget = True`` - sets the logging target to the class-property previously set with RsInstrument.set_global_logging_target() Default: ``False``
			- ``LoggingToConsole = True`` - immediately starts logging to the console. Default: False
			- ``LoggingToUdp = True`` - immediately starts logging to the UDP port. Default: False
			- ``LoggingUdpPort = 49200`` - UDP port to log to. Default: 49200
"""

		GlobalData.bounded_class = RsInstrument
		self._core = Core(
			resource_name,
			id_query,
			reset,
			driver_options=RsInstrument._driver_options_const,
			user_options=options,
			direct_session=direct_session,
			called_from_driver=False)
		self._core.driver_version = RsInstrument._driver_version_const
		# Custom interfaces
		self._events = Events(self._core)

	@classmethod
	def from_existing_session(cls, session: object, options: str = None) -> 'RsInstrument':
		"""Creates a new RsInstrument object with the entered 'session' reused.
		:param session: can be another driver or a direct pyvisa session
		:param options: string tokens alternating the driver settings"""
		GlobalData.bounded_class = RsInstrument
		resource_name = None
		if hasattr(session, 'resource_name'):
			resource_name = getattr(session, 'resource_name')
		# noinspection PyTypeChecker
		return cls(resource_name, False, False, options, session)

	@classmethod
	def set_global_logging_target(cls, target) -> None:
		"""Sets global common target stream that each instance can use. To use it, call the following: io.logger.set_logging_target_global().
		If an instance uses global logging target, it automatically uses the global relative timestamp (if set).
		You can set the target to None to invalidate it."""
		cls._global_logging_target_stream = target

	@classmethod
	def get_global_logging_target(cls):
		"""Returns global common target stream."""
		return cls._global_logging_target_stream

	@classmethod
	def set_global_logging_relative_timestamp(cls, timestamp: datetime) -> None:
		"""Sets global common relative timestamp for log entries. To use it, call the following: io.logger.set_relative_timestamp_global()"""
		cls._global_logging_relative_timestamp = timestamp

	@classmethod
	def set_global_logging_relative_timestamp_now(cls) -> None:
		"""Sets global common relative timestamp for log entries to this moment.
		To use it, call the following: io.logger.set_relative_timestamp_global()."""
		cls._global_logging_relative_timestamp = datetime.now()

	@classmethod
	def clear_global_logging_relative_timestamp(cls) -> None:
		"""Clears the global relative timestamp. After this, all the instances using the global relative timestamp continue logging with the absolute timestamps."""
		# noinspection PyTypeChecker
		cls._global_logging_relative_timestamp = None

	@classmethod
	def get_global_logging_relative_timestamp(cls) -> datetime or None:
		"""Returns global common relative timestamp for log entries."""
		return cls._global_logging_relative_timestamp

	def __str__(self):
		"""String representation of the object."""
		if self._core.io:
			return f"RsInstrument session '{self._core.io.resource_name}'"
		else:
			return f"RsInstrument with session closed"

	def __enter__(self) -> 'RsInstrument':
		"""Stuff to do when entering the context.
		Currently, this method does nothing, and returns the RsInstrument object."""
		return self

	def __exit__(self, exc_type, value, traceback):
		"""Stuff to do when leaving the context.
		Closes the opened session."""
		self.close()

	def close(self) -> None:
		"""Closes the active RsInstrument session"""
		self._core.io.close()

	@staticmethod
	def list_resources(expression: str = '?*::INSTR', visa_select: str = None) -> List[str]:
		"""Finds all the resources defined by the expression.

		* '?*' - matches all the available instruments
		* 'USB::?*' - matches all the USB instruments
		* 'TCPIP::192?*' - matches all the LAN instruments with the IP address starting with 192

		:param expression: see the examples in the function
		:param visa_select: optional parameter selecting a specific VISA. Examples: '@ivi', '@rs'
		"""
		rm = VisaSession.get_resource_manager(visa_select)
		resources = rm.list_resources(expression)
		rm.close()
		# noinspection PyTypeChecker
		return resources

	def get_session_handle(self):
		"""Returns the underlying pyvisa session"""
		return self._core.get_session_handle()

	@property
	def events(self) -> Events:
		"""Interface for event handlers, see :ref:`here <Events>` """
		return self._events

	@property
	def logger(self) -> ScpiLogger:
		"""Scpi Logger interface, see :ref:`here <Logger>` """
		return self._core.io.logger

	# Utilities part follows - copy it manually from the Utilities.py file
	@property
	def driver_version(self) -> str:
		"""Returns the instrument driver version"""
		return self._core.driver_version

	@property
	def idn_string(self) -> str:
		"""Returns instrument's identification string - the response on the SCPI command *IDN?"""
		return self._core.io.idn_string

	@idn_string.setter
	def idn_string(self, idn_string: str) -> None:
		"""Sets instrument's identification string - the response on the SCPI command *IDN?"""
		self._core.io.idn_string = idn_string

	@property
	def manufacturer(self) -> str:
		"""Returns manufacturer of the instrument"""
		return self._core.io.manufacturer

	@property
	def full_instrument_model_name(self) -> str:
		"""Returns the current instrument's full name e.g. 'FSW26'"""
		return self._core.io.full_model_name

	@property
	def instrument_model_name(self) -> str:
		"""Returns the current instrument's family name e.g. 'FSW'"""
		return self._core.io.model

	@property
	def supported_models(self) -> List[str]:
		"""Returns a list of the instrument models supported by this instrument driver"""
		return self._core.supported_instr_models

	@property
	def instrument_firmware_version(self) -> str:
		"""Returns instrument's firmware version"""
		return self._core.io.firmware_version

	@property
	def instrument_serial_number(self) -> str:
		"""Returns instrument's serial_number"""
		return self._core.io.serial_number

	def query_opc(self, timeout: int = 0) -> int:
		"""SCPI command: *OPC?
		Queries the instrument's OPC bit and hence it waits until the instrument reports operation complete.
		If you define timeout > 0, the VISA timeout is set to that value just for this method call."""
		return self._core.io.query_opc(timeout)

	@property
	def instrument_status_checking(self) -> bool:
		"""Sets / returns Instrument Status Checking.
		When True (default is True), all the driver methods and properties are sending "SYSTem:ERRor?"
		at the end to immediately react on error that might have occurred.
		We recommend keeping the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
		The default state after initializing the session is ON."""
		return self._core.io.query_instr_status

	@instrument_status_checking.setter
	def instrument_status_checking(self, value) -> None:
		"""Sets / returns Instrument Status Checking.
		When True (default is True), all the driver methods and properties are sending "SYSTem:ERRor?"
		at the end to immediately react on error that might have occurred.
		We recommend keeping the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
		The default state after initializing the session is ON."""
		self._core.io.query_instr_status = value

	@property
	def encoding(self) -> str:
		"""Returns string<=>bytes encoding of the session."""
		return self._core.io.encoding

	@encoding.setter
	def encoding(self, value: str) -> None:
		"""Sets string<=>bytes encoding of the session."""
		self._core.io.encoding = value

	@property
	def opc_query_after_write(self) -> bool:
		"""Sets / returns Instrument *OPC? query sending after each command write.
		When True, (default is False) the driver sends *OPC? every time a write command is performed.
		Use this if you want to make sure your sequence is performed command-after-command."""
		return self._core.io.opc_query_after_write

	@opc_query_after_write.setter
	def opc_query_after_write(self, value) -> None:
		"""Sets / returns Instrument *OPC? query sending after each command write.
		When True, (default is False) the driver sends *OPC? every time a write command is performed.
		Use this if you want to make sure your sequence is performed command-after-command."""
		self._core.io.opc_query_after_write = value

	@property
	def bin_float_numbers_format(self) -> BinFloatFormat:
		"""Sets / returns format of float numbers when transferred as binary data"""
		return self._core.io.bin_float_numbers_format

	@bin_float_numbers_format.setter
	def bin_float_numbers_format(self, value: BinFloatFormat) -> None:
		"""Sets / returns format of float numbers when transferred as binary data"""
		self._core.io.bin_float_numbers_format = value

	@property
	def bin_int_numbers_format(self) -> BinIntFormat:
		"""Sets / returns format of integer numbers when transferred as binary data"""
		return self._core.io.bin_int_numbers_format

	@bin_int_numbers_format.setter
	def bin_int_numbers_format(self, value: BinIntFormat) -> None:
		"""Sets / returns format of integer numbers when transferred as binary data"""
		self._core.io.bin_int_numbers_format = value

	def clear_status(self) -> None:
		"""Clears instrument's status system, the session's I/O buffers and the instrument's error queue"""
		return self._core.io.clear_status()

	def query_all_errors(self) -> List[str] or None:
		"""Queries and clears all the errors from the instrument's error queue.
		The method returns list of strings as error messages. If no error is detected, the return value is None.
		The process is: querying 'SYSTem:ERRor?' in a loop until the error queue is empty.
		If you want to include the error codes, call the query_all_errors_with_codes()"""
		return self._core.io.query_all_syst_errors(include_codes=False)

	def query_all_errors_with_codes(self) -> List[Tuple[int, str]] or None:
		"""Queries and clears all the errors from the instrument's error queue.
		The method returns list of tuples (code: int, message: str). If no error is detected, the return value is None.
		The process is: querying 'SYSTem:ERRor?' in a loop until the error queue is empty."""
		return self._core.io.query_all_syst_errors(include_codes=True)

	def reset(self, timeout: int = 0) -> None:
		"""SCPI command: *RST
		Sends *RST command + calls the clear_status().
		If you define timeout > 0, the VISA timeout is set to that value just for this method call."""
		self._core.io.reset(timeout)

	def self_test(self, timeout: int = None) -> Tuple[int, str]:
		"""SCPI command: *TST?
		Performs instrument's self-test.
		Returns tuple (code:int, message: str). Code 0 means the self-test passed.
		You can define the custom timeout in milliseconds. If you do not define it, the method uses default self-test timeout (usually 60 secs)."""
		return self._core.io.self_test(timeout)

	def is_connection_active(self) -> bool:
		"""Returns true, if the VISA connection is active and the communication with the instrument still works."""
		return self._core.io.is_connection_active()

	def reconnect(self, force_close: bool = False) -> bool:
		"""If the connection is not active, the method tries to reconnect to the device.
		If the connection is active, and force_close is False, the method does nothing.
		If the connection is active, and force_close is True, the method closes, and opens the session again.
		Returns True, if the reconnection has been performed."""
		return self._core.io.reconnect(force_close)

	@property
	def resource_name(self) -> str:
		"""Returns the resource name used in the constructor."""
		return self._core.io.resource_name

	@property
	def opc_timeout(self) -> int:
		"""Sets / returns timeout in milliseconds for all the operations that use OPC synchronization."""
		return self._core.io.opc_timeout

	@opc_timeout.setter
	def opc_timeout(self, value: int) -> None:
		"""Sets / returns timeout in milliseconds for all the operations that use OPC synchronization."""
		self._core.io.opc_timeout = value

	@property
	def visa_timeout(self) -> int:
		"""Sets / returns visa IO timeout in milliseconds."""
		return self._core.io.visa_timeout

	@visa_timeout.setter
	def visa_timeout(self, value) -> None:
		"""Sets / returns visa IO timeout in milliseconds."""
		self._core.io.visa_timeout = value

	@property
	def data_chunk_size(self) -> int:
		"""Returns max chunk size of one data block."""
		return self._core.io.data_chunk_size

	@data_chunk_size.setter
	def data_chunk_size(self, chunk_size: int) -> None:
		"""Sets the maximum size of one block transferred during write/read operations."""
		self._core.io.data_chunk_size = chunk_size

	@property
	def visa_manufacturer(self) -> str:
		"""Returns the manufacturer of the current VISA session."""
		return self._core.io.visa_manufacturer

	@property
	def opc_sync_query_mechanism(self) -> OpcSyncQueryMechanism:
		"""Returns the current setting of the OPC-Sync query mechanism."""
		return self._core.io.opc_sync_query_mechanism

	@opc_sync_query_mechanism.setter
	def opc_sync_query_mechanism(self, mechanism: OpcSyncQueryMechanism) -> None:
		"""Sets the current setting of the OPC-Sync query mechanism."""
		self._core.io.opc_sync_query_mechanism = mechanism

	def go_to_local(self) -> None:
		"""Puts the instrument into local state."""
		self._core.io.go_to_local()

	def go_to_remote(self) -> None:
		"""Puts the instrument into remote state."""
		self._core.io.go_to_remote()

	def lock_resource(self, timeout: int, requested_key: str or bytes = None) -> bytes or None:
		"""Locks the instrument to prevent it from communicating with other clients."""
		return self._core.io.lock_resource(timeout, requested_key)

	def unlock_resource(self) -> None:
		"""Unlocks the instrument to other clients."""
		self._core.io.unlock_resource()

	def process_all_commands(self) -> None:
		"""SCPI command: *WAI
		Stops further commands processing until all commands sent before *WAI have been executed."""
		return self._core.io.write('*WAI')

	def write(self, cmd: str) -> None:
		"""Writes the command to the instrument as string.
		This method is an alias to the write_str() method."""
		self._core.io.write(cmd, log_info='Write')

	def write_str(self, cmd: str) -> None:
		"""Writes the command to the instrument as string.
		This method is an alias to write() method."""
		self._core.io.write(cmd, log_info='Write')

	def write_int(self, cmd: str, param: int) -> None:
		"""Writes the command to the instrument followed by the integer parameter:
		e.g.: cmd = 'SELECT:INPUT' param = '2', result command = 'SELECT:INPUT 2'"""
		self._core.io.write(f'{cmd} {param}', log_info='Write integer')

	def write_int_with_opc(self, cmd: str, param: int, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the integer parameter:
		e.g.: cmd = 'SELECT:INPUT' param = '2', result command = 'SELECT:INPUT 2'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {param}', timeout, log_info='Write integer with OPC')

	def write_float(self, cmd: str, param: float) -> None:
		"""Writes the command to the instrument followed by the boolean parameter:
		e.g.: cmd = 'CENTER:FREQ' param = '10E6', result command = 'CENTER:FREQ 10E6'"""
		self._core.io.write(f'{cmd} {Conv.float_to_str(param)}', log_info='Write float')

	def write_float_with_opc(self, cmd: str, param: float, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the boolean parameter:
		e.g.: cmd = 'CENTER:FREQ' param = '10E6', result command = 'CENTER:FREQ 10E6'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {Conv.float_to_str(param)}', timeout, log_info='Write float with OPC')

	def write_bool(self, cmd: str, param: bool) -> None:
		"""Writes the command to the instrument followed by the boolean parameter:
		e.g.: cmd = 'OUTPUT' param = 'True', result command = 'OUTPUT ON'"""
		self._core.io.write(f'{cmd} {Conv.bool_to_str(param)}', log_info='Write boolean')

	def write_bool_with_opc(self, cmd: str, param: bool, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the boolean parameter:
		e.g.: cmd = 'OUTPUT' param = 'True', result command = 'OUTPUT ON'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {Conv.bool_to_str(param)}', timeout, log_info='Write boolean with OPC')

	def query(self, query: str) -> str:
		"""Sends the string query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit.
		This method is an alias to the query_str() method."""
		return self._core.io.query_str(query)

	def query_str(self, query: str) -> str:
		"""Sends the string query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit.
		This method is an alias to the query() method."""
		return self._core.io.query_str(query)

	def query_stripped(self, query: str) -> str:
		"""Sends the string query to the instrument and returns the response as string stripped of the trailing LF and leading/trailing single/double quotes.
		The stripping of the leading/trailing quotes is blocked, if the string contains the quotes in the middle.
		"""
		return trim_str_response(self._core.io.query_str(query))

	def query_str_stripped(self, query: str) -> str:
		"""Sends the string query to the instrument and returns the response as string stripped of the trailing LF and leading/trailing single/double quotes.
		The stripping of the leading/trailing quotes is blocked, if the string contains the quotes in the middle.
		This method is an alias to the query_stripped() method."""
		return self.query_stripped(query)

	def query_bool(self, query: str) -> bool:
		"""Sends the query to the instrument and returns the response as boolean."""
		return self._core.io.query_bool(query)

	def query_int(self, query: str) -> int:
		"""Sends the query to the instrument and returns the response as integer."""
		return self._core.io.query_int(query)

	def query_float(self, query: str) -> float:
		"""Sends the query to the instrument and returns the response as float."""
		return self._core.io.query_float(query)

	def query_str_list(self, query: str, remove_blank_response: bool = False) -> List[str]:
		"""Sends the string query to the instrument and returns the response as List of strings, where the delimiter is comma (','). Each element of the list is trimmed for leading and trailing quotes.
		\nMeaning of the 'remove_blank_response':
		- False(default): whitespaces-only response is returned as a list with one empty element [''].
		- True: whitespaces-only response is returned as an empty list []."""
		return self._core.io.query_str_list(query, remove_blank_response)

	def query_bool_list(self, query: str) -> List[bool]:
		"""Sends the string query to the instrument and returns the response as List of booleans,
		where the delimiter is comma (',').
		Blank or empty response is returned as an empty list."""
		return self._core.io.query_bool_list(query)

	def write_str_with_opc(self, cmd: str, timeout: int = None) -> None:
		"""Writes the opc-synced command to the instrument.
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(cmd, timeout)

	def write_with_opc(self, cmd: str, timeout: int = None) -> None:
		"""This method is an alias to the write_str_with_opc().
		Writes the opc-synced command to the instrument.
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(cmd, timeout)

	def query_str_with_opc(self, query: str, timeout: int = None) -> str:
		"""Sends the opc-synced query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_str_with_opc(query, timeout)

	def query_with_opc(self, query: str, timeout: int = None) -> str:
		"""This method is an alias to the write_str_with_opc().
		Sends the opc-synced query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_str_with_opc(query, timeout)

	def query_str_list_with_opc(self, query: str, timeout: int = None, remove_blank_response: bool = False) -> List[str]:
		"""Sends a OPC-synced query and reads response from the instrument as csv-list.
		If you do not provide timeout, the method uses current opc_timeout.
		\nMeaning of the 'remove_blank_response':
		- False(default): whitespaces-only response is returned as a list with one empty element [''].
		- True: whitespaces-only response is returned as an empty list []."""
		return self._core.io.query_str_list_with_opc(query, timeout, remove_blank_response)

	def query_bool_with_opc(self, query: str, timeout: int = None) -> bool:
		"""Sends the opc-synced query to the instrument and returns the response as boolean.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bool_with_opc(query, timeout)

	def query_bool_list_with_opc(self, query: str, timeout: int = None) -> List[bool]:
		"""Sends a OPC-synced query and reads response from the instrument as csv-list of booleans.
		If you do not provide timeout, the method uses current opc_timeout.
		Blank or empty response is returned as an empty list."""
		return self._core.io.query_bool_list_with_opc(query, timeout)

	def query_int_with_opc(self, query: str, timeout: int = None) -> int:
		"""Sends the opc-synced query to the instrument and returns the response as integer.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_int_with_opc(query, timeout)

	def query_float_with_opc(self, query: str, timeout: int = None) -> float:
		"""Sends the opc-synced query to the instrument and returns the response as float.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_float_with_opc(query, timeout)

	def write_bin_block(self, cmd: str, payload: bytes) -> None:
		"""Writes all the payload as binary data block to the instrument.
		The binary data header is added at the beginning of the transmission automatically, do not include it in the payload!!!"""
		self._core.io.write_bin_block(cmd, payload)

	def query_bin_block(self, query: str) -> bytes:
		"""Queries binary data block to bytes.
		Throws an exception if the returned data was not a binary data.
		Returns data:bytes"""
		return self._core.io.query_bin_block(query)

	def query_bin_block_with_opc(self, query: str, timeout: int = None) -> bytes:
		"""Sends a OPC-synced query and returns binary data block to bytes.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bin_block_with_opc(query, timeout)

	def query_bin_or_ascii_float_list(self, query: str) -> List[float]:
		"""Queries a list of floating-point numbers that can be returned as ASCII or binary format.

		* For ASCII format, the list numbers are decoded as comma-separated values.
		* For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).
		"""
		return self._core.io.query_bin_or_ascii_float_list(query)

	def query_bin_or_ascii_float_list_with_opc(self, query: str, timeout: int = None) -> List[float]:
		"""Sends a OPC-synced query and reads a list of floating-point numbers that can be returned as ASCII or binary format.

		* For ASCII format, the list numbers are decoded as comma-separated values.
		* For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).

		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bin_or_ascii_float_list_with_opc(query, timeout)

	def query_bin_or_ascii_int_list(self, query: str) -> List[int]:
		"""Queries a list of floating-point numbers that can be returned as ASCII or binary format.

		* For ASCII format, the list numbers are decoded as comma-separated values.
		* For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).
		"""
		return self._core.io.query_bin_or_ascii_int_list(query)

	def query_bin_or_ascii_int_list_with_opc(self, query: str, timeout: int = None) -> List[int]:
		"""Sends a OPC-synced query and reads a list of floating-point numbers that can be returned as ASCII or binary format.

		* For ASCII format, the list numbers are decoded as comma-separated values.
		* For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).

		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bin_or_ascii_int_list_with_opc(query, timeout)

	# Write / Read to file
	def query_bin_block_to_file(self, query: str, file_path: str, append: bool = False) -> None:
		"""Queries binary data block to the provided file.
		If append is False, any existing file content is discarded.
		If append is True, the new content is added to the end of the existing file, or if the file does not exit, it is created.
		Throws an exception if the returned data was not a binary data.
		Example for transferring a file from Instrument -> PC:
		query = f"MMEM:DATA? '{INSTR_FILE_PATH}'".

		Alternatively, use the dedicated methods for this purpose:

		* ``send_file_from_pc_to_instrument()``
		* ``read_file_from_instrument_to_pc()``

		"""
		self._core.io.query_bin_block_to_file(query, file_path, append)

	def query_bin_block_to_file_with_opc(self, query: str, file_path: str, append: bool = False, timeout: int = None) -> None:
		"""Sends a OPC-synced query and writes the returned data to the provided file.
		If append is False, any existing file content is discarded.
		If append is True, the new content is added to the end of the existing file, or if the file does not exit, it is created.
		Throws an exception if the returned data was not a binary data."""
		self._core.io.query_bin_block_to_file_with_opc(query, file_path, append, timeout)

	def write_bin_block_from_file(self, cmd: str, file_path: str) -> None:
		"""Writes data from the file as binary data block to the instrument using the provided command.
		Example for transferring a file from PC -> Instrument:
		cmd = f"MMEM:DATA '{INSTR_FILE_PATH}',".

		Alternatively, use the dedicated methods for this purpose:

		* ``send_file_from_pc_to_instrument()``
		* ``read_file_from_instrument_to_pc()``

		"""
		self._core.io.write_bin_block_from_file(cmd, file_path)

	def send_file_from_pc_to_instrument(self, source_pc_file: str, target_instr_file: str) -> None:
		"""SCPI Command: MMEM:DATA \n
		Sends file from PC to the instrument."""
		self._core.io.send_file_from_pc_to_instrument(source_pc_file, target_instr_file)

	def read_file_from_instrument_to_pc(self, source_instr_file: str, target_pc_file: str, append_to_pc_file: bool = False) -> None:
		"""SCPI Command: MMEM:DATA? \n
		Reads file from instrument to the PC. \n
		Set the ``append_to_pc_file`` to True if you want to append the read content to the end of the existing PC file."""
		self._core.io.read_file_from_instrument_to_pc(source_instr_file, target_pc_file, append_to_pc_file)

	def get_file_size(self, instr_file: str) -> int or None:
		"""Return size of the instrument file, or None if the file does not exist."""
		return self._core.io.get_file_size(instr_file)

	def file_exists(self, instr_file: str) -> bool:
		"""Returns true, if the instrument file exist."""
		return self.get_file_size(instr_file) is not None

	def get_last_sent_cmd(self) -> str:
		"""Returns the last commands sent to the instrument. Only works in simulation mode."""
		return self._core.get_last_sent_cmd()

	def get_lock(self) -> threading.RLock:
		"""Returns the thread lock for the current session. \n
		By default:

		* If you create a new RsInstrument instance with new VISA session, the session gets a new thread lock. You can assign it to another RsInstrument sessions in order to share one physical instrument with a multi-thread access.
		* If you create a new RsInstrument from an existing session, the thread lock is shared automatically making both instances multi-thread safe.

		You can always assign new thread lock by calling ``driver.utilities.assign_lock()``"""
		return self._core.io.get_lock()

	def assign_lock(self, lock: threading.RLock) -> None:
		"""Assigns the provided thread lock."""
		self._core.io.assign_lock(lock)

	def clear_lock(self) -> None:
		"""Clears the existing thread lock, making the current session thread-independent from others that might share the current thread lock."""
		self._core.io.clear_lock()

	def get_total_execution_time(self) -> timedelta:
		"""Returns total time spent by the library on communicating with the instrument.
		This time is always shorter than get_total_time(), since it does not include gaps between the communication.
		You can reset this counter with reset_time_statistics()."""
		return self._core.io.total_execution_time

	def get_total_time(self) -> timedelta:
		"""Returns total time spent by the library on communicating with the instrument.
		This time is always shorter than get_total_time(), since it does not include gaps between the communication.
		You can reset this counter with reset_time_statistics()."""
		return datetime.now() - self._core.io.total_time_startpoint

	def get_total_time_startpoint(self) -> datetime:
		"""Returns time from which the execution started.
		This is the value that the get_total_time() calculates as its reference.
		Calling the reset_time_statistics() sets this time to now."""
		return self._core.io.total_time_startpoint

	def reset_time_statistics(self) -> None:
		"""Resets all execution and total time counters.
		Affects the results of get_total_time(), get_total_execution_time() and get_total_time_startpoint()"""
		self._core.io.reset_time_statistics()

	@staticmethod
	def assert_minimum_version(min_version: str) -> None:
		"""Asserts that the driver version fulfills the minimum required version you have entered.
		This way you make sure your installed driver is of the entered version or newer."""
		min_version_list = min_version.split('.')
		curr_version_list = RsInstrument._driver_version_const.split('.')
		count_min = len(min_version_list)
		count_curr = len(curr_version_list)
		count = count_min if count_min < count_curr else count_curr
		for i in range(count):
			minimum = int(min_version_list[i])
			curr = int(curr_version_list[i])
			if curr > minimum:
				break
			if curr < minimum:
				raise Exception(f"Assertion for minimum RsInstrument version failed. Current version: '{RsInstrument._driver_version_const}', minimum required version: '{min_version}'")

	def instr_err_suppressor(self, visa_tout_ms: int = 0, suppress_only_codes: int or List[int] = None) -> InstrErrorSuppressor:
		"""Returns Context Manager that suppresses the instrument errors.
		Other exceptions types are still raised.
		On entering the context, this class clears all the instrument status errors.
		:param visa_tout_ms: VISA Timeout in milliseconds, that is set for this context. Afterward, it is changed back. Default value: do-not-change.
		:param suppress_only_codes: You can enter a code or list of codes for errors to be suppressed. Other errors will be reported. Example: If you enter -113 here, only the 'Undefined Header' error will be suppressed. Default value: suppress-all-errors."""
		return InstrErrorSuppressor(self._core.io, visa_tout_ms, suppress_only_codes)

	def visa_tout_suppressor(self, visa_tout_ms: int = 0) -> VisaTimeoutSuppressor:
		"""Returns Context Manager that suppresses the VISA timeout error.
		Careful!!!: Only the very first VISA Timeout exception is suppressed,
		and afterward the context ends. Therefore, use only one command per context manager,
		if you do not want to skip the following ones.
		:param visa_tout_ms: VISA Timeout in milliseconds, that is set for this context. Afterward, it is changed back. Default value: do-not-change.
		"""
		return VisaTimeoutSuppressor(self._core.io, visa_tout_ms)

	@property
	def instrument_options(self) -> List[str]:
		"""Returns all the instrument options.
		The options are sorted in the ascending order starting with K-options and continuing with B-options"""
		return self._core.io.instr_options.get_all()

	def has_instr_option(self, options: str or List[str]) -> bool:
		"""Returns true, if the entered options (case-insensitive) matches at least one of the installed options (or-logic).
		You can enter either a string with one option, or more options '/'-separated, or more options as a list of strings.
		If K0 is present, all the K-options are reported as present. B-options are not affected by K0.
		Example 1: options='k23' returns true, if the instrument has the option 'K23'.
		Example 2: options='k23 / K23e' returns true, if the instrument has either the option 'K23' or the option 'K23E'.
		Example 3: options=['k11','K22'] returns true, if the instrument has either the option 'K11' or the option 'K22'."""
		return self._core.io.instr_options.has(options)

	def has_instr_option_regex(self, re_options: str or List[str]) -> bool:
		"""Returns true, if the entered regex string (case-insensitive) matches at least one of the installed options.
		The match must be complete, not just partial (search).
		You can enter either a string with one option, or more options '/'-separated, or more options as a list of strings.
		Example 1: re_options='k10.' returns true, if the instrument contains any option 'K100' ... up to 'K109' .
		Example 2: re_options='k10. / k20.*' returns true, if the instrument contains any of the options 'K10x' or 'K20xxx'.
		Example 3: re_options=['k10.', 'k20.*'] returns true, if the instrument contains any options 'K10x' or 'K20xxx'."""
		return self._core.io.instr_options.has_regex(re_options)

	def has_instr_option_k0(self) -> bool:
		"""Returns true, if the instrument has K0 installed."""
		return self._core.io.instr_options.has_k0()

	def add_instr_option(self, option: str) -> None:
		"""Adds new option if not already existing."""
		self._core.io.instr_options.add(option)

	def remove_instr_option(self, option: str) -> None:
		"""Removes the option if exists."""
		self._core.io.instr_options.remove(option)
