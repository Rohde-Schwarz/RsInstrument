"""See the class docstring."""

from enum import Enum

from .Conversions import list_to_csv_quoted_str, value_to_quoted_str, list_to_csv_str, value_to_str, enum_list_to_str, enum_scalar_to_str, enum_ext_scalar_to_str, enum_ext_list_to_str
from .Types import DataType
from .InstrumentErrors import RsInstrException


def value_to_scpi_string(data, data_type: DataType) -> str:
	"""Convert data to SCPI string parameter: data -> str.
	Does not work with enum data types."""
	if data_type.is_list:
		assert isinstance(data, list), f"Expected command parameter list, actual data type: {type(data)}. Value: {data}"
	else:
		assert not isinstance(data, list), f"Expected command parameter scalar, actual data type: {type(data)}. Value: {data}"
	# Strings are enclosed by single quotes
	if data_type == DataType.StringList:
		assert all(isinstance(x, str) for x in data), f"Expected command parameter list of strings, detected one or more elements of non-string type. Value: {data}"
		return list_to_csv_quoted_str(data)
	elif data_type == DataType.String:
		assert isinstance(data, str), f"Expected command parameter string, actual data type: {type(data)}. Value: {data}"
		return value_to_quoted_str(data)

	# Raw string is not enclosed by quotes
	elif data_type == DataType.RawStringList:
		assert all(isinstance(x, str) for x in data), f"Expected command parameter list of strings, detected one or more elements of non-string type. Value: {data}"
		return list_to_csv_str(data)
	elif data_type == DataType.RawString:
		assert isinstance(data, str), f"Expected command parameter string, actual data type: {type(data)}. Value: {data}"
		return value_to_str(data)

	elif data_type == DataType.BooleanList:
		assert all(type(x) == bool for x in data), f"Expected command parameter list of booleans, detected one or more elements of non-boolean type. Value: {data}"
		return list_to_csv_str(data)
	elif data_type == DataType.Boolean:
		assert type(data) == bool, f"Expected command parameter boolean, actual data type: {type(data)}. Value: {data}"
		return value_to_str(data)

	# For integer and float, allow them to be mixed
	elif data_type == DataType.IntegerList or data_type == DataType.FloatList:
		assert all((isinstance(x, int) or isinstance(x, float)) and type(x) != bool for x in data), f"Expected command parameter list of numbers, detected one or more elements of non-number type. Value: {data}"
		return list_to_csv_str(data)
	elif data_type == DataType.Integer or data_type == DataType.Float:
		assert (isinstance(data, int) or isinstance(data, float)) and type(data) != bool, f"Expected command parameter number, actual data type: {type(data)}. Value: {data}"
		return value_to_str(data)

	# For integer and float extended, allow them to be mixed including the boolean type
	elif data_type == DataType.IntegerExtList or data_type == DataType.FloatExtList:
		assert all((isinstance(x, int) or isinstance(x, float) or isinstance(x, bool)) for x in data), f"Expected command parameter list of numbers or booleans, detected one or more elements of non-number type. Value: {data}"
		return list_to_csv_str(data)
	elif data_type == DataType.IntegerExt or data_type == DataType.FloatExt:
		assert (isinstance(data, int) or isinstance(data, float) or isinstance(data, bool)), f"Expected command parameter number or boolean, actual data type: {type(data)}. Value: {data}"
		return value_to_str(data)
	else:
		raise RsInstrException(f"Unsupported data type: '{type(data_type)}'.")


class ConverterToScpiString:
	"""Converter from argument value to SCPI string.
	Provides method get_value(arg_value) -> str
	"""

	def __init__(self, data_type: DataType, enum_type: Enum = None):
		self.enum_type = enum_type
		self.data_type = data_type
		self.element_type = self.data_type.element_type
		if self.element_type == DataType.Enum or self.element_type == DataType.EnumExt:
			assert self.enum_type, f"For data_type {data_type.name}, you have to define the enum_type variable."

	def get_value(self, data) -> str:
		"""Returns SCPI string converted from the argument data."""
		if self.data_type.is_list:
			assert isinstance(data, list), f"Expected command parameter list, actual data type: {type(data)}. Value: {data}"
		else:
			assert not isinstance(data, list), f"Expected command parameter scalar, actual data type: {type(data)}. Value: {data}"
		if self.data_type == DataType.Enum:
			return enum_scalar_to_str(data, self.enum_type)
		if self.data_type == DataType.EnumExt:
			return enum_ext_scalar_to_str(data, self.enum_type)
		if self.data_type == DataType.EnumList:
			return enum_list_to_str(data, self.enum_type)
		if self.data_type == DataType.EnumExtList:
			return enum_ext_list_to_str(data, self.enum_type)
		return value_to_scpi_string(data, self.data_type)
