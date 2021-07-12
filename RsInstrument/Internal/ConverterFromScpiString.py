"""See the class docstring."""

from enum import Enum

from .Conversions import str_to_bool, str_to_int, str_to_int_or_bool, str_to_float, str_to_float_or_bool, str_to_scalar_enum_helper
from .Conversions import str_to_str_list, str_to_bool_list, str_to_int_list, str_to_int_or_bool_list, str_to_float_list, str_to_float_or_bool_list, str_to_list_enum_helper
from .Types import DataType
from .Utilities import trim_str_response
from .InstrumentErrors import RsInstrException


class ConverterFromScpiString:
	"""Converter from SCPI response string to argument value
	For list argument types, you must use the method get_one_element_value in a loop for each element.
	Provides methods:
	- get_one_element_value(str): returns one scalar value converted from the SCPI string.
	- get_list_value(str): return complete list value converted from the SCPI string.
	- get_value(str): calls either get_one_element_value or get_list_value() depending on the data type. \n
	The reason for the different methods is, that sometimes the list data are interleaved with other arguments.
	In order to parse them properly, the ArgStructStringParser module must be able to set the argument value element-by-element.
	On the other side, the driver methods might want to set the whole argument value, because the result scpi string is a single argument response."""

	def __init__(self, data_type: DataType, enum_type: Enum = None):
		self.enum_type = enum_type
		self.data_type = data_type
		self.element_type = self.data_type.element_type

		if self.element_type == DataType.RawString:
			self.converter = trim_str_response
			self.list_converter = str_to_str_list

		elif self.element_type == DataType.String:
			self.converter = trim_str_response
			self.list_converter = str_to_str_list

		elif self.element_type == DataType.Boolean:
			self.converter = str_to_bool
			self.list_converter = str_to_bool_list

		elif self.element_type == DataType.Integer:
			self.converter = str_to_int
			self.list_converter = str_to_int_list

		elif self.element_type == DataType.IntegerExt:
			self.converter = str_to_int_or_bool
			self.list_converter = str_to_int_or_bool_list

		elif self.element_type == DataType.Float:
			self.converter = str_to_float
			self.list_converter = str_to_float_list

		elif self.element_type == DataType.FloatExt:
			self.converter = str_to_float_or_bool
			self.list_converter = str_to_float_or_bool_list

		elif self.element_type == DataType.Enum:
			assert self.enum_type, f"For data type enum, you have to define the enum_type variable."
			# noinspection PyTypeChecker
			self.enum_members = [x.name for x in self.enum_type]
		else:
			raise RsInstrException(f"Unsupported data type '{data_type}'")

	def get_one_element_value(self, scpi_string: str):
		"""Returns single element !!! of the argument value converted from the SCPI string (single element)"""
		assert isinstance(scpi_string, str), f"Input parameter scpi_string must be string. Actual parameter: {type(scpi_string)}, value: {scpi_string}"
		if self.element_type is DataType.Enum:
			return str_to_scalar_enum_helper(scpi_string, self.enum_type, self.enum_members)
		return self.converter(scpi_string)

	def get_value(self, scpi_string: str):
		"""Returns complete value of the argument converted from the SCPI string (list or scalar)"""
		if not self.data_type.is_list:
			return self.get_one_element_value(scpi_string)

		assert isinstance(scpi_string, str), f"Input parameter scpi_string must be string. Actual parameter: {type(scpi_string)}, value: {scpi_string}"
		if self.element_type is DataType.Enum:
			return str_to_list_enum_helper(scpi_string, self.enum_type, self.enum_members)
		return self.list_converter(scpi_string)
