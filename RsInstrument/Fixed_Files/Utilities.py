"""Utilities extending the driver for methods provided with RsInstrument."""

from typing import List, Tuple
import threading

from ..Internal import Core
from ..Internal import Conversions as Conv
from ..Internal.ScpiLogger import ScpiLogger


class Utilities:
	"""Common utility class.
	Utility functions common for all types of drivers. \n
	Access snippet: ``utils = [DRIVER_PREFIX].utilities``"""
	def __init__(self, core: Core):
		self._core = core

	@property
	def logger(self) -> ScpiLogger:
		"""Scpi Logger interface, see :ref:`here <Logger>` \n
		Access snippet: ``logger = [DRIVER_PREFIX].utilities.logger``"""
		return self._core.io.logger

	@property
	def driver_version(self) -> str:
		"""Returns the instrument driver version."""
		return self._core.driver_version

	@property
	def idn_string(self) -> str:
		"""Returns instrument's identification string - the response on the SCPI command *IDN?"""
		return self._core.io.idn_string

	@property
	def manufacturer(self) -> str:
		"""Returns manufacturer of the instrument."""
		return self._core.io.manufacturer

	@property
	def full_instrument_model_name(self) -> str:
		"""Returns the current instrument's full name e.g. 'FSW26'."""
		return self._core.io.full_model_name

	@property
	def instrument_model_name(self) -> str:
		"""Returns the current instrument's family name e.g. 'FSW'."""
		return self._core.io.model

	@property
	def supported_models(self) -> List[str]:
		"""Returns a list of the instrument models supported by this instrument driver."""
		return self._core.supported_instr_models

	@property
	def instrument_firmware_version(self) -> str:
		"""Returns instrument's firmware version."""
		return self._core.io.firmware_version

	@property
	def instrument_serial_number(self) -> str:
		"""Returns instrument's serial_number."""
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
		We recommend to keep the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
		The default state after initializing the session is ON."""
		return self._core.io.query_instr_status

	@instrument_status_checking.setter
	def instrument_status_checking(self, value) -> None:
		"""Sets / returns Instrument Status Checking.
		When True (default is True), all the driver methods and properties are sending "SYSTem:ERRor?"
		at the end to immediately react on error that might have occurred.
		We recommend to keep the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
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
	def bin_float_numbers_format(self) -> Conv.BinFloatFormat:
		"""Sets / returns format of float numbers when transferred as binary data."""
		return self._core.io.bin_float_numbers_format

	@bin_float_numbers_format.setter
	def bin_float_numbers_format(self, value: Conv.BinFloatFormat) -> None:
		"""Sets / returns format of float numbers when transferred as binary data."""
		self._core.io.bin_float_numbers_format = value

	@property
	def bin_int_numbers_format(self) -> Conv.BinIntFormat:
		"""Sets / returns format of integer numbers when transferred as binary data."""
		return self._core.io.bin_int_numbers_format

	@bin_int_numbers_format.setter
	def bin_int_numbers_format(self, value: Conv.BinIntFormat) -> None:
		"""Sets / returns format of integer numbers when transferred as binary data."""
		self._core.io.bin_int_numbers_format = value

	def clear_status(self) -> None:
		"""Clears instrument's status system, the session's I/O buffers and the instrument's error queue."""
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

	@property
	def instrument_options(self) -> List[str]:
		"""Returns all the instrument options.
		The options are sorted in the ascending order starting with K-options and continuing with B-options."""
		return self._core.io.instr_options.get_all()

	def reset(self) -> None:
		"""SCPI command: *RST
		Sends *RST command + calls the clear_status()."""
		self._core.io.reset()
		self.default_instrument_setup()

	def default_instrument_setup(self) -> None:
		"""Custom steps performed at the init and at the reset()."""

	def self_test(self, timeout: int = None) -> Tuple[int, str]:
		"""SCPI command: *TST?
		Performs instrument's self-test.
		Returns tuple (code:int, message: str). Code 0 means the self-test passed.
		You can define the custom timeout in milliseconds. If you do not define it, the default selftest timeout is used (usually 60 secs)."""
		return self._core.io.self_test(timeout)

	def is_connection_active(self) -> bool:
		"""Returns true, if the VISA connection is active and the communication with the instrument still works."""
		return self._core.io.is_connection_active()

	def reconnect(self, force_close: bool = False) -> bool:
		"""If the connection is not active, the method tries to reconnect to the device
		If the connection is active, and force_close is False, the method does nothing.
		If the connection is active, and force_close is True, the method closes, and opens the session again.
		Returns True, if the reconnection has been performed."""
		return self._core.io.reconnect(force_close)

	@property
	def resource_name(self) -> int:
		"""Returns the resource name used in the constructor"""
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
		"""Sets / returns the maximum size of one block transferred during write/read operations"""
		return self._core.io.data_chunk_size

	@data_chunk_size.setter
	def data_chunk_size(self, chunk_size: int) -> None:
		"""Sets / returns the maximum size of one block transferred during write/read operations."""
		self._core.io.data_chunk_size = chunk_size

	@property
	def visa_manufacturer(self) -> int:
		"""Returns the manufacturer of the current VISA session."""
		return self._core.io.visa_manufacturer

	def process_all_commands(self) -> None:
		"""SCPI command: *WAI
		Stops further commands processing until all commands sent before *WAI have been executed."""
		return self._core.io.write('*WAI')

	def write_str(self, cmd: str) -> None:
		"""Writes the command to the instrument."""
		self._core.io.write(cmd)

	def write(self, cmd: str) -> None:
		"""This method is an alias to the write_str().
		Writes the command to the instrument as string."""
		self._core.io.write(cmd)

	def write_int(self, cmd: str, param: int) -> None:
		"""Writes the command to the instrument followed by the integer parameter:
		e.g.: cmd = 'SELECT:INPUT' param = '2', result command = 'SELECT:INPUT 2'"""
		self._core.io.write(f'{cmd} {param}')

	def write_int_with_opc(self, cmd: str, param: int, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the integer parameter:
		e.g.: cmd = 'SELECT:INPUT' param = '2', result command = 'SELECT:INPUT 2'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {param}', timeout)

	def write_float(self, cmd: str, param: float) -> None:
		"""Writes the command to the instrument followed by the boolean parameter:
		e.g.: cmd = 'CENTER:FREQ' param = '10E6', result command = 'CENTER:FREQ 10E6'"""
		self._core.io.write(f'{cmd} {Conv.float_to_str(param)}')

	def write_float_with_opc(self, cmd: str, param: float, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the boolean parameter:
		e.g.: cmd = 'CENTER:FREQ' param = '10E6', result command = 'CENTER:FREQ 10E6'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {Conv.float_to_str(param)}', timeout)

	def write_bool(self, cmd: str, param: bool) -> None:
		"""Writes the command to the instrument followed by the boolean parameter:
		e.g.: cmd = 'OUTPUT' param = 'True', result command = 'OUTPUT ON'"""
		self._core.io.write(f'{cmd} {Conv.bool_to_str(param)}')

	def write_bool_with_opc(self, cmd: str, param: bool, timeout: int = None) -> None:
		"""Writes the command with OPC to the instrument followed by the boolean parameter:
		e.g.: cmd = 'OUTPUT' param = 'True', result command = 'OUTPUT ON'
		If you do not provide timeout, the method uses current opc_timeout."""
		self._core.io.write_with_opc(f'{cmd} {Conv.bool_to_str(param)}', timeout)

	def query_str(self, query: str) -> str:
		"""Sends the query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit."""
		return self._core.io.query_str(query)

	def query(self, query: str) -> str:
		"""This method is an alias to the query_str().
		Sends the query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit."""
		return self._core.io.query_str(query)

	def query_bool(self, query: str) -> bool:
		"""Sends the query to the instrument and returns the response as boolean."""
		return self._core.io.query_bool(query)

	def query_int(self, query: str) -> int:
		"""Sends the query to the instrument and returns the response as integer."""
		return self._core.io.query_int(query)

	def query_float(self, query: str) -> float:
		"""Sends the query to the instrument and returns the response as float."""
		return self._core.io.query_float(query)

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
		"""This method is an alias to the query_str_with_opc().
		Sends the opc-synced query to the instrument and returns the response as string.
		The response is trimmed of any trailing LF characters and has no length limit.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_str_with_opc(query, timeout)

	def query_bool_with_opc(self, query: str, timeout: int = None) -> bool:
		"""Sends the opc-synced query to the instrument and returns the response as boolean.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bool_with_opc(query, timeout)

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
		"""Queries a list of floating-point numbers that can be returned in ASCII format or in binary format.
		- For ASCII format, the list numbers are decoded as comma-separated values.
		- For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32)."""
		return self._core.io.query_bin_or_ascii_float_list(query)

	def query_bin_or_ascii_float_list_with_opc(self, query: str, timeout: int = None) -> List[float]:
		"""Sends a OPC-synced query and reads a list of floating-point numbers that can be returned in ASCII format or in binary format.
		- For ASCII format, the list numbers are decoded as comma-separated values.
		- For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).
		If you do not provide timeout, the method uses current opc_timeout."""
		return self._core.io.query_bin_or_ascii_float_list_with_opc(query, timeout)

	def query_bin_or_ascii_int_list(self, query: str) -> List[int]:
		"""Queries a list of floating-point numbers that can be returned in ASCII format or in binary format.
		- For ASCII format, the list numbers are decoded as comma-separated values.
		- For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32)."""
		return self._core.io.query_bin_or_ascii_int_list(query)

	def query_bin_or_ascii_int_list_with_opc(self, query: str, timeout: int = None) -> List[int]:
		"""Sends a OPC-synced query and reads a list of floating-point numbers that can be returned in ASCII format or in binary format.
		- For ASCII format, the list numbers are decoded as comma-separated values.
		- For Binary Format, the numbers are decoded based on the property BinFloatFormat, usually float 32-bit (FORM REAL,32).
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
			- ``send_file_from_pc_to_instrument()``
			- ``read_file_from_instrument_to_pc()``"""
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
			- ``send_file_from_pc_to_instrument()``
			- ``read_file_from_instrument_to_pc()``"""
		self._core.io.write_bin_block_from_file(cmd, file_path)

	def send_file_from_pc_to_instrument(self, source_pc_file: str, target_instr_file: str) -> None:
		"""SCPI Command: MMEM:DATA \n
		Sends file from PC to the instrument"""
		self._core.io.send_file_from_pc_to_instrument(source_pc_file, target_instr_file)

	def read_file_from_instrument_to_pc(self, source_instr_file: str, target_pc_file: str, append_to_pc_file: bool = False) -> None:
		"""SCPI Command: MMEM:DATA? \n
		Reads file from instrument to the PC. \n
		Set the ``append_to_pc_file`` to True if you want to append the read content to the end of the existing PC file"""
		self._core.io.read_file_from_instrument_to_pc(source_instr_file, target_pc_file, append_to_pc_file)

	def get_last_sent_cmd(self) -> str:
		"""Returns the last commands sent to the instrument. Only works in simulation mode"""
		return self._core.get_last_sent_cmd()

	def get_lock(self) -> threading.RLock:
		"""Returns the thread lock for the current session. \n
		By default:
			- If you create standard new [DRIVER_PREFIX] instance with new VISA session, the session gets a new thread lock. You can assign it to other [DRIVER_PREFIX] sessions in order to share one physical instrument with a multi-thread access.
			- If you create new [DRIVER_PREFIX] from an existing session, the thread lock is shared automatically making both instances multi-thread safe.
		You can always assign new thread lock by calling ``driver.utilities.assign_lock()``"""
		return self._core.io.get_lock()

	def assign_lock(self, lock: threading.RLock) -> None:
		"""Assigns the provided thread lock."""
		self._core.io.assign_lock(lock)

	def clear_lock(self):
		"""Clears the existing thread lock, making the current session thread-independent from others that might share the current thread lock."""
		self._core.io.clear_lock()

	def sync_from(self, source: 'Utilities') -> None:
		"""Synchronises these Utils with the source."""
		self.logger.sync_from(source.logger)
		self.assign_lock(source.get_lock())
		self.bin_float_numbers_format = source.bin_float_numbers_format
		self.bin_int_numbers_format = source.bin_int_numbers_format
		self.data_chunk_size = source.data_chunk_size
		self.encoding = source.encoding
		self.instrument_status_checking = source.instrument_status_checking
		self.opc_query_after_write = source.opc_query_after_write
		self.opc_timeout = source.opc_timeout
