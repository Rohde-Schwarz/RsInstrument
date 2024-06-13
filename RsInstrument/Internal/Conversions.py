"""Contains conversion functions for SCPI string -> parameter and vice versa."""

import math
import struct
import sys
from enum import Enum
from typing import List, Tuple
from .ScpiEnums import ScpiEnum, enum_spec_prefixes, enum_spec_strings
from .Properties import Properties
from datetime import datetime

from . import Utilities
from .InstrumentErrors import RsInstrException


class BinFloatFormat(Enum):
	"""Binary format of a float number."""
	Single_4bytes = 1
	Single_4bytes_swapped = 2
	Double_8bytes = 3
	Double_8bytes_swapped = 4


class BinIntFormat(Enum):
	"""Binary format of an integer number."""
	Integer32_4bytes = 1
	Integer32_4bytes_swapped = 2
	Integer16_2bytes = 3
	Integer16_2bytes_swapped = 4


def assert_string_data(value: str) -> None:
	"""Asserts value is string type."""
	assert isinstance(value, str), f"Input value type must be string. Actual type: {type(value)}, value: {value}"


def assert_list_data(value: List) -> None:
	"""Asserts value is list type."""
	assert isinstance(value, list), f"Input value type must be a list. Actual type: {type(value)}, value: {value}"


def _get_endianness_symbol(swap_endianness: bool) -> str:
	"""Based on the current endianness returns the symbol used in the 'struct' module."""
	if swap_endianness is False:
		return '@'
	elif swap_endianness is True and sys.byteorder == 'little':
		return '>'
	else:
		return '<'


def bytes_to_float32_list(data: bytes, swap_endianness=False) -> List[float]:
	"""Converts bytes to list of floats - one number is represented by 4 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{len(data) // 4}f'
	return list(struct.unpack(fmt, data))


def bytes_to_double64_list(data: bytes, swap_endianness=False) -> List[float]:
	"""Converts bytes to list of doubles - one number is represented by 8 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{len(data) // 8}d'
	return list(struct.unpack(fmt, data))


def bytes_to_int32_list(data: bytes, swap_endianness=False) -> List[int]:
	"""Converts bytes to list of integer32 - one number is represented by 4 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{len(data) // 4}i'
	return list(struct.unpack(fmt, data))


def bytes_to_int16_list(data: bytes, swap_endianness=False) -> List[int]:
	"""Converts bytes to list of integer16 - one number is represented by 2 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{len(data) // 2}h'
	return list(struct.unpack(fmt, data))


def bytes_to_list_of_floats(data: bytes, fmt: BinFloatFormat) -> List[float]:
	"""Decodes binary data to a list of floating-point numbers based on the entered format."""
	if fmt == BinFloatFormat.Single_4bytes:
		return bytes_to_float32_list(data)
	elif fmt == BinFloatFormat.Single_4bytes_swapped:
		return bytes_to_float32_list(data, True)
	elif fmt == BinFloatFormat.Double_8bytes:
		return bytes_to_double64_list(data)
	elif fmt == BinFloatFormat.Double_8bytes_swapped:
		return bytes_to_double64_list(data, True)


def bytes_to_list_of_integers(data: bytes, fmt: BinIntFormat) -> List[int]:
	"""Decodes binary data to a list of integer numbers based on the entered format."""
	if fmt == BinIntFormat.Integer32_4bytes:
		return bytes_to_int32_list(data)
	elif fmt == BinIntFormat.Integer32_4bytes_swapped:
		return bytes_to_int32_list(data, True)
	elif fmt == BinIntFormat.Integer16_2bytes:
		return bytes_to_int16_list(data)
	elif fmt == BinIntFormat.Integer16_2bytes_swapped:
		return bytes_to_int16_list(data, True)


def double64_list_to_bytes(data: List[float], swap_endianness=False) -> bytes:
	"""Converts list of doubles to bytes - one number is converted to 8 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{str(len(data))}d'
	return struct.pack(fmt, *data)


def float32_list_to_bytes(data: List[float], swap_endianness=False) -> bytes:
	"""Converts list of floats to bytes - one number is converted to 4 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{str(len(data))}f'
	return struct.pack(fmt, *data)


def int32_list_to_bytes(data: List[int], swap_endianness=False) -> bytes:
	"""Converts list of integers 32 to bytes - one number is converted to 4 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{str(len(data))}i'
	return struct.pack(fmt, *data)


def int16_list_to_bytes(data: List[float], swap_endianness=False) -> bytes:
	"""Converts list of integers 16 to bytes - one number is converted to 2 bytes."""
	fmt = f'{_get_endianness_symbol(swap_endianness)}{str(len(data))}h'
	return struct.pack(fmt, *data)


def list_of_integers_to_bytes(ints: List[int], fmt: BinIntFormat) -> bytes:
	"""Encodes list of integers to binary data based on the entered format."""
	if fmt == BinIntFormat.Integer32_4bytes:
		return int32_list_to_bytes(ints)
	elif fmt == BinIntFormat.Integer32_4bytes_swapped:
		return int32_list_to_bytes(ints, True)
	elif fmt == BinIntFormat.Integer16_2bytes:
		return int16_list_to_bytes(ints)
	elif fmt == BinIntFormat.Integer16_2bytes_swapped:
		return int16_list_to_bytes(ints, True)


def list_of_floats_to_bytes(floats: List[float], fmt: BinFloatFormat) -> bytes:
	"""Encodes list of floats to binary data based on the entered format."""
	if fmt == BinFloatFormat.Single_4bytes:
		return float32_list_to_bytes(floats)
	elif fmt == BinFloatFormat.Single_4bytes_swapped:
		return float32_list_to_bytes(floats, True)
	elif fmt == BinFloatFormat.Double_8bytes:
		return double64_list_to_bytes(floats)
	elif fmt == BinFloatFormat.Double_8bytes_swapped:
		return double64_list_to_bytes(floats, True)


pure_bool_true_lookup = frozenset(['on', 'On', 'ON', 'true', 'True', 'TRUE'])
bool_true_lookup = frozenset(['1', 'on', 'On', 'ON', 'true', 'True', 'TRUE'])
bool_false_lookup = frozenset(['0', 'off', 'Off', 'OFF', 'false', 'False', 'FALSE'])
pure_bool_false_lookup = frozenset(['off', 'Off', 'OFF', 'false', 'False', 'FALSE'])


def str_to_bool(string: str) -> bool:
	"""Converts string to boolean value.
	The function is robust, and case-insensitive.
	If the string can not be converted to a boolean, the function returns False."""
	assert_string_data(string)
	if string in bool_true_lookup:
		return True
	if string in bool_false_lookup:
		return False
	# If leading/trailing spaces
	string = string.strip()
	if string in bool_true_lookup:
		return True
	if string in bool_false_lookup:
		return False
	# If enclosed by brackets
	string = Utilities.trim_str_response(string)
	if string in bool_true_lookup:
		return True
	if string in bool_false_lookup:
		return False
	return False


def string_to_pure_bool(string: str) -> bool or None:
	"""Converts string to boolean value. Compare to str_to_bool(), the values '1' and '0' are not considered boolean.
	Also, if the method can not convert the string to boolean, it returns None."""
	assert_string_data(string)
	if string in pure_bool_true_lookup:
		return True
	if string in pure_bool_false_lookup:
		return False
	# If leading/trailing spaces
	string = string.strip()
	if string in pure_bool_true_lookup:
		return True
	if string in pure_bool_false_lookup:
		return False
	# If enclosed by brackets
	string = Utilities.trim_str_response(string)
	if string in pure_bool_true_lookup:
		return True
	if string in pure_bool_false_lookup:
		return False
	return None


number_plus_inf_lookup = frozenset(['Inf', 'INF', 'INFINITY', '+Inf', '+INF', '+inf', '+INFINITY', '+Infinity', '+infinity'])
number_minus_inf_lookup = frozenset(['-Inf', '-INF', '-inf', '-INFINITY', '-Infinity', '-infinity'])
number_nan_lookup = frozenset(['Nan', 'NAN', 'nan', 'NaN', 'NAV', 'NaV', 'NCAP', 'INV', 'NONE', 'none', 'None', 'DTX', 'UND', 'und'])
number_max_lookup = frozenset(['OFL', 'ofl', 'Ofl'])
number_min_lookup = frozenset(['UFL', 'ufl', 'Ufl'])
number_si_suffix = {
	'pHz': 1E-12, 'MHz': 1E+6, 'kHz': 1E+3, 'GHz': 1E+9, 'mHz': 1E-3, 'uHz': 1E-6, 'µHz': 1E-6, 'THz': 1E+12, 'nHz': 1E-9, 'ns': 1E-9, 'fW': 1E-15,
	'pW': 1E-12, 'nW': 1E-9, 'uW': 1E-6, 'µW': 1E-6, 'mW': 1E-3, 'kW': 1E3, 'MW': 1E6, 'GW': 1E9, 'MV': 1E+6, 'MA': 1E+6, 'ps': 1E-12, 'fs': 1E-15,
	'km': 1E+3, 'kV': 1E+3, 'kA': 1E+3, 'pF': 1E-2, 'Hz': 1.0, 'mm': 1E-3, 'mA': 1E-3, 'mF': 1E-3, 'mV': 1E-3, 'pV': 1E-12, 'nF': 1E-9, 'nA': 1E-9,
	'nV': 1E-9, 'nm': 1E-9, 'pm': 1E-12, 'us': 1E-6, 'µs': 1E-6, 'uF': 1E-6, 'µF': 1E-6, 'ms': 1E-3, 'uA': 1E-6, 'µA': 1E-6, 'uV': 1E-6, 'µV': 1E-6,
	'um': 1E-6, 'µm': 1E-6, 'pA': 1E-12, 'V': 1, 'W': 1, 'A': 1, 'F': 1, 's': 1, 'm': 1}
int_neg_inf = -(sys.maxsize - 1)


def strip_si_suffix(string: str) -> Tuple[bool, str, float]:
	"""Tries to find defined suffixes in the text and returns the stripped text and the multiplier as double number.
	If no known suffix is detected, the method returns false, strippedText=text, multiplier=1.0
	Example: text='123 MHz' strippedText='123' multiplier=1E6"""
	for suffix in number_si_suffix.keys():
		if string.endswith(suffix):
			return True, string[:-len(suffix)].rstrip(), number_si_suffix[suffix]
	return False, string, 1.0


def str_to_int(string: str) -> int:
	"""Converts string to integer value. Float values are coerced to integer.
	Also recognizes case-insensitive special values like NaN, INV, NCAP..."""
	assert_string_data(string)
	string = string.strip(" \t\r\n'\"")
	if string == '':
		return 0
	value = str_special_values_to_int(string)
	if value:
		return value

	# Hexadecimal numbers
	if string.startswith('#H') or string.startswith('0x'):
		if ',' in string:
			return int(string[2:string.find(',')], 16)
		else:
			return int(string[2:], 16)

	# Binary numbers
	if string.startswith('#B') or string.startswith('0b'):
		if ',' in string:
			return int(string[2:string.find(',')], 2)
		else:
			return int(string[2:], 2)

	# Octal numbers
	if string.startswith('#Q') or string.startswith('0o'):
		if ',' in string:
			return int(string[2:string.find(',')], 8)
		else:
			return int(string[2:], 8)
	# Simulation
	if string == 'Simulating':
		return 0
	try:
		return int(round(float(string)))
	except ValueError:
		result = strip_si_suffix(string)
		if result[0] is False:
			raise
		try:
			return int(round(float(result[1]) * result[2]))
		except ValueError:
			raise ValueError(f"could not convert string to integer: '{string}'")


def str_special_values_to_int(string: str) -> int:
	"""Converts special string values to integer. Returns None if no special value was found."""
	assert_string_data(string)
	if string in number_plus_inf_lookup or string in number_max_lookup:
		return sys.maxsize
	if string in number_minus_inf_lookup or string in number_min_lookup or string in number_nan_lookup:
		return int_neg_inf
	if string == 'OFF':
		return int_neg_inf + 1
	if string == 'ON':
		return int_neg_inf + 2
	if string == 'OK':
		return sys.maxsize - 1
	if string == 'DC':
		# noinspection PyTypeChecker
		return int_neg_inf / 100
	if string == 'ULEU':
		return int(sys.maxsize / 10)
	if string == 'ULEL':
		# noinspection PyTypeChecker
		return int_neg_inf / 10
	# noinspection PyTypeChecker
	return None


def str_to_int_or_bool(string: str) -> int or bool:
	"""Similar to str_to_int, but for special values "ON/OFF" the function returns boolean"""
	result = string_to_pure_bool(string)
	if result is not None:
		return result
	return str_to_int(string)


def str_to_float(string: str) -> float:
	"""Converts string to float value.
	Also recognizes case-insensitive special values like NaN, INV, NCAP..."""
	assert_string_data(string)
	string = string.strip(" \t\r\n'\"")
	if string == '':
		return 0.0
	if string in number_plus_inf_lookup:
		return math.inf
	if string in number_minus_inf_lookup:
		return -math.inf
	if string in number_nan_lookup:
		return math.nan
	if string in number_max_lookup:
		return sys.float_info.max
	if string in number_min_lookup:
		return -sys.float_info.max
	if string == 'OFF':
		return -sys.float_info.epsilon
	if string == 'ON':
		return -2*sys.float_info.epsilon
	if string == 'OK':
		return sys.float_info.epsilon
	if string == 'DC' or string == '':
		return -sys.float_info.max / 100
	if string == 'ULEU':
		return sys.float_info.max / 10
	if string == 'ULEL':
		return -sys.float_info.max / 10
	if string == 'Simulating':
		return 0.0
	try:
		return float(string)
	except ValueError:
		result = strip_si_suffix(string)
		if result[0] is False:
			raise
		try:
			return float(result[1]) * result[2]
		except ValueError:
			raise ValueError(f"could not convert string to float: '{string}'")


def str_to_float_or_bool(string: str) -> float or bool:
	"""Similar to str_to_float, but for special values "ON/OFF" the function returns boolean"""
	result = string_to_pure_bool(string)
	if result is not None:
		return result
	return str_to_float(string)


def float_to_str(value: float) -> str:
	"""Converts double number to string using {.12g} formatter."""
	return format(value, ".12g")


def bool_to_str(value: bool) -> str:
	"""Converts boolean to 'ON' or 'OFF' string."""
	if type(value) is bool:
		return 'ON' if value is True else 'OFF'
	else:
		raise RsInstrException(f"bool_to_str: unsupported variable type '{type(value)}', value '{value}'. Only boolean values are supported.")


def str_enclose_by_quotes(string: str) -> str:
	"""Returns string enclosed by single quotes."""
	assert_string_data(string)
	return Properties.scpi_quotes + string + Properties.scpi_quotes


def list_to_csv_str(value: List, delimiter: str = ',') -> str:
	"""Converts list of elements to strings separated by commas.
	The method also tolerates a scalar value, and handles it as list of one element.
	Element types can differ on an individual basis.
	Supported element types:
	- int
	- bool
	- float
	- string -> string no quotes
	- enum"""
	if isinstance(value, int) or isinstance(value, bool) or isinstance(value, float) or isinstance(value, str) or isinstance(value, Enum):
		value = [value]

	assert_list_data(value)
	result = []
	for x in value:
		el = value_to_str(x)
		if not el:
			raise TypeError(f"List element type is not supported by Conversions.list_to_csv_str: '{x}'")
		result.append(el)
	return delimiter.join(result)


def list_to_csv_quoted_str(value: List) -> str:
	"""Converts list of elements to quoted strings separated by commas.
	The method also tolerates a scalar value, and handles it as list of one element.
	Only string elements are enclosed by single quotes
	Element types can differ on an individual basis.
	Supported element types:
	- int
	- bool
	- float
	- string -> string enclosed by quotes
	- enum"""
	if isinstance(value, int) or isinstance(value, bool) or isinstance(value, float) or isinstance(value, str) or isinstance(value, Enum):
		value = [value]

	assert_list_data(value)
	result = []
	for x in value:
		if isinstance(x, str):
			el = str_enclose_by_quotes(x)
		else:
			el = value_to_str(x)
		if not el:
			raise TypeError(f"List element type is not supported by Conversions.list_to_csv_quoted_str: '{x}'")
		result.append(el)
	return ','.join(result)


def decimal_value_to_str(x: int or float) -> str:
	"""Converts scalar decimal value to string.
	Supported element types:
	- int
	- float"""
	if isinstance(x, int) and type(x) is not bool:
		return str(x)
	elif isinstance(x, float):
		return float_to_str(x)
	else:
		raise RsInstrException(f"decimal_value_to_str: unsupported variable type '{type(x)}', value '{x}'. Only integer and float types are supported.")


def decimal_or_bool_value_to_str(x: int or float or bool) -> str:
	"""Converts scalar decimal value to string.
	Supported element types:
	- int
	- float
	- boolean"""
	if type(x) is bool:
		return bool_to_str(x)
	if isinstance(x, int):
		return str(x)
	elif isinstance(x, float):
		return float_to_str(x)
	else:
		raise RsInstrException(f"decimal_or_bool_value_to_str: unsupported variable type '{type(x)}', value '{x}'. Only integer, float and boolean types are supported.")


def value_to_str(x: int or bool or float or str or Enum) -> str:
	"""Converts scalar value to string.
	Supported element types:
	- int
	- bool
	- float
	- string
	- enum"""
	if isinstance(x, bool):
		return bool_to_str(x)
	elif isinstance(x, int):
		return str(x)
	elif isinstance(x, float):
		return float_to_str(x)
	elif isinstance(x, str):
		return x
	elif isinstance(x, Enum):
		if isinstance(x.value, str):
			return enum_value_to_scpi_string(x.value)
		return enum_value_to_scpi_string(x.name)
	else:
		raise RsInstrException(f"value_to_str: unsupported variable type '{type(x)}', value '{x}'. Supported types: int, bool, float, str, enum.")


def enum_value_to_scpi_string(enum_value: str) -> str:
	"""Conversion EnumValue -> SCPI_String
	Unescapes all the special characters that can not be contained in the enum member definition, but can be sent to the instrument as enum string.
	Use this to send the scpi enum value to the instrument."""
	for key in enum_spec_prefixes:
		if enum_value.startswith(key):
			enum_value = enum_spec_prefixes[key] + enum_value[len(key):]
	for key in enum_spec_strings:
		enum_value = enum_value.replace(key, enum_spec_strings[key])
	return enum_value


def value_to_quoted_str(x: int or bool or float or str or Enum) -> str:
	"""Converts scalar value to string enclosed by single quotes.
	Supported element types:
	- int
	- bool
	- float
	- string
	- enum"""
	return Properties.scpi_quotes + value_to_str(x) + Properties.scpi_quotes


def str_to_float_list(string: str) -> List[float]:
	"""Converts string with comma-separated values to list of floats.
	Empty or blank string is converted to empty list."""
	assert_string_data(string)
	if not string:
		return []
	if string.isspace():
		return []
	result = [*map(str_to_float, string.split(','))]
	return result


def str_to_float_or_bool_list(string: str) -> List[float or bool]:
	"""Converts string with comma-separated values to list of float or boolean values.
	Empty or blank string is converted to empty list."""
	assert_string_data(string)
	if not string:
		return []
	if string.isspace():
		return []
	result = [*map(str_to_float_or_bool, string.split(','))]
	return result


def str_to_int_list(string: str) -> List[int]:
	"""Converts string with comma-separated values to list of integers.
	Empty or blank string is converted to empty list."""
	assert_string_data(string)
	if not string:
		return []
	if string.isspace():
		return []
	result = [*map(str_to_int, string.split(','))]
	return result


def str_to_int_or_bool_list(string: str) -> List[int or bool]:
	"""Converts string with comma-separated values to list of integer or boolean values.
	Empty or blank string is converted to empty list."""
	assert_string_data(string)
	if not string:
		return []
	if string.isspace():
		return []
	result = [*map(str_to_int_or_bool, string.split(','))]
	return result


def str_to_bool_list(string: str) -> List[bool]:
	"""Converts string with comma-separated values to list of booleans.
	Empty or blank string is converted to empty list."""
	assert_string_data(string)
	if not string:
		return []
	if string.isspace():
		return []
	result = [*map(str_to_bool, string.split(','))]
	return result


def str_to_str_list(string: str, remove_blank_response: bool = False) -> List[str]:
	"""Converts string with comma-separated values to list of strings.
	Each element is trimmed by trim_str_response().
	Meaning of the 'remove_empty_response':
		- False(default): empty response is returned as a list with one empty element [''].
		- True: empty response is returned as an empty list []."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(Utilities.trim_str_response, string.split(','))]
	if remove_blank_response and len(result) == 1 and result[0] == '':
		return []
	return result


def str_to_scalar_enum_helper(string: str, scpi_enum: ScpiEnum, array_search: bool, exc_if_not_found) -> Enum:
	"""Converts string to one enum element.
	array_search signal no need to force the comma removing,
	because the elements definitely do not have any commas - commas have been used to split string to the list of strings
	The function can also return:
	- integer special value, if the string was not found in the enum, and it is a special value.
	- input string, if the string was not found and raise_if_not_found is set to False - used for the EnumExt types."""
	if scpi_enum.has_quotes:
		value = Utilities.trim_str_response(string, mode=Utilities.TrimStringMode.white_chars_double_quotes)
	else:
		value = Utilities.trim_str_response(string)
	enum_value = scpi_enum.find_in_enum_members(value, False)
	if enum_value is not None:
		return enum_value
	if array_search is False:
		# If the result is still -1 (not found), try to force removing the comma in the string.
		enum_value = scpi_enum.find_in_enum_members(value, True)
		if enum_value is not None:
			return enum_value
	# If not found, search in the special integer numbers:
	spec_value = str_special_values_to_int(value)
	if spec_value:
		# noinspection PyTypeChecker
		return spec_value
	if exc_if_not_found:
		raise RsInstrException(f"String '{value}' can not be found in the enum type '{scpi_enum.enum_type}'")
	# noinspection PyTypeChecker
	return Utilities.trim_str_response(string)


def str_to_simple_scalar_enum(string: str, enum_type, case_sensitive: bool = True, ignore_underscores: bool = False) -> Enum or None:
	"""Converts string to one enum element.
	Does not handle special value or non-mandatory parts.
	The function is used in core only for standard enum conversions, not for SCPI enum conversions."""
	value = Utilities.trim_str_response(string)
	enum_members = [x.name for x in enum_type]
	enum_members_mod = [x.name for x in enum_type]
	if not case_sensitive:
		enum_members_mod = [x.upper() for x in enum_members]
		value = value.upper()
	if ignore_underscores:
		enum_members_mod = [x.replace('_', '') for x in enum_members_mod]
		value = value.replace('_', '')
	if value in enum_members_mod:
		return enum_type[enum_members[enum_members_mod.index(value)]]
	return None


def str_to_list_enum_helper(string: str, scpi_enum: ScpiEnum, exc_if_not_found: bool = True) -> List[Enum]:
	"""Converts string to list of enum elements. separated by comma."""
	if not string:
		return []
	if string.isspace():
		return []
	elements = string.split(',')
	return [str_to_scalar_enum_helper(x, scpi_enum, True, exc_if_not_found) for x in elements]


def enum_scalar_to_str(data, enum_type) -> str:
	"""Converts enum scalar value to string."""
	assert isinstance(data, enum_type), f"Expected command parameter {enum_type}, actual data type: {type(data)}. Value: {data}"
	return value_to_str(data)


def enum_ext_scalar_to_str(data, enum_type) -> str:
	"""Converts enum scalar value to string.
	If the input value is string, the function returns the string with single quotes."""
	if isinstance(data, str):
		# Return string with quotes
		return value_to_quoted_str(Utilities.trim_str_response(data))
	assert isinstance(data, enum_type), f"Expected command parameter string or {enum_type}, actual data type: {type(data)}. Value: {data}"
	return value_to_str(data)


def enum_list_to_str(data: List, enum_type) -> str:
	"""Converts enum list to csv-string.
	The method also tolerates a scalar value, and handles it as list of one element."""
	if isinstance(data, enum_type):
		data = [data]
	# For enums, check that each element is an enum
	assert all(isinstance(x, enum_type) for x in data), f"Expected command parameter list of {enum_type}, detected one or more elements of non-enum type. Value: {data}"
	return list_to_csv_str(data)


def enum_ext_list_to_str(data: List, enum_type) -> str:
	"""Converts enum list to csv-string. Allows the elements to be either enum or string.
	The method also tolerates a scalar value, and handles it as list of one element."""
	if isinstance(data, enum_type or str) or isinstance(data, str):
		data = [data]
	assert all((isinstance(x, enum_type or str) or isinstance(x, str)) for x in data), f"Expected command parameter list of strings or {enum_type}, detected one or more elements of non-enum/non-string type. Value: {data}"
	return list_to_csv_quoted_str(data)


def str_to_scalar_enum(string: str, enum_type) -> Enum:
	"""Converts string to one enum element.
	Throws exception if the string can not be converted to an enum element or a special value."""
	return str_to_scalar_enum_helper(string, ScpiEnum(enum_type), False, exc_if_not_found=True)


def str_to_scalar_enum_ext(string: str, enum_type) -> Enum:
	"""Converts string to one enum element.
	Compared to str_to_scalar_enum, in case the string can not be converted, it is returned trimmed for quotes and ."""
	return str_to_scalar_enum_helper(string, ScpiEnum(enum_type), False, exc_if_not_found=False)


def str_to_list_enum(string: str, enum_type) -> List[Enum]:
	"""Converts string to list of enum elements."""
	return str_to_list_enum_helper(string, ScpiEnum(enum_type))


def str_to_list_enum_ext(string: str, enum_type) -> List[Enum]:
	"""Converts string to list of enum or string elements."""
	return str_to_list_enum_helper(string, ScpiEnum(enum_type), exc_if_not_found=False)


def convert_ts_to_datetime(timestamp: datetime or float) -> datetime:
	"""Converts timestamp as float to datetime. For datetime tuple it just passes the value."""
	if isinstance(timestamp, float) or isinstance(timestamp, int):
		return datetime.fromtimestamp(timestamp)
	return timestamp


def get_timestamp_string(timestamp: datetime or float) -> str:
	"""Returns the timestamp as string. The timestamp can be a datetime tuple or float seconds coming from the time.time()."""
	timestamp = convert_ts_to_datetime(timestamp)
	cur_time = timestamp.strftime('%H:%M:%S.%f')[:-3]
	return cur_time


def get_timedelta_fixed_string(time_start: datetime or float, time_end: datetime or float) -> str:
	"""Returns the time span as string - fixed in the format of '%H:%M:%S.%f'."""
	time_a = convert_ts_to_datetime(time_start)
	time_b = convert_ts_to_datetime(time_end)
	frac = (time_b - time_a).total_seconds()
	wh = math.floor(frac)
	d = int(wh / 86400)
	h = int((wh - (d * 86400)) / 3600)
	m = int((wh - (d * 86400 + h * 3600)) / 60)
	s = int((wh - (d * 86400 + h * 3600 + m * 60)))
	ms = int((frac - wh) * 1000)
	res = f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'
	if d > 0:
		res = f'{d}d ' + res
	return res


def get_timedelta_string(time_a: datetime or float, time_b: datetime or float) -> str:
	"""Returns the time span as string - dynamic based on the difference."""
	time_a = convert_ts_to_datetime(time_a)
	time_b = convert_ts_to_datetime(time_b)
	if time_b < time_a:
		return '0.000 ms'
	diff = time_b - time_a
	if diff.seconds < 10:
		return f'{diff.total_seconds() * 1000:0.3f} ms'
	elif diff.seconds < 1000:
		a = diff.total_seconds()
		return f'{a:0.3f} secs'
	hours, remainder = divmod(diff.seconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
