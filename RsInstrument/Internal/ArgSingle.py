"""Single argument definition for a scalar argument."""

from .ConverterFromScpiString import ConverterFromScpiString
from .ConverterToScpiString import ConverterToScpiString
from .InstrumentErrors import RsInstrException

from .Types import DataType


class ArgSingle(object):
	"""Single Argument outside a structure - used for composing query arguments.
	Contains the argument value as well (self.value)."""

	def __init__(self, name: str, value, data_type: DataType, enum_type=None, is_optional: bool = False, is_open_list: bool = False, repetition: int = 1, intern_link: str = None):
		self.name = name if name else ''
		self.argument_ix = None
		self.value = value
		self.data_type = data_type
		self.enum_type = enum_type
		self.is_optional = is_optional
		self.is_open_list = is_open_list
		self.repetition = repetition
		self.intern_link = intern_link
		self.conv_from_scpi_string = None
		self.conv_to_scpi_string = None

		if self.data_type.is_scalar_enum:
			# self.assert_mandatory_has_value(self)
			self.conv_from_scpi_string = ConverterFromScpiString(self.data_type, self.enum_type)
			self.conv_to_scpi_string = ConverterToScpiString(self.data_type, self.enum_type)
		elif self.data_type.is_list_enum:
			# self.assert_mandatory_has_value(self)
			if self.value is not None:
				self.conv_from_scpi_string = ConverterFromScpiString(self.data_type, self.enum_type)
				self.conv_to_scpi_string = ConverterToScpiString(self.data_type, self.enum_type)
		else:
			self.conv_from_scpi_string = ConverterFromScpiString(self.data_type)
			self.conv_to_scpi_string = ConverterToScpiString(self.data_type)

		self.check_consistency()

	@classmethod
	def as_open_list(cls, name: str, value: object, data_type: DataType, enum_type=None) -> 'ArgSingle':
		"""Creates new ArgSingle of open list type.Use this method for all non-interleaved list types. \n
		:param name: name of the argument
		:param value: value of the argument
		:param data_type: data type of the argument
		:param enum_type: enum type if the data_type is Enum or EnumExt (or list of those)
		:return: ArgSingle object of an open list type"""
		return cls(name, value, data_type, enum_type, False, True, 1, None)

	def __str__(self):
		opt = '~' if self.is_optional else ''
		name = f" '{self.name}'" if self.name != '' else ''
		out = f"SingleArg {opt}{self.data_type.name}{name}"

		if self.is_open_list is False and self.repetition > 1:
			out += f' [{self.repetition}]'
		elif self.is_open_list is True:
			out += f' [{self.repetition}...]'
		if self.intern_link:
			out += f", Linking: '{self.intern_link}'"
		if self.value:
			out += f', value: {self.value}'
		else:
			out += ", <no value>"
		if self.intern_link:
			out += f", Linking: '{self.intern_link}'"
		return out

	# noinspection PyUnusedLocal
	def has_value(self, value_obj=None) -> bool:
		"""Returns true, if the argument has value."""
		return self.value is not None

	# noinspection PyUnusedLocal
	def assert_is_optional(self, obj=None) -> None:
		"""Asserts that the parameter is optional.
		If not, the method throws an exception."""
		if self.is_optional:
			return
		raise RsInstrException(f'Single argument is not optional: {self}')

	# noinspection PyUnusedLocal
	def assert_mandatory_has_value(self, value_obj=None) -> None:
		"""Asserts that if the parameter is mandatory, it must have value assigned.
		If not, the method throws an exception."""
		if self.is_optional:
			return
		if self.value is None:
			raise ValueError(f'Mandatory single argument has no value: {self}')

	def set_scalar_value_from_str(self, string: str) -> None:
		"""Sets scalar value from input string"""
		self.value = self.conv_from_scpi_string.get_value(string)

	def check_consistency(self) -> None:
		"""Checks the consistency of the object"""
		if self.value is None:
			return
		if isinstance(self.value, list):
			if self.data_type.is_scalar:
				raise RsInstrException(f'Argument real data type is list, but it is declared as {self.data_type}. Value: {self.value}')
		else:
			if self.data_type.is_list:
				raise RsInstrException(f'Argument real data type is scalar, but it is declared as {self.data_type}. Value: {self.value}')
