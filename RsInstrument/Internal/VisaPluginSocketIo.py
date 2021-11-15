"""See the docstring for the SocketIo class."""

import socket
import re
from contextlib import contextmanager
from .InstrumentErrors import RsInstrException

# noinspection PyPackageRequirements
import pyvisa


class SocketIo:
	"""Socket IO plugin providing implementations for all the necessary VISA functions. This class does not need the underlying VISA installation."""
	def __init__(self, resource_name: str):
		self.session = socket.socket()
		self.resource_name = resource_name
		m = re.search(r'TCPIP::([^:]+)::([^:]+)::SOCKET', self.resource_name)
		if not m:
			raise RsInstrException(f"SocketIO instrument unsupported resource name. '{self.resource_name}' Supported resource name example: 'TCPIP::192.168.1.100::5025::SOCKET'")
		self.host = m.group(1).strip()
		self.port = int(m.group(2).strip())
		self._read_termination = None
		self._chunk_size = 1024
		self._timeout = 5000
		self.visalib = VisaLib(self)

	def connect(self):
		"""Connects to the server (IP address and port number)"""
		self.session.connect((self.host, self.port))

	# noinspection PyUnresolvedReferences
	@property
	def interface_type(self) -> int:
		"""Returns interface type as integer number (6)"""
		return pyvisa.constants.VI_INTF_TCPIP

	@property
	def resource_class(self) -> str:
		"""Returns resource class as string"""
		return 'SOCKET'

	@property
	def read_termination(self) -> str:
		"""Read termination character"""
		return self._read_termination

	@read_termination.setter
	def read_termination(self, value: str or bool) -> None:
		"""Read termination character. You can set it to False, or a string value"""
		if isinstance(value, bool):
			if value is True:
				raise ValueError("SocketIO read_termination can not be set to True. You have to provide a string value")
			self._read_termination = None
			return
		if isinstance(value, str):
			self._read_termination = value
			return
		raise ValueError(f"SocketIO read_termination invalid type: '{value}'")

	@property
	def chunk_size(self) -> int:
		"""Transfer chunk size"""
		return self._chunk_size

	@chunk_size.setter
	def chunk_size(self, chunk_size: int) -> None:
		"""Transfer chunk size"""
		self._chunk_size = chunk_size

	@property
	def timeout(self) -> int:
		"""Read and Write timeout"""
		return self._timeout

	@timeout.setter
	def timeout(self, timeout: int) -> None:
		"""Read and Write timeout"""
		self._timeout = timeout
		tout_float = float(self._timeout / 1000)
		self.session.settimeout(tout_float)

	def clear(self) -> None:
		"""Clear the buffers"""
		return

	def write(self, cmd: str) -> None:
		"""Writes command as string to the instrument"""
		self.session.send(cmd.encode())

	def write_raw(self, cmd: bytes) -> None:
		"""Writes command as bytes to the instrument"""
		self.session.send(cmd)

	# noinspection PyUnusedLocal
	def read_bytes(self, count: int, **kwargs) -> bytes:
		"""Reads count bytes"""
		data, status = self.visalib.read(self.session, count)
		return data

	# noinspection PyUnusedLocal
	@contextmanager
	def ignore_warning(self, filter_value: int) -> None:
		"""Context property with no effect for the socket connection"""
		try:
			yield None
		finally:
			# Code to release resource, e.g.:
			pass

	def close(self) -> None:
		"""Closes the socket connection"""
		self.session.close()


class VisaLib:
	"""Implementation of the pyvisa's VisaLib providing the method read()"""
	def __init__(self, socket_io: SocketIo):
		self._socket_io = socket_io

	def __str__(self):
		return "SocketIO"

	# noinspection PyUnresolvedReferences
	def read(self, session, chunk_size: int):
		"""Reads bytes from the instrument to the maximum size of chunk_size.
		Returns Tuple of bytes and status"""
		term_char_detected = False
		read_len = 0
		chunk = bytes()

		try:
			while True:
				to_read_len = chunk_size - read_len
				if to_read_len <= 0:
					break
				data = session.recv(to_read_len)
				chunk += data
				read_len += len(data)

				if self._socket_io.read_termination is not None:
					# Read termination character is ON, look for it and stop the reading if found
					term_char = self._socket_io.read_termination.encode()
					if term_char in data:
						term_char_ix = data.index(term_char)
						read_len = term_char_ix + 1
						term_char_detected = True
						break
					else:
						pass

		except socket.timeout:
			raise pyvisa.VisaIOError(pyvisa.constants.VI_ERROR_TMO)

		if read_len < chunk_size:
			# Less than required data arrived, no more available
			more_data_available = False
		else:
			# MaxCount data arrived, possibly more data available
			if self._socket_io.read_termination is not None:
				more_data_available = not term_char_detected
			else:
				more_data_available = True

		return_code = pyvisa.constants.StatusCode.success_max_count_read if more_data_available else pyvisa.constants.StatusCode.success
		return chunk, return_code


class ResourceManager:
	"""Implementation of the VISA's Resource Manager."""
	def __init__(self):
		self.VisaManufacturerName = "SocketIO"
		self.connection = None

	def open_resource(self, resource_name: str) -> SocketIo:
		"""Creates new Socket connection"""
		self.connection = SocketIo(resource_name)
		self.connection.connect()
		return self.connection
