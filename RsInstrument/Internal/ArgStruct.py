"""Definition for an argument which is a part of a structure."""

from .ConverterFromScpiString import ConverterFromScpiString
from .ConverterToScpiString import ConverterToScpiString
from .Types import DataType
from .InstrumentErrors import RsInstrException


class ArgStruct(object):
	"""Describes an argument in data structures.
	This info is used to parse a string query response to the output structure,
	or to parse the output structure to the string parameter for writing.
	Contains reference to the value in the owning structure."""

	def __init__(self, name: str, data_type: DataType, enum_type=None, is_optional=False, is_open_list=False, repetition=1, intern_link: str = None):
		self.argument_ix = None
		self.name = name
		self.data_type = data_type
		self.is_optional = is_optional
		self.is_open_list = is_open_list
		self.repetition = repetition
		self.intern_link = intern_link
		self.enum_type = enum_type
		self.conv_from_scpi_string = ConverterFromScpiString(self.data_type, self.enum_type)
		self.conv_to_scpi_string = ConverterToScpiString(self.data_type, self.enum_type)

	@classmethod
	def scalar_int(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar integer argument."""
		return cls(name, DataType.Integer, None, False, False, 1, intern_link)

	@classmethod
	def scalar_int_ext(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar extended integer argument."""
		return cls(name, DataType.IntegerExt, None, False, False, 1, intern_link)

	@classmethod
	def scalar_str(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar string argument."""
		return cls(name, DataType.String, None, False, False, 1, intern_link)

	@classmethod
	def scalar_raw_str(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar raw string argument."""
		return cls(name, DataType.RawString, None, False, False, 1, intern_link)

	@classmethod
	def scalar_bool(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar boolean argument."""
		return cls(name, DataType.Boolean, None, False, False, 1, intern_link)

	@classmethod
	def scalar_float(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar float argument."""
		return cls(name, DataType.Float, None, False, False, 1, intern_link)

	@classmethod
	def scalar_float_ext(cls, name: str, intern_link: str = None):
		"""Describes mandatory scalar extended float argument."""
		return cls(name, DataType.FloatExt, None, False, False, 1, intern_link)

	@classmethod
	def scalar_enum(cls, name: str, enum_type, intern_link: str = None):
		"""Describes mandatory scalar float argument."""
		return cls(name, DataType.Enum, enum_type, False, False, 1, intern_link)

	@classmethod
	def scalar_str_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar string argument."""
		return cls(name, DataType.String, None, True, False, 1, intern_link)

	@classmethod
	def scalar_raw_str_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar raw string argument."""
		return cls(name, DataType.RawString, None, True, False, 1, intern_link)

	@classmethod
	def scalar_bool_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar boolean argument."""
		return cls(name, DataType.Boolean, None, True, False, 1, intern_link)

	@classmethod
	def scalar_int_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar integer argument."""
		return cls(name, DataType.Integer, None, True, False, 1, intern_link)

	@classmethod
	def scalar_int_ext_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar extended integer argument."""
		return cls(name, DataType.IntegerExt, None, True, False, 1, intern_link)

	@classmethod
	def scalar_float_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar float argument."""
		return cls(name, DataType.Float, None, True, False, 1, intern_link)

	@classmethod
	def scalar_float_ext_optional(cls, name: str, intern_link: str = None):
		"""Describes optional scalar extended float argument."""
		return cls(name, DataType.FloatExt, None, True, False, 1, intern_link)

	@classmethod
	def scalar_enum_optional(cls, name: str, enum_type, intern_link: str = None):
		"""Describes optional scalar float argument."""
		return cls(name, DataType.Enum, enum_type, True, False, 1, intern_link)

	def __str__(self):
		opt = '~' if self.is_optional else ''
		name = f" '{self.name}'" if self.name != '' else ''
		out = f"StructArg {opt}{self.data_type.name}{name}"

		if self.is_open_list is False and self.repetition > 1:
			out += f' [{self.repetition}]'
		elif self.is_open_list is True:
			out += f' [{self.repetition}...]'
		if self.intern_link:
			out += f", Linking: '{self.intern_link}'"
		return out

	def has_value(self, obj) -> bool:
		"""Returns True, if the entered object attribute has value."""
		return getattr(obj, self.name) is not None

	def assert_is_optional(self, obj) -> None:
		"""Asserts that the parameter is optional.
		If not, the method throws an exception."""
		if self.is_optional:
			return
		value = getattr(obj, self.name)
		if value is None:
			raise RsInstrException(f"Structure '{obj}', argument without value is not optional: {self}")
		else:
			raise RsInstrException(f"Structure '{obj}', argument is not optional: {self}', value '{value}'")

	def assert_mandatory_has_value(self, obj) -> None:
		"""Asserts that if the parameter is mandatory, it must have value assigned.
		If not, the method throws an exception."""
		if self.is_optional:
			return
		if getattr(obj, self.name) is None:
			raise ValueError(f"Mandatory structure '{obj}' argument '{self.name}' has no value.")
