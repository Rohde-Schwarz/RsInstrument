"""VisaSession for simulated sessions."""

import threading
from typing import Callable, Dict, AnyStr

from . import InstrumentSettings
from .StreamReader import StreamReader
from .StreamWriter import StreamWriter


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class VisaSessionSim(object):
	"""Visa session in simulation mode.
	Provides the properties for the simulation mode.
	Also serves as a cache for the SCPI command values: If you query a SCPI command value, it returns the last set value by that SCPI command."""

	def __init__(self, resource_name: str, settings: InstrumentSettings, direct_session=None):
		self.reusing_session = direct_session is not None
		# noinspection PyTypeChecker
		self._data_chunk_size: int = None
		# noinspection PyTypeChecker
		self._lock: threading.RLock = None

		# Event handlers
		# noinspection PyTypeChecker
		self.on_read_chunk_handler: Callable = None
		"""If assigned a handler, the VisaSession sends it event on each read chunk transfer."""
		# noinspection PyTypeChecker
		self.on_write_chunk_handler: Callable = None
		"""If assigned a handler, the VisaSession sends it event on each write chunk transfer."""
		self.io_events_include_data: bool = False
		"""If true, the VisaSession events sent to on_read_chunk_handler and on_write_chunk_handler contain transferred data."""

		self.manufacturer: str = 'Rohde&Schwarz'
		self.resource_name = resource_name
		self.vxi_capable = True
		self.encoding = settings.encoding  # default encoder between bytes and string

		# Changeable settings
		self.opc_timeout = 10000 if settings.opc_timeout == 0 else settings.opc_timeout
		self.visa_timeout = settings.visa_timeout
		self.data_chunk_size = settings.io_segment_size

		self._last_cmd = None

		# If the return value is written to a cache, this flag signals if it was a cached value
		self.cached_to_stream = False

		# cache command values dictionary
		self._cmd_vals_cache: Dict[str, AnyStr] = {}

		# Decide, whether to create a new thread lock or the existing one from the direct_session
		if direct_session and hasattr(direct_session, 'session_thread_rlock'):
			rlock = direct_session.session_thread_rlock
			if isinstance(rlock, type(threading.RLock())):
				self.assign_lock(rlock)
		if self.get_lock() is None:
			# The existing session did not have a thread lock, assign a new one
			self.assign_lock(threading.RLock())

		if self.reusing_session:
			self.resource_name = direct_session.resource_name

	def assign_lock(self, lock: threading.RLock) -> None:
		"""Assigns the provided thread lock. The lock is only used by the parent class Instrument."""
		self._lock = lock

	def get_lock(self) -> threading.RLock:
		"""Returns the current RLock object."""
		return self._lock

	def _update_cmd_vals_cache(self, cmd: str, param: AnyStr = None) -> None:
		"""Parses out the parameter from the command and stores/updates them in the cache"""
		aux = cmd.split(' ', 1)
		if len(aux) < 2:
			return
		headers = aux[0].strip().lower()
		param = aux[1].strip()
		self._cmd_vals_cache[headers] = param

	def _update_cmd_vals_cache_split(self, cmd: str, param: AnyStr) -> None:
		"""Stores/updates cmd and param in the cache"""
		headers = cmd.strip().lower()
		self._cmd_vals_cache[headers] = param

	def _get_cmd_cached_value(self, cmd: str) -> str or None:
		"""Returns cached parameter to the corresponding command
		Returns None of the command is not found in the cache"""
		aux = cmd.split('?', 1)
		headers = aux[0].strip().lower()
		return self._cmd_vals_cache.get(headers, None)

	def get_last_sent_cmd(self) -> str:
		"""Returns the last commands sent to the instrument"""
		return self._last_cmd

	def is_rsnrp_session(self) -> bool:
		"""Returns True, if the current session is a NRP-Z session"""
		return False

	def query_syst_error(self) -> str or None:
		"""Returns one response to the SYSTEM:ERROR? query."""
		return None

	def query_all_syst_errors(self) -> list or None:
		"""Returns all errors in the instrument's error queue.
		If no error is detected, the return value is None."""
		return None

	def clear_before_read(self) -> None:
		"""Clears IO buffers and the ESR register before reading/writing responses synchronized with *OPC."""
		return

	def clear(self) -> None:
		"""Perform VISA viClear conditionally based on the instrument settings."""
		return

	def clear_status_after_query_with_opc(self) -> bool:
		"""Returns true, if the opc-sync queries require status clearing afterward."""
		return False

	def write(self, cmd: str) -> None:
		"""Writes command to the instrument."""
		self._last_cmd = cmd
		self._update_cmd_vals_cache(cmd)
		return

	def query_str(self, query: str) -> str:
		"""Queries the instrument and reads the response as string.
		The length of the string is not limited. The response is then trimmed for trailing LF."""
		self._last_cmd = query
		cached = self._get_cmd_cached_value(query)
		return 'Simulating' if cached is None else cached

	def write_with_opc(self, cmd: str, timeout: int = None) -> None:
		"""Sends command with OPC-sync.
		If you do not provide timeout, the method uses current opc_timeout."""
		self.write(cmd)

	def query_str_with_opc(self, query: str, timeout: int = None, context: str = 'Query string with OPC') -> str:
		"""Query string with OPC synchronization.
		The response is trimmed for any trailing LF.
		If you do not provide timeout, the method uses current opc_timeout."""
		return self.query_str(query)

	def query_opc(self, timeout: int = 0) -> bool:
		"""Sends *OPC? query and reads the result."""
		return True

	def query_and_clear_esr(self) -> int:
		"""Sends *ESR? query and reads the result."""
		return 0

	def error_in_error_queue(self) -> bool:
		"""Returns true, if error queue contains at least one error."""
		return False

	def reset_ese_sre(self) -> None:
		"""Resets the status of ESE and SRE registers to default values."""
		return

	def write_bin_block(self, cmd: str, data_stream: StreamReader) -> None:
		"""Writes all the payload as binary data block to the instrument.
		The binary data header is added at the beginning of the transmission automatically."""
		self._last_cmd = cmd
		param = data_stream.read()
		self._update_cmd_vals_cache_split(cmd, param)

	def query_bin_block(self, query: str, stream: StreamWriter, exc_if_not_bin: bool = True) -> None:
		"""Query binary data block and returns it as byte data."""
		self._last_cmd = query
		cached = self._get_cmd_cached_value(query)

		if cached is None:
			stream.write(bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 65, 66]))
			self.cached_to_stream = False
		else:
			if isinstance(cached, str):
				stream.switch_to_string_data(self.encoding)
			stream.write(cached)
			self.cached_to_stream = True

	def query_bin_block_with_opc(self, query: str, stream: StreamWriter, exc_if_not_bin: bool = True, timeout: int = None) -> None:
		"""Query binary data block with OPC and returns it as byte data."""
		self.query_bin_block(query, stream)

	def read_up_to_char(self, stop_chars: bytes, max_cnt: int) -> bytes:
		"""Reads until one of the stop_chars is read or the max_cnt is reached, or EOT is detected.
		Returns the read data including the stop character."""
		return b'Simulating'

	def get_session_handle(self) -> object:
		"""Returns the underlying pyvisa session."""
		return f"Simulating session, resource name '{self.resource_name}'"

	def close(self) -> None:
		"""Closes the Visa session.
		If the object was created with the direct session input, the session is not closed."""
		return
