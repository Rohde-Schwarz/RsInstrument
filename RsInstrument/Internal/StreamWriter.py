"""See the docstring for the StreamWriter class."""

from enum import Flag
from typing import AnyStr

from .Utilities import size_to_kb_mb_string
from .InstrumentErrors import RsInstrException


class Type(Flag):
	"""Defines type of the stream - variable or file."""
	Variable = 1
	File = 2
	FileAppend = 6


class StreamWriter:
	"""Lightweight stream writer implementation. Data target can be: \n
	- bytes
	- string
	- file"""

	def __init__(self, binary: bool, target: Type, meta_data=None):
		"""Initializes StreamWriter instance.\n
		:param binary: True: Binary data, False: ASCII data
		:param target: Target for the stream. Variable / File (FileAppend)
		:param meta_data: Only valid for File and FileAppend - define file path as string:
		For Type.File, data must be string with file path. If the file exists, it will be overwritten.
		For Type.FileAppend, data must be string with file path. If the file exists, it will be appended."""
		self._binary: bool = binary
		self._written_len: int = 0
		self._target = target

		if Type.Variable in self._target:
			assert meta_data is None, f'You can not define input meta_data for a Variable StreamWriter.'
			self._data: AnyStr = bytes() if binary else ''
		elif Type.File in self._target:
			assert isinstance(meta_data, str), f'Additional data must be of string type (file path). Actual type: {type(meta_data)}'
			self._file_path = meta_data
			mode = 'w' if self._target == Type.File else 'a'
			mode += 'b' if self._binary else ''
			self._data = open(self._file_path, mode)
		else:
			raise RsInstrException(f'StreamWriter unknown target {target}')

	@classmethod
	def as_bin_var(cls) -> 'StreamWriter':
		"""Creates new StreamWriter with bytes variable."""
		return cls(True, Type.Variable)

	@classmethod
	def as_string_var(cls) -> 'StreamWriter':
		"""Creates new StreamWriter with string variable."""
		return cls(False, Type.Variable)

	@classmethod
	def as_bin_file(cls, file_path: str, append: bool = False) -> 'StreamWriter':
		"""Creates new StreamWriter to binary file.
		:param file_path: [str] Path to the file.
		:param append: Optional [bool] If True, the content is appended to the existing content."""
		return cls(True, Type.FileAppend if append else Type.File, file_path)

	@classmethod
	def as_text_file(cls, file_path: str, append: bool = False) -> 'StreamWriter':
		"""Creates new StreamWriter to text file.
		:param file_path: [str] Path to the file.
		:param append: Optional [bool] If True, the content is appended to the existing content."""
		return cls(False, Type.FileAppend if append else Type.File, file_path)

	def __str__(self):
		if Type.Variable in self._target:
			mode = 'binary' if self._binary else 'string'
			return f'StreamWriter {mode} variable, current size {size_to_kb_mb_string(len(self), True)}'
		if Type.File in self._target:
			mode = 'binary' if self._binary else 'text'
			append = ' appended' if Type.FileAppend in self._target else ''
			return f'StreamWriter {mode} file{append}, current{append} size {size_to_kb_mb_string(len(self), True)}, file: {self._file_path}'

	def __len__(self):
		"""Returns remaining length."""
		return self._written_len

	def __enter__(self):
		return self

	def __exit__(self, exception_type, exception_value, traceback):
		self.close()

	@property
	def binary(self) -> bool:
		"""Returns true, if the data held is binary.
		File streams are always binary."""
		return self._binary

	def write(self, data: AnyStr) -> None:
		"""Writes chunk to the stream.
			- For Type.Bytes data must be bytes.
			- For Type.String, data must be string.
			- For Type.File and Type.FileAppend, data must be bytes."""
		assert self._data is not None, 'StreamWriter buffer is invalid. You have probably closed it already.'
		if self._binary:
			assert isinstance(data, bytes), f'Bytes data is required. Actual type: {type(data)}. {self}'
		else:
			assert isinstance(data, str), f'String data is required. Actual type: {type(data)}. {self}'

		if Type.Variable in self._target:
			self._data += data
		elif Type.File in self._target:
			self._data.write(data)
		self._written_len += len(data)

	def switch_to_string_data(self) -> None:
		"""Switches from binary to string data.
		For variables, the current content is converted.
		For files, they are closed and reopened as for appended text writing."""
		if self._binary is False:
			return
		self._binary = False
		if Type.Variable in self._target:
			if len(self) == 0:
				self._data = ''
			else:
				# Convert current bytes content to string
				# noinspection PyUnresolvedReferences
				self._data = self._data.decode('utf-8')
		elif Type.File in self._target:
			self._data.close()
			self._data = open(self._file_path, 'a')

	@property
	def content(self) -> AnyStr:
		"""Returns content of the writer. Only works with variable types."""
		if self._target != Type.Variable:
			raise RsInstrException(f'Can not return content for the current {self}')
		# noinspection PyTypeChecker
		return self._data

	@property
	def written_len(self) -> int:
		"""Returns number of bytes written to the stream since its creation."""
		return self._written_len

	def close(self) -> None:
		"""Closes the StreamWriter. You can not use its instance afterwards."""
		if Type.File in self._target and self._data:
			self._data.close()
		self._data = None
