"""Visa Session is an extension of the pure VISA providing higher level of methods regardless of the session kind."""

import time
from enum import Enum, Flag
from typing import List, Tuple, Callable, AnyStr
import os.path
import re
import threading

# noinspection PyPackageRequirements
import pyvisa

from .VisaPluginSocketIo import ResourceManager, SocketIo
from . import InstrumentSettings, InstrumentErrors, Conversions as Conv
from .InstrumentSettings import WaitForOpcMode, InstrViClearMode as ViClearMode
from .StreamReader import StreamReader
from .StreamWriter import StreamWriter
from .Utilities import size_to_kb_mb_string, calculate_chunks_count
import platform
import struct


class SessionKind(Enum):
	"""Visa instrument session type."""
	unsupported = 0
	gpib = 1
	serial = 2
	vxi11 = 3
	socket = 5
	usb = 6
	rs_nrp = 7


class ReadDataType(Enum):
	"""Data type returned by the instrument."""
	unknown = 0
	ascii = 1
	null = 2
	bin_known_len = 3
	bin_unknown_len = 4


class StatusByte(Flag):
	"""Status Byte flags."""
	NONE = 0x00
	error_queue_not_empty = 0x04
	questionable_status_reg = 0x08
	message_available = 0x10
	event_status_byte = 0x20
	request_service = 0x40
	operation_status_reg = 0x80


class EventStatusRegister(Flag):
	"""Event Status Register flags."""
	null = 0x00
	operation_complete = 0x01


# noinspection PyUnresolvedReferences
class VisaSession(object):
	"""Extended VISA class."""

	def __init__(self, resource_name: str, settings: InstrumentSettings, direct_session=None):
		self.reusing_session = direct_session is not None
		# noinspection PyTypeChecker
		self._data_chunk_size: int = None
		self._std_bin_block_header_max_len: int = 999999999
		self._lock = None
		self.disable_opc_query: bool = settings.disable_opc_query
		self.last_status = None
		self.visa_library_name = None
		self.resource_name = resource_name		# might be changed later if direct_session is used

		# Implemented for interface compatibility with VisaSessionSim
		self.cached_to_stream = False

		# Event handlers
		# noinspection PyTypeChecker
		self.on_read_chunk_handler: Callable = None
		"""If assigned a handler, the VisaSession sends it event on each read chunk transfer."""
		# noinspection PyTypeChecker
		self.on_write_chunk_handler: Callable = None
		"""If assigned a handler, the VisaSession sends it event on each write chunk transfer."""
		self.io_events_include_data: bool = False
		"""If true, the VisaSession events sent to on_read_chunk_handler and on_write_chunk_handler contain transferred data."""

		if self.reusing_session:
			# Reuse the session
			if not isinstance(direct_session, pyvisa.Resource) and not isinstance(direct_session, SocketIo):
				raise InstrumentErrors.RsInstrException(f"Direct_session must be a VISA resource object. Actual type: '{type(direct_session)}', value: '{direct_session}'")
			self._session = direct_session
			self.resource_name = self._session.resource_name
		else:
			# Create new session
			# Check resource_name for the trailing (SelectVisa=..)
			pure_resource_name, visa_select = self._get_pure_resource_name(resource_name)
			if settings.visa_select is not None:
				visa_select = settings.visa_select
			self._rm = VisaSession.get_resource_manager(visa_select)
			self.manufacturer = self._get_visa_manufacturer()

			# Resource manager opening
			try:
				self._session = self._rm.open_resource(pure_resource_name)
			except pyvisa.VisaIOError as e:
				if e.error_code != pyvisa.constants.StatusCode.error_resource_not_found:
					raise e
				message = e.description
				message += f"\nLibrary: {self._rm.visalib}\nManufacturer: {self.manufacturer}\nResource Name: '{resource_name}'"
				raise InstrumentErrors.ResourceError(resource_name, message)
			self.resource_name = resource_name

		# Decide, whether to create a new thread lock or the existing one from the session
		if hasattr(self._session, 'session_thread_rlock'):
			rlock = self._session.session_thread_rlock
			if isinstance(rlock, type(threading.RLock())):
				self.assign_lock(rlock)
		if self.get_lock() is None:
			# The existing session did not have a thread lock, assign a new one
			self.assign_lock(threading.RLock())

		self._interface_type = SessionKind.unsupported
		if self._session.interface_type == pyvisa.constants.InterfaceType.gpib or self._session.interface_type == pyvisa.constants.InterfaceType.gpib:
			self._interface_type = SessionKind.gpib

		elif self._session.interface_type == pyvisa.constants.InterfaceType.rsnrp:
			self._interface_type = SessionKind.rs_nrp

		elif self._session.interface_type == pyvisa.constants.InterfaceType.asrl:
			self._interface_type = SessionKind.serial

		elif self._session.interface_type == pyvisa.constants.InterfaceType.usb:
			# Check whether it is not the NRP-Z
			intf_type = self._session.get_visa_attribute(pyvisa.constants.VI_ATTR_INTF_TYPE)
			if intf_type == pyvisa.constants.InterfaceType.rsnrp:
				self._interface_type = SessionKind.rs_nrp

		elif self._session.interface_type == pyvisa.constants.InterfaceType.tcpip:
			self._interface_type = SessionKind.vxi11
			if self._session.resource_class == 'SOCKET':
				self._interface_type = SessionKind.socket

		# Specifics for different interfaces
		self._assure_write_with_tc = settings.assure_write_with_tc
		self._term_char = settings.term_char
		self._term_char_bin = self._term_char.encode('utf-8')
		self._session.write_termination = ''
		self.vxi_capable = True

		if self._interface_type == SessionKind.serial:
			self._session.read_termination = self._term_char
			self.vxi_capable = False
			self._assure_write_with_tc = True
		elif self._interface_type == SessionKind.socket:
			self._session.read_termination = self._term_char
			self.vxi_capable = False
			self._assure_write_with_tc = True
		else:
			self._session.read_termination = ''

		# NRP-Z specific settings
		if self.is_rsnrp_session():
			self.disable_opc_query = True
			# NRP-Z does not support chunk reading, therefore the segment must be in one piece
			settings.io_segment_size = 1000000
			self.vxi_capable = False

		self.write_delay = settings.write_delay
		self.read_delay = settings.read_delay
		self._viclear_exe_mode = settings.viclear_exe_mode
		self._opc_wait_mode = settings.opc_wait_mode

		# Parameters that need to be coerced based on Vxi-capability
		if self.vxi_capable:
			self._add_term_char_to_write_bin_block = settings.add_term_char_to_write_bin_block
		else:
			self._add_term_char_to_write_bin_block = True

		# Changeable settings
		self.opc_timeout = 10000 if settings.opc_timeout == 0 else settings.opc_timeout
		self.visa_timeout = settings.visa_timeout
		self._session.chunk_size = settings.io_segment_size
		self._data_chunk_size = settings.io_segment_size

		# Must call the VISA viClear() before the any communication with the instrument
		self.clear()

		# Further steps are for NRP-Z session not valid
		if self.is_rsnrp_session():
			return

		# Clear instrument status
		self.write('*CLS')
		if self.vxi_capable:
			stb = self._read_stb()
			if stb & StatusByte.message_available:
				self._flush_junk_data()

		# Apply settings for ESE and SRE, plus coerce the _opcWaitMode if necessary
		self._opc_wait_mode = self._set_regs_ese_sre(self._opc_wait_mode)

	@staticmethod
	def _get_pure_resource_name(resource_name: str):
		"""Returns pure resource name stripped of the (SelectVisa) part and the visa_select string"""
		m = re.search(r'(.+)\(SelectVisa=([^),]+)\)', resource_name)
		if not m:
			return resource_name, None
		resource_name = m.group(1).strip()
		visa_select = m.group(2).strip()
		return resource_name, visa_select

	@classmethod
	def get_resource_manager(cls, visa_select: str) -> pyvisa.ResourceManager:
		"""Returns resource manager for the desired VISA implementation"""
		operating_system = platform.system().lower()
		bittness = struct.calcsize('P') * 8
		if visa_select is None or visa_select in ['@default', '@standard', 'default', 'standard', 'defaultvisa', 'standardvisa', '@defaultvisa', '@standardvisa']:
			return pyvisa.ResourceManager()
		if visa_select.lower() in ['@ni', 'ni', 'ivi', '@ivi', 'visa-ni', 'nivisa', 'ni-visa', 'nationalinstruments', 'nationalinstrumentsvisa']:
			return pyvisa.ResourceManager()
		if visa_select.lower() in ['@py', 'pyvisa', 'visa-py', 'pyvisa-py']:
			return pyvisa.ResourceManager('@py')
		if 'rohde&schwarz' in visa_select.lower() or 'rohdeschwarz' in visa_select.lower() or visa_select.lower() == 'rsvisa' or visa_select.lower() == 'rs' or visa_select.lower() == 'r&s':
			if operating_system == 'windows':
				if bittness == 32:
					visa_select = r'c:\Windows\SysWOW64\RsVisa32.dll'
				else:
					visa_select = r'c:\Windows\system32\RsVisa32.dll'
				return pyvisa.ResourceManager(visa_select)
			elif operating_system == 'linux':
				# The default install location may be different
				# for debian/red hat/opensuse derived distributions
				check_visa = [f'/usr/lib{bittness}/librsvisa.so', r'/usr/lib/librsvisa.so']
				for check in check_visa:
					if os.path.isfile(check):
						return pyvisa.ResourceManager(check)

		if visa_select.lower() in ['socketio', 'socket', 'none']:
			return ResourceManager()
		return pyvisa.ResourceManager(visa_select)

	def _get_visa_manufacturer(self) -> str:
		"""Returns manufacturer of the current VISA"""
		if hasattr(self._rm, 'VisaManufacturerName'):
			return self._rm.VisaManufacturerName
		try:
			return self._rm.visalib.get_attribute(self._rm.session, pyvisa.constants.VI_ATTR_RSRC_MANF_NAME)[0]
		except TypeError:
			return self._rm.visalib.__class__.__name__

	def is_rsnrp_session(self) -> bool:
		"""Returns True, if the current session is a NRP-Z session"""
		return self._interface_type == SessionKind.rs_nrp

	def assign_lock(self, lock: threading.RLock) -> None:
		"""Assigns the provided thread lock by setting the pyvisa runtime session attribute 'session_thread_rlock'
		This is done, because if the session is to be entered as an existing session to another RsInstrument object,
		the lock must be shared as well. The lock is only used by the parent class Instrument."""
		setattr(self._session, 'session_thread_rlock', lock)
		self._lock = lock

	def get_lock(self) -> threading.RLock:
		"""Returns the current RLock object."""
		return self._lock

	@property
	def visa_timeout(self) -> int:
		"""See the visa_timeout.setter."""
		return int(self._session.timeout)

	@visa_timeout.setter
	def visa_timeout(self, value: int) -> None:
		"""Sets / Gets visa IO timeout in milliseconds."""
		self._session.timeout = int(value)

	@property
	def data_chunk_size(self) -> int:
		"""Returns max chunk size of one data block."""
		return self._data_chunk_size

	@data_chunk_size.setter
	def data_chunk_size(self, chunk_size: int) -> None:
		"""Sets the maximum size of one block transferred during write/read operations."""
		self._data_chunk_size = int(chunk_size)
		self._session.chunk_size = int(chunk_size)

	def _resolve_opc_timeout(self, timeout: int) -> int:
		"""Resolves entered timeout value - if the input value is less than 1, it is replaces with opc_timeout."""
		if timeout is None or timeout < 1:
			return self.opc_timeout
		else:
			return timeout

	def _set_regs_ese_sre(self, mode: WaitForOpcMode) -> WaitForOpcMode:
		"""Based on the WaitForOpcMode, it sets the ESE and SRE register masks.
		Returns coerced WaitForOpcMode."""
		# Set the SRE and ESE registers accordingly
		# No SRE is supported
		self._set_ese_mask(EventStatusRegister.operation_complete)
		self._set_sre_mask(StatusByte.NONE)
		return mode

	def _set_ese_mask(self, mask: EventStatusRegister, reset: bool = True) -> None:
		"""Sends *ESE command with mask parameter."""
		if reset is False:
			current_value = int(self._query_str_no_events('*ESE?'))
			mask = current_value | mask.value
		self.write("*ESE %d" % mask.value)

	def _set_sre_mask(self, mask: StatusByte, reset: bool = True) -> None:
		"""Sends *SRE command with StatusByte mask parameter."""
		if reset is False:
			current_value = int(self._query_str_no_events('*SRE?'))
			mask = current_value | mask.value
		# Also affect the _opc_wait_mode:
		# If the mask has event_status_byte == false, and the _opc_wait_mode is service_request, set it to stb_poll
		# If the mask has event_status_byte == true, do not change anything
		self.write(f'*SRE {mask.value}')

	def _write_and_poll_stb_vxi(self, command: str, is_query: bool, timeout: int, end_mask: StatusByte) -> StatusByte:
		"""Reads Status Byte Register and ends if the ESB bit (5) is set to 1.
		Also works with the SOCKET and SERIAL interface by sending *STB? query.
		In that case however, command cannot be a query.
		Returns the last read Status Byte value."""
		timeout_secs = timeout / 1000
		self.clear_before_read()
		if command.endswith(self._term_char):
			command = command.rstrip(self._term_char)
		self.write(command + ';*OPC')
		# Use catch to return the VISA Timeout back
		start = time.time()
		# STB polling loop
		while True:
			stb = self._read_stb()
			elapsed = self._polling_delay(start)
			if elapsed > timeout_secs:
				self._narrow_down_opc_tout_error(command, is_query, timeout)
			if end_mask & stb:
				break
		return stb

	def _write_and_poll_stb_non_vxi(self, command: str, timeout: int, end_mask: StatusByte) -> StatusByte:
		"""Queries Status Byte Register (*STB?) and ends if the ESB bit (5) is set to 1.
			The command must not be a query. Also works with the SOCKET and SERIAL interface.
			Returns the last read Status Byte value."""
		timeout_secs = timeout / 1000
		self.clear_before_read()
		if command.endswith(self._term_char):
			command = command.rstrip(self._term_char)
		self.write(command + ';*OPC')
		start = time.time()
		# STB polling loop
		while True:
			stb = self._query_stb()
			elapsed = self._polling_delay(start)
			if elapsed > timeout_secs:
				InstrumentErrors.throw_opc_tout_exception(self.opc_timeout, timeout)
			if stb & end_mask:
				break
		return stb

	def _narrow_down_opc_tout_error(self, command: str, is_query: bool, timeout: int) -> None:
		"""Called by the _write_and_poll_stb_vxi when the timeout expires.
		The method tries to closer identify the cause of the timeout."""
		stb = self._read_stb()
		timeout = self._resolve_opc_timeout(timeout)
		if is_query:
			if stb & StatusByte.error_queue_not_empty:
				self.clear()
				context = f"Query '{command.strip()}' with OPC Wait resulted in timeout. OPC Timeout is set to {timeout} ms. Additionally, "
				InstrumentErrors.assert_no_instrument_status_errors(self.resource_name, self.query_all_syst_errors(), context, first_exc=InstrumentErrors.TimeoutException)
			InstrumentErrors.throw_opc_tout_exception(self.opc_timeout, timeout, f"Query '{command.strip()}'.")
		else:
			if stb & StatusByte.error_queue_not_empty:
				self.clear()
				context = f"Command '{command.strip()}' with OPC Wait resulted in timeout. OPC Timeout is set to {timeout} ms. Additionally, "
				InstrumentErrors.assert_no_instrument_status_errors(self.resource_name, self.query_all_syst_errors(), context, first_exc=InstrumentErrors.TimeoutException)
			InstrumentErrors.throw_opc_tout_exception(self.opc_timeout, timeout, f"Command '{command.strip()}'.")

	def _narrow_down_io_tout_error(self, context: str, visa_timeout: int = 0) -> None:
		"""Called internally after IOTimeoutException can narrow down the error to more specific exception.
		You can define the visa_timeout value for the error message. Otherwise the current visa_timeout is reported."""
		if self.vxi_capable:
			stb = self._read_stb()
		else:
			# Non-Vxi session
			old_tout = self.visa_timeout
			try:
				self.visa_timeout = 500
				stb = self._query_stb()
			finally:
				self.visa_timeout = old_tout
		if visa_timeout <= 0:
			visa_timeout = self.visa_timeout
		context = context + f'VISA Timeout error occurred ({visa_timeout} milliseconds)'
		if stb & StatusByte.error_queue_not_empty:
			InstrumentErrors.assert_no_instrument_status_errors(self.resource_name, self.query_all_syst_errors(), context + ' and ...', first_exc=InstrumentErrors.TimeoutException)
		# In case the previous exception is not thrown
		raise InstrumentErrors.TimeoutException(context)

	def _polling_delay(self, start):
		"""Generates progressive polling delay."""

		elapsed = time.time() - start
		if self._opc_wait_mode == WaitForOpcMode.stb_poll:
			if elapsed < 0.01:
				return elapsed
			if elapsed < 0.1:
				time.sleep(0.005)
				return elapsed
			if elapsed < 1:
				time.sleep(0.02)
				return elapsed
			if elapsed < 5:
				time.sleep(0.05)
				return elapsed
			if elapsed < 10:
				time.sleep(0.1)
				return elapsed
			if elapsed < 50:
				time.sleep(0.5)
				return elapsed
			time.sleep(1)
		elif self._opc_wait_mode == WaitForOpcMode.stb_poll_slow:
			if elapsed < 0.01:
				time.sleep(0.001)
				return elapsed
			if elapsed < 1:
				time.sleep(0.02)
				return elapsed
			if elapsed < 5:
				time.sleep(0.1)
				return elapsed
			if elapsed < 10:
				time.sleep(0.2)
				return elapsed
			if elapsed < 20:
				time.sleep(0.5)
				return elapsed
			time.sleep(1)
		elif self._opc_wait_mode == WaitForOpcMode.stb_poll_superslow:
			if elapsed < 1:
				time.sleep(0.1)
				return elapsed
			if elapsed < 10:
				time.sleep(0.5)
				return elapsed
			if elapsed < 20:
				time.sleep(1)
				return elapsed
			time.sleep(2)

		return elapsed

	@staticmethod
	def _parse_err_query_response(response: str) -> Tuple[int, str]:
		"""
		Parses entered response string to Tuple(code, message).
		E.g.: response = '-110,"Command error"' returns: (-110,'Command error')
		"""
		m = re.match(r'(-?[\d]+).*?"(.*)"', response)
		code = 0
		if m:
			try:
				code = int(m.group(1))
			except ValueError:
				pass
			return code, m.group(2)
		else:
			return code, response

	def query_syst_error(self) -> Tuple[int, str] or None:
		"""Returns one response to the SYSTEM:ERROR? query.
		The response is a Tuple of (code: int, message: str)"""
		error = self._query_str_no_events('SYST:ERR?')
		if error.startswith('0,'):
			return None
		return self._parse_err_query_response(error.strip())

	def query_all_syst_errors(self) -> List[Tuple[int, str]] or None:
		"""Returns all errors in the instrument's error queue.
		If no error is detected, the return value is None."""
		errors = []
		while True:
			entry = self.query_syst_error()
			if entry is None:
				break
			errors.append(entry)
			if len(errors) > 50:
				# Safety stop
				errors.append('query_all_syst_errors - max limit 50 of SYST:ERR? sent.')
				break
		if len(errors) == 0:
			return None
		else:
			return errors

	def _query_stb(self) -> StatusByte:
		"""Sends *STB? query and reads the result."""
		return StatusByte(int(self._query_str_no_events('*STB?')))

	def _read_stb(self) -> StatusByte:
		"""Calls viReadStb and returns the result."""
		return StatusByte(self._session.read_stb())

	def clear_before_read(self) -> None:
		"""Clears IO buffers and the ESR register before reading/writing responses synchronized with *OPC."""

		# For NRP-Z sessions, skip this completely
		if self.is_rsnrp_session():
			return

		if not self.vxi_capable:
			# Non-Vxi session must use *CLS in any case
			self.write('*CLS')
			correct = False
			opc = self._query_str_no_events('*OPC?')
			repeat = 0
			while not correct:
				if len(opc) <= 2:
					opc = opc.strip()
					correct = opc == '0' or opc == '1'
				if not correct:
					# Read again with a small VISA timeout
					opc = self._read_str_timed(5, True)
				repeat += 1
				if repeat > 10:
					break

		stb = self._query_stb()
		condition = StatusByte.error_queue_not_empty | StatusByte.message_available | StatusByte.event_status_byte
		if not stb & condition:
			return
		repeat = 0
		# Loop more times to clear the status subsystem
		while stb & condition:
			if stb & StatusByte.error_queue_not_empty:
				self.write('*CLS')
				_ = self.query_all_syst_errors()
			if stb & StatusByte.message_available:
				# Clear output buffer
				self._flush_junk_data()
			if stb & StatusByte.event_status_byte:
				# OPC or error bits in the ESR
				self.write('*CLS')
				self.query_and_clear_esr()
			# Check if the status byte value changed
			previous_stb = stb
			stb = self._query_stb()
			if stb == previous_stb:
				repeat += 1
				if repeat > 10:
					raise RsInstrException(f"Cannot clear the instrument's status subsystem. Status Byte: '{stb}'")

	def _flush_junk_data(self) -> None:
		"""Reads junk bytes to clear the instrument's output buffer."""
		if self.read_delay > 0:
			time.sleep(self.read_delay / 1000)
		self._read_unknown_len(StreamWriter.as_bin_var(), False)

	def clear(self) -> None:
		"""Perform VISA viClear conditionally based on the instrument settings."""
		perform_all = ViClearMode.execute_on_all in self._viclear_exe_mode
		perform = False
		if perform_all:
			perform = True
		else:
			# Perform on all is blocked, use the SessionKind to decide
			if self._interface_type == SessionKind.gpib:
				perform = ViClearMode.execute_on_gpib in self._viclear_exe_mode

			elif self._interface_type == SessionKind.serial:
				perform = ViClearMode.execute_on_serial in self._viclear_exe_mode

			elif self._interface_type == SessionKind.socket:
				perform = ViClearMode.execute_on_socket in self._viclear_exe_mode

			elif self._interface_type == SessionKind.usb:
				perform = ViClearMode.execute_on_usb in self._viclear_exe_mode

			elif self._interface_type == SessionKind.vxi11:
				perform = ViClearMode.execute_on_tcpvxi in self._viclear_exe_mode

		if not perform:
			return

		if ViClearMode.ignore_error in self._viclear_exe_mode:
			# noinspection PyBroadException
			try:
				self._session.clear()
			except Exception:
				pass
		else:
			self._session.clear()

	def is_connection_active(self) -> bool:
		"""Returns true, if the VISA connection is active and the communication with the instrument still works.
		This is achieved by:
		- checking the session property timeout
		- sending the *IDN? query"""
		if self._session is None:
			return False
		# noinspection PyBroadException
		try:
			old_tout = self.visa_timeout
			self.visa_timeout = 2000
			self.write('*IDN?')
			_ = self._read_str_no_events()
			self.visa_timeout = old_tout
			return True
		except Exception:
			return False

	def _write_and_wait_for_opc(self, command: str, is_query: bool, timeout: int) -> StatusByte:
		"""Internal method to synchronise a command with OPC timeout.
		Timeout value 0 means the OPC timeout is used."""
		timeout = self._resolve_opc_timeout(timeout)

		if command.endswith(self._term_char):
			command = command.rstrip(self._term_char)
		if is_query:
			InstrumentErrors.assert_query_has_qmark(command, 'Query with OPC')
		else:
			InstrumentErrors.assert_cmd_has_no_qmark(command, 'Write with OPC')

		if self._opc_wait_mode == WaitForOpcMode.opc_query:
			if is_query:
				raise RsInstrException('Sending a query with OpcQuery synchronization is not possible')
			stb = self._write_and_query_opc(command, timeout)
		else:
			# STB polling
			end_stb_mask = StatusByte.error_queue_not_empty | StatusByte.event_status_byte
			if is_query:
				end_stb_mask |= StatusByte.message_available
			if self.vxi_capable:
				stb = self._write_and_poll_stb_vxi(command, is_query, timeout, end_stb_mask)
			else:
				stb = self._write_and_poll_stb_non_vxi(command, timeout, end_stb_mask)

		return stb

	def _write_and_query_opc(self, cmd: str, timeout: int) -> StatusByte:
		"""Internal method to write a command followed by query_opc().
		Used for opc-synchronization if the mode is set to WaitForOpcMode.opc_query or the session is not-vxi.
		Timeout value 0 means the OPC timeout is used."""
		old_tout = self.visa_timeout

		# Change VISA Timeout if necessary
		if old_tout != timeout:
			self.visa_timeout = timeout
		try:
			# try-catch to set the VISA timeout back
			self.write(cmd)
			self.query_opc()
		finally:
			if old_tout != timeout:
				self.visa_timeout = old_tout
		return self._query_stb()

	def write(self, cmd: str) -> None:
		"""Writes command to the instrument."""
		if self.write_delay > 0:
			time.sleep(self.write_delay / 1000)
		add_tc = False
		if self._assure_write_with_tc and not cmd.endswith(self._term_char):
			add_tc = True
		if add_tc:
			self._session.write(cmd + self._term_char)
		else:
			self._session.write(cmd)

	def _read_unknown_len(self, stream: StreamWriter, allow_chunk_events: bool, prepend_data: AnyStr = None) -> None:
		"""Reads data of unknown length to the provided WriteStream.
		The read is performed in an incremental chunk steps to optimize memory use (for NRP-Z session it is set to fixed self._data_chunk_size):
			- The first read is performed with the fixed size of 1024 bytes
			- The 2nd one reads 64 kBytes
			- The 3rd one reads 128 kBytes
			- The 4th one reads 256 kBytes and so on, with the max cap of self._data_chunk_size
		:param stream: [StreamWriter] target for the read data
		:param allow_chunk_events: [bool] if True, the method can send the chunk_events. If False, sending events is blocked.
		:param prepend_data: Optional[bytes or string] You can prepend this data to the beginning. It will be considered part of the first chunk read
		:return: read data [bytes or string], depending on the parameter binary."""
		with self._session.ignore_warning(pyvisa.constants.StatusCode.success_max_count_read):
			if prepend_data and isinstance(prepend_data, str):
				prepend_data = prepend_data.encode('utf-8')
			chunk_ix = 0
			eot = False
			while not eot:
				if self.is_rsnrp_session():
					chunk_size = self._data_chunk_size
				else:
					if chunk_ix == 0:
						# First read, set 1024 bytes read size
						chunk_size = 1024
					elif chunk_ix == 1:
						chunk_size = 65536
					else:
						chunk_size *= 2
				if chunk_size > self._data_chunk_size:
					chunk_size = self._data_chunk_size
				chunk, self.last_status = self._session.visalib.read(self._session.session, chunk_size)
				if chunk_ix == 0 and prepend_data:
					chunk = prepend_data + chunk
				eot = not self._last_status_more_data_available()
				if not stream.binary:
					chunk = chunk.decode('utf-8')
					if eot:
						chunk = chunk.rstrip(self._term_char)
				stream.write(chunk)
				if self.on_read_chunk_handler and allow_chunk_events:
					total_size = len(stream) if eot is True else None
					event_args = EventArgsChunk(stream.binary, chunk_ix, len(chunk), total_size, len(stream), eot, None, chunk if self.io_events_include_data else None)
					self.on_read_chunk_handler(event_args)
				chunk_ix += 1

	def _last_status_more_data_available(self):
		"""Returns True, if the last status signalled that more data is available"""
		return self.last_status == pyvisa.constants.StatusCode.success_max_count_read

	def _read_str_no_events(self) -> str:
		"""Reads response from the instrument. The response is then trimmed for trailing LF. \n
		Sending of any read events is blocked."""
		if self.read_delay > 0:
			time.sleep(self.read_delay / 1000)
		stream = StreamWriter.as_string_var()
		self._read_unknown_len(stream, False)
		return stream.content

	def _query_str_no_events(self, query: str) -> str:
		"""Queries the instrument and reads the response as string.
		The length of the string is not limited. The response is then trimmed for trailing LF.
		Sending of any read events is blocked. Use this method for all the service VisaSession queries."""
		response = ''
		self.write(query)
		try:
			response = self._read_str_no_events()
		except pyvisa.VisaIOError:
			self._narrow_down_io_tout_error(f"Query '{query.rstrip(self._term_char)}' - ")
		return response

	def _query_str_no_events_timed(self, query: str, timeout: int, suppress_read_tout: bool = False) -> str:
		"""Queries the instrument and reads the response as string.
		The entered timeout sets the VISA timeout just for this call. You can suppress the timeout error.
		The length of the string is not limited. The response is then trimmed for trailing LF.
		Sending of any read events is blocked. Use this method for all the service VisaSession queries."""
		response = ''
		self.write(query)
		try:
			response = self._read_str_timed(timeout, suppress_read_tout)
		except pyvisa.VisaIOError:
			self._narrow_down_io_tout_error(f"Query with timeout {timeout} ms '{query.rstrip(self._term_char)}' - ", timeout)
		return response

	def _read_str_timed(self, timeout: int, suppress_read_tout: bool = False) -> str:
		"""Reads response from the instrument with a VISA timeout temporarily set for the read.
		The VISA timeout is set back to the previous value before the method finishes even if an exception occurs.
		Sending of any read events is blocked."""
		old_visa_tout = self.visa_timeout
		if suppress_read_tout:
			try:
				if timeout != old_visa_tout:
					self.visa_timeout = timeout
				data = self._read_str_no_events()
				return data
			except TimeoutError:
				pass
			finally:
				self.visa_timeout = old_visa_tout
		else:
			try:
				if timeout != old_visa_tout:
					self.visa_timeout = timeout
				data = self._read_str_no_events()
				return data
			finally:
				self.visa_timeout = old_visa_tout

	def _read_str(self) -> str:
		"""Reads response from the instrument. The response is then trimmed for trailing LF."""
		if self.read_delay > 0:
			time.sleep(self.read_delay / 1000)
		stream = StreamWriter.as_string_var()
		self._read_unknown_len(stream, True)
		return stream.content

	def query_str(self, query: str) -> str:
		"""Queries the instrument and reads the response as string.
		The length of the string is not limited. The response is then trimmed for trailing LF."""
		response = ''
		self.write(query)
		try:
			response = self._read_str()
		except pyvisa.VisaIOError:
			self._narrow_down_io_tout_error(f"Query '{query.rstrip(self._term_char)}' - ")
		return response

	def query_str_no_tout_err(self, query: str, tout: int) -> str:
		"""Same as query_str, but you can set the timeout just for this one call.
		If the timeout exception occurs, it is suppressed and the method returns Null"""
		response = None
		old_tout = self.visa_timeout
		try:
			self.visa_timeout = tout
			response = self.query_str(query)
		except (pyvisa.VisaIOError, InstrumentErrors.StatusException):
			pass
		finally:
			self.visa_timeout = old_tout
		return response

	def write_with_opc(self, command: str, timeout: int = None) -> None:
		"""Sends command with OPC-sync.
		If you do not provide timeout, the method uses current opc_timeout."""
		self._write_and_wait_for_opc(command, False, timeout)

	def query_str_with_opc(self, query: str, timeout: int = None, context: str = 'Query string with OPC') -> str:
		"""Query string with OPC synchronization.
		The response is trimmed for any trailing LF.
		If you do not provide timeout, the method uses current opc_timeout."""
		timeout = self._resolve_opc_timeout(timeout)
		if self.vxi_capable and self._opc_wait_mode is not WaitForOpcMode.opc_query:
			# For Vxi session, use the STB poll or SRQ wait and then read the response
			stb = self._write_and_wait_for_opc(query, True, timeout)
			self._check_msg_available_after_opc_wait(stb, query, timeout, context)
			response = self._read_str()
		else:
			# For non-Vxi sessions, use the longer VISA Timeout without the *OPC?
			# Same is valid for WaitForOpcMode.OpcQuery
			InstrumentErrors.assert_query_has_qmark(query, 'Query with VISA timeout')
			self.write(query)
			old_tout = self.visa_timeout
			# Change VISA Timeout if necessary
			if old_tout != timeout:
				self.visa_timeout = timeout
			try:
				# try-catch to set the VISA timeout back
				response = self._read_str()
				if self._opc_wait_mode is WaitForOpcMode.opc_query:
					self.query_opc()
			finally:
				if old_tout != timeout:
					self.visa_timeout = old_tout

		return response

	def query_opc(self, timeout: int = 0) -> bool:
		"""Sends *OPC? query and reads the result.
		If you define timeout > 0, the VISA timeout is set to that value just for this method call."""
		if self.disable_opc_query:
			return True
		if timeout > 0:
			response = self._query_str_no_events_timed('*OPC?', timeout)
		else:
			response = self._query_str_no_events('*OPC?')
		return Conv.str_to_bool(response)

	def query_and_clear_esr(self) -> int:
		"""Sends *ESR? query and reads the result."""
		response = self._query_str_no_events('*ESR?')
		return int(response)

	def _check_msg_available_after_opc_wait(self, stb: StatusByte, query: str, timeout: int, context: str) -> None:
		"""Used internally after _StbPolling() to check if the message is available.
		Throws an exception in case of MAV not available."""
		if not self.vxi_capable:
			return
		if stb & StatusByte.message_available:
			return
		# Message not available
		context = context + f" Query '{query.rstrip(self._term_char)}'"
		if stb & StatusByte.error_queue_not_empty:
			# Instrument reports an error
			InstrumentErrors.assert_no_instrument_status_errors(self.resource_name, self.query_all_syst_errors(), context)
		else:
			# Sometimes even if the StatusByte.MessageAvailable is false, the message is available.
			# Try to read the STB again
			stb = self._read_stb()
			if not stb & StatusByte.event_status_byte:
				# Instrument did not respond within the defined time
				InstrumentErrors.throw_opc_tout_exception(self.opc_timeout, timeout, f'{context} No response from the instrument.')

	def error_in_error_queue(self) -> bool:
		"""Returns true, if error queue contains at least one error."""
		stb = self._query_stb()
		if stb & StatusByte.error_queue_not_empty:
			return True
		return False

	def reset_ese_sre(self) -> None:
		"""Resets the status of ESE and SRE registers to default values."""
		self._set_regs_ese_sre(self._opc_wait_mode)

	def write_bin_block(self, cmd: str, data_stream: StreamReader) -> None:
		"""Writes all the payload as binary data block to the instrument.
		The binary data header is added at the beginning of the transmission automatically.
		:param cmd: [str] SCPI command with which to send the data
		:param data_stream: [StreamReader] data provider for the payload"""
		data_size = len(data_stream)
		len_str = f'{data_size}'
		cmd = cmd.rstrip(self._term_char)
		if '#' in cmd:
			raise RsInstrException(
				f"Command '{cmd}' must be provided without the binary data header. "
				f"The method 'write_bin_block' composes and prepends the binary data header automatically.")
		if data_size <= self._std_bin_block_header_max_len:
			# Standard bin data header for sizes below 1E9 bytes, e.g.: '#512345'
			cmd_plus_header = f'{cmd}#{len(len_str)}{len_str}'.encode('utf-8')
		else:
			# Big sizes bin data header: e.g.: '#(3000000000)'
			cmd_plus_header = f'{cmd}#({len_str})'.encode('utf-8')

		if data_size <= self._data_chunk_size:
			# Write all in one step
			full_chunk = data_stream.read_as_binary()
			write_buf = cmd_plus_header + full_chunk
			if self._add_term_char_to_write_bin_block:
				write_buf += self._term_char_bin
			self._session.write_raw(write_buf)
			# Event sending
			if self.on_write_chunk_handler:
				event_args = EventArgsChunk(True, 0, data_size, data_size, data_size, True, 1, full_chunk if self.io_events_include_data else None)
				self.on_write_chunk_handler(event_args)
		else:
			# Write in chunks
			try:
				# Use finally to set the session send_end back to True
				self._session.send_end = False
				total_chunks = calculate_chunks_count(data_size, self._data_chunk_size)
				chunk_ix = 0
				if self.write_delay > 0:
					time.sleep(self.write_delay / 1000)
				# Write bin header
				self._session.write_raw(cmd_plus_header)
				# Write chunks
				while True:
					if len(data_stream) > self._data_chunk_size:
						#  Not the last segment
						chunk = data_stream.read_as_binary(self._data_chunk_size)
						self._session.write_raw(chunk)
						# Event sending
						if self.on_write_chunk_handler:
							event_args = EventArgsChunk(
								True, chunk_ix, self._data_chunk_size, data_size, data_size - len(data_stream), False, total_chunks, chunk if self.io_events_include_data else None)
							self.on_write_chunk_handler(event_args)
					else:
						# Last segment, indicate end of message again
						chunk = data_stream.read_as_binary()
						if self._add_term_char_to_write_bin_block:
							# Append LF
							self._session.write_raw(chunk)
							self._session.send_end = True
							self._session.write_raw(self._term_char_bin)
						else:
							self._session.send_end = True
							self._session.write_raw(chunk)

						# Event sending
						if self.on_write_chunk_handler:
							event_args = EventArgsChunk(True, chunk_ix, len(chunk), data_size, data_size, True, total_chunks, chunk if self.io_events_include_data else None)
							self.on_write_chunk_handler(event_args)
						break
					chunk_ix += 1
			finally:
				self._session.send_end = True

	def _parse_bin_data_header(self, exc_if_not_bin: bool) -> Tuple[ReadDataType, str, int]:
		"""Parses the binary data block and returns the expected length of the following data block. \n
		:param exc_if_not_bin: [bool] if True, the method throws exception in case the data is not binary.
		:return: read_data_type: [ReadDataType], parsed_header: [string], bin_data_len: [integer]"""
		length = -1
		if self.read_delay > 0:
			time.sleep(self.read_delay / 1000)

		char: AnyStr = self._session.read_bytes(1, break_on_termchar=True)
		if char == b'#':
			# binary transfer
			char = self._session.read_bytes(1, break_on_termchar=True)
			if char == b'0':
				data_type = ReadDataType.bin_unknown_len
				return data_type, '#0', -1
			if char == b'(':
				# format for big lengths i.e. > 1E9 bytes: '#(1234567890123)...'
				data_type = ReadDataType.bin_known_len
				len_str = (self.read_up_to_char(b')', 100)[:-1]).decode('utf-8')
				whole_hdr = '#(' + len_str + ')'
				length = int(len_str)
				return data_type, whole_hdr, length

			# classic format for < 1E9 bytes: '#9123456789...'
			data_type = ReadDataType.bin_known_len
			len_of_len = int(char)
			len_str = self._session.read_bytes(len_of_len).decode('utf-8')
			length = int(len_str)
			whole_hdr = '#' + char.decode('utf-8') + len_str
			return data_type, whole_hdr, length

		data_type = ReadDataType.ascii
		if char == self._term_char_bin:
			data_type = ReadDataType.null
		if self.vxi_capable:
			# For Vxi session, to be sure, check whether there are more chars in the read buffer
			stb = self._read_stb()
			if stb & StatusByte.message_available:
				data_type = ReadDataType.ascii
		whole_hdr = char.decode('utf-8')
		if exc_if_not_bin:
			if data_type == ReadDataType.null:
				InstrumentErrors.throw_bin_block_unexp_resp_exception(self.resource_name, self._term_char)
			# Read 20 more characters to compose a better exception message
			whole_hdr += self.read_up_to_char(self._term_char_bin, 20).decode('utf-8')
			if self.last_status == pyvisa.constants.StatusCode.success_max_count_read:
				self._flush_junk_data()
			InstrumentErrors.throw_bin_block_unexp_resp_exception(self.resource_name, whole_hdr)
		return data_type, whole_hdr, length

	def read_bin_block(self, stream: StreamWriter, exc_if_not_bin: bool) -> None:
		"""Reads binary data block to the provided stream. \n
		:param stream: [StreamWriter] target for the read data. Can be string, bytes, or a file
		:param exc_if_not_bin: if True, the method throws exception if the received data is not binary"""
		data_type, header, length = self._parse_bin_data_header(exc_if_not_bin)
		if data_type == ReadDataType.ascii:
			stream.switch_to_string_data()
			self._read_unknown_len(stream, True, header)
		elif data_type == ReadDataType.null:
			# No data, consider it ASCII. Change the stream type to ASCII and return empty string
			stream.switch_to_string_data()
		elif data_type == ReadDataType.bin_unknown_len:
			if not self.vxi_capable:
				raise RsInstrException(f'Non-Vxi11 sessions can not read binary data block of unknown length.')
			self._read_unknown_len(stream, True)
		elif length == 0:
			self._flush_junk_data()
		else:
			self._read_bin_block_known_len(stream, length)

	def _read_bin_block_known_len(self, stream: StreamWriter, length: int) -> None:
		"""Reads binary data of defined length. All remaining data above the length are disposed of. \n
		:param stream: [StreamWriter] target for the read data. Can be string, bytes, or a file
		:param length: [int] expected length of the data"""
		# Use try-catch to switch the termination character back ON in case of an exception (for non-Vxi sessions)
		try:
			# Binary transmission, for non-Vxi session, set the termination character to OFF
			if not self.vxi_capable:
				self._session.read_termination = False
			# Binary data of known length
			left_to_read = length
			self.last_status = pyvisa.constants.StatusCode.success
			with self._session.ignore_warning(pyvisa.constants.StatusCode.success_max_count_read):
				chunk_ix = 0
				total_chunks = calculate_chunks_count(length, self._data_chunk_size)
				while len(stream) < length:
					chunk_size = min(self._data_chunk_size, left_to_read)
					chunk, self.last_status = self._session.visalib.read(self._session.session, chunk_size)
					left_to_read -= len(chunk)
					stream.write(chunk)
					if self.on_read_chunk_handler:
						event_args = EventArgsChunk(True, chunk_ix, chunk_size, length, len(stream), left_to_read == 0, total_chunks, chunk if self.io_events_include_data else None)
						self.on_read_chunk_handler(event_args)
					chunk_ix += 1
			if self._last_status_more_data_available():
				if not self.vxi_capable:
					self._session.read_termination = self._term_char
				self._flush_junk_data()
		finally:
			# Make sure that in any case the self._session.read_termination is ON again for non-Vxi sessions
			if not self.vxi_capable:
				self._session.read_termination = self._term_char

	def query_bin_block(self, query: str, stream: StreamWriter, exc_if_not_bin: bool = True) -> None:
		"""Query binary data block and returns it as byte data. \n
		:param query: [str] query to send to the instrument
		:param stream: [StreamWriter] target for the read data. Can be string, bytes, or a file
		:param exc_if_not_bin: [Boolean] if True, the method throws exception if the received data is not binary"""
		self.write(query)
		self.read_bin_block(stream, exc_if_not_bin)
		return

	def query_bin_block_with_opc(self, query: str, stream: StreamWriter, exc_if_not_bin: bool = True, timeout: int = None) -> None:
		"""Query binary data block with OPC and returns it as byte data.
		:param query: [str] query to send to the instrument
		:param stream: [StreamWriter] target for the read data. Can be string, bytes, or a file
		:param exc_if_not_bin: [Boolean] if True, the method throws exception if the received data is not binary
		:param timeout: Optional[Integer] timeout for the operation. If you skip it, the method uses the current opc timeout."""
		timeout = self._resolve_opc_timeout(timeout)
		if self.vxi_capable and self._opc_wait_mode != WaitForOpcMode.opc_query:
			# For Vxi session, use the STB poll and read the response
			stb = self._write_and_wait_for_opc(query, True, timeout)
			self._check_msg_available_after_opc_wait(stb, query, timeout, 'query_bin_block_with_opc')
			self.read_bin_block(stream, exc_if_not_bin)
		else:
			# For non-Vxi session, use the longer VISA Timeout without the *OPC
			InstrumentErrors.assert_query_has_qmark(query, 'query_bin_block_with_opc')
			self.write(query)
			old_visa_timeout = self.visa_timeout
			# Change VISA Timeout if necessary
			if old_visa_timeout != timeout:
				self.visa_timeout = timeout
			try:
				# try-catch to set the VISA timeout back
				self.read_bin_block(stream, exc_if_not_bin)
				if self._opc_wait_mode == WaitForOpcMode.opc_query:
					self.query_opc()
			finally:
				# Change VISA Timeout back if necessary
				if old_visa_timeout != timeout:
					self.visa_timeout = old_visa_timeout

	def read_up_to_char(self, stop_chars: bytes, max_cnt: int) -> bytes:
		"""Reads until one of the stop_chars is read or the max_cnt is reached, or EOT is detected.
		Returns the read data including the stop character."""
		response = b''
		for i in range(max_cnt):
			char, self.last_status = self._session.visalib.read(self._session.session, 1)
			response += char
			if char in stop_chars:
				break
			if self.last_status != pyvisa.constants.StatusCode.success_max_count_read:
				break
		return response

	def get_session_handle(self) -> object:
		"""Returns the underlying pyvisa session."""
		return self._session

	def close(self) -> None:
		"""Closes the Visa session.
		If the object was created with the direct session input, the session is not closed."""
		if not self.reusing_session:
			self._session.close()

	# Events


class EventArgsChunk:
	"""Event arguments for chunk io event."""

	def __init__(
			self,
			binary: bool,
			chunk_ix: int,
			chunk_size: int,
			total_size: int,
			transferred_size: int,
			end_of_transfer: bool,
			total_chunks: int or None,
			data: AnyStr = None):

		self.binary = binary
		self.chunk_ix = chunk_ix
		self.total_chunks = total_chunks
		self.chunk_size = chunk_size
		self.transferred_size = transferred_size
		self.total_size = total_size
		self.end_of_transfer = end_of_transfer
		self.data = data

	def __str__(self):
		if self.binary:
			type_info = 'binary'
		else:
			type_info = 'ascii'
		if not self.total_chunks:
			chunk_info = f' chunk nr. {self.chunk_ix + 1}'
		elif self.total_chunks > 1:
			chunk_info = f' chunk nr. {self.chunk_ix + 1}/{self.total_chunks}'
		else:
			chunk_info = ' chunk nr. 1/1'
		eot = ' (EOT)' if self.end_of_transfer else ''
		result = \
			f'EventArgsChunk {type_info},{chunk_info}, {size_to_kb_mb_string(self.chunk_size, True)}, ' \
			f'sum {size_to_kb_mb_string(self.transferred_size, True)} / {size_to_kb_mb_string(self.total_size, True) if self.total_size else "<N.A.>"}{eot}.'
		return result
