"""See the docstring for the StreamReader class."""

from enum import Enum
from os import path
from typing import AnyStr

from .Utilities import size_to_kb_mb_string
from .InstrumentErrors import RsInstrException


class Type(Enum):
	"""Defines type of the stream - variable or file."""
	Variable = 1
	File = 2


class StreamReader:
	"""Lightweight stream reader implementation. Data source can be: \n
	- variable
	- file"""

	def __init__(self, binary: bool, source: Type, data: AnyStr):
		"""Initializes StreamReader instance.\n
		:param binary: True: Binary data, False: ASCII data
		:param source: Source type for the stream. Variable / File
		:param data: Depending on the 'binary' and 'source':
		For source type Variable the data must be either bytes() or str
		For source type File data must be string with existing file path."""
		self._source = source
		self._binary = binary
		self._start_ptr = 0
		self._read_len = 0

		if self._source == Type.Variable:
			if self._binary:
				assert isinstance(data, bytes), f'Data must be of bytes type. Actual type: {type(data)}'
			else:
				assert isinstance(data, str), f'Data must be of string type. Actual type: {type(data)}'
			self._data = data
			self._full_len = len(self._data)
		elif self._source == Type.File:
			assert isinstance(data, str), f'Data must be of string type (file path). Actual type: {type(data)}'
			if not path.isfile(data):
				raise RsInstrException(f'File does not exist. File path: {data}')
			self.file_path = data
			self._data = open(self.file_path, 'rb' if self._binary else 'r')
			self._full_len = path.getsize(self.file_path)
		else:
			raise RsInstrException(f'StreamReader unknown type {source}')

	@classmethod
	def as_bin_var(cls, data: bytes) -> 'StreamReader':
		"""Creates new StreamReader from bytes.
		:param data: [bytes] data for the stream."""
		return cls(True, Type.Variable, data)

	@classmethod
	def as_string_var(cls, data: str) -> 'StreamReader':
		"""Creates new StreamReader from string.
		:param data: [str] data for the stream."""
		return cls(False, Type.Variable, data)

	@classmethod
	def as_bin_file(cls, file_path: str) -> 'StreamReader':
		"""Creates new StreamReader from binary file. The file must exist at this time.
		:param file_path: [str] Path to the file."""
		return cls(True, Type.File, file_path)

	@classmethod
	def as_text_file(cls, file_path: str) -> 'StreamReader':
		"""Creates new StreamReader from text file. The file must exist at this time.
		:param file_path: [str] Path to the file."""
		return cls(False, Type.File, file_path)

	def __str__(self):
		if self._source == Type.Variable:
			mode = 'binary' if self._binary else 'string'
			return f'StreamReader {mode} data, full size {size_to_kb_mb_string(self._full_len, True)}, remaining size {size_to_kb_mb_string(len(self), True)}'
		if self._source == Type.File:
			mode = 'binary' if self._binary else 'text'
			return f'StreamReader {mode}, full size {size_to_kb_mb_string(self._full_len, True)}, remaining size {size_to_kb_mb_string(len(self), True)}'

	def __len__(self):
		"""Returns remaining length."""
		return self._full_len - self._start_ptr

	def __enter__(self):
		return self

	def __exit__(self, exception_type, exception_value, traceback):
		self.close()

	@property
	def full_len(self) -> int:
		"""Returns original full length."""
		return self._full_len

	@property
	def binary(self) -> bool:
		"""Returns true, if the data provided is binary."""
		return self._binary

	def read(self, chunk_size: int = None) -> AnyStr:
		"""Read chunk from the data and moves the data pointer behind it.
		If the remaining length is smaller than the chunk_size, the method returns the remaining length only.
		:param chunk_size: chunk to read. If not set, the method reads the entire data."""
		assert self._data is not None, 'StreamReader buffer is invalid. You have probably closed it already.'
		chunk_size = len(self) if chunk_size is None else chunk_size
		chunk_size = min(chunk_size, len(self))
		if chunk_size < 0:
			raise ValueError(f'Chunk size can not be negative number: {chunk_size}')
		self._read_len += chunk_size
		if self._source == Type.Variable:
			self._start_ptr += chunk_size
			return self._data[self._start_ptr - chunk_size: self._start_ptr]
		elif self._source == Type.File:
			self._start_ptr += chunk_size
			return self._data.read(chunk_size)

	@property
	def read_len(self) -> int:
		"""Returns number of bytes read from the stream since its creation."""
		return self._read_len

	def read_as_binary(self, encoding: str, chunk_size: int = None) -> bytes:
		"""Same as read(), but always returns the data in binary format.
		Practically works exactly as read() for binary streams.
		For string streams, the method converts the returned data using the provided encoding to bytes()."""
		if self._binary:
			return self.read(chunk_size)
		else:
			return self.read(chunk_size).encode(encoding)

	def close(self):
		"""Closes the StreamReader. You can not use its instance afterwards."""
		if self._source == Type.File and self._data:
			self._data.close()
		self._data = None
