"""Contains conversion functions for SCPI string -> parameter and vice versa."""

import math
import struct
import sys
from enum import Enum
from typing import List

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
	The function robust, and case insensitive.
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
int_neg_inf = -(sys.maxsize - 1)
enum_spec_prefixes = {'_minus': '-', '_plus': '+', '_': ''}
enum_spec_strings = {'_dash_': '-', '_dot_': '.'}


def str_to_int(string: str) -> int:
	"""Converts string to integer value. Float values are coerced to integer.
	Also recognizes case insensitive special values like NaN, INV, NCAP..."""
	assert_string_data(string)
	string = string.strip()
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
	return int(round(float(string)))


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
	Also recognizes case insensitive special values like NaN, INV, NCAP..."""
	assert_string_data(string)
	string = string.strip()
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
	return float(string)


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
	return "'" + string + "'"


def list_to_csv_str(value: List, delimiter: str = ',') -> str:
	"""Converts list of elements to strings separated by commas.
	Element types can differ on an individual basis.
	Supported element types:
	- int
	- bool
	- float
	- string -> string no quotes
	- enum"""
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
	Only string elements are enclosed by single quotes
	Element types can differ on an individual basis.
	Supported element types:
	- int
	- bool
	- float
	- string -> string enclosed by quotes
	- enum"""
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
	return f"'{value_to_str(x)}'"


def str_to_float_list(string: str) -> List[float]:
	"""Converts string with comma-separated values to list of Floats."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(str_to_float, string.split(','))]
	return result


def str_to_float_or_bool_list(string: str) -> List[float or bool]:
	"""Converts string with comma-separated values to list of float or boolean values."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(str_to_float_or_bool, string.split(','))]
	return result


def str_to_int_list(string: str) -> List[int]:
	"""Converts string with comma-separated values to list of Integers."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(str_to_int, string.split(','))]
	return result


def str_to_int_or_bool_list(string: str) -> List[int or bool]:
	"""Converts string with comma-separated values to list of integer or boolean values."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(str_to_int_or_bool, string.split(','))]
	return result


def str_to_bool_list(string: str) -> List[bool]:
	"""Converts string with comma-separated values to list of booleans."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(str_to_bool, string.split(','))]
	return result


def str_to_str_list(string: str, clear_one_empty_item: bool = False) -> List[str]:
	"""Converts string with comma-separated values to list of strings.
	Each element is trimmed by trim_str_response().
	If the clear_one_empty_item is set to True (default is False), and the result is exactly one empty string item, the method returns empty list."""
	assert_string_data(string)
	if not string:
		return []
	result = [*map(Utilities.trim_str_response, string.split(','))]
	if clear_one_empty_item and len(result) == 1 and result[0] == '':
		return []
	return result


def _find_in_enum_members(item: str, enum_members: List[str]) -> int:
	"""Matches a string in the provided list of member strings.
	The item must be not fully matched.
	The item is matched if a member string starts with the item (the item is a prefix of the member).
	Example: item='CONN' will match the enum_member 'CONNected'
	If the item contains a comma, only the value before comma is considered
	Returns found index in the enum_members list"""
	if ',' in item:
		item = item[:item.index(',')].strip()
	i = 0
	for x in enum_members:
		if x.startswith(item):
			return i
		i += 1

	# smart matching:
	# item = 'MAX' matches enum 'MAXpeak'
	# item = 'SPECtrum1' matches enum 'SPEC1'
	# item = 'SPEC' matches enum 'SPECtrum1'

	item = ''.join([c for c in item if not c.islower()])
	# item must be longer than 1 character
	if len(item) < 2:
		return -1
	i = 0
	for x in enum_members:
		x_uc = ''.join([c for c in x if not c.islower()])
		if x_uc == item:
			return i
		i += 1
	return -1


def str_to_scalar_enum_helper(string: str, enum_type: Enum, enum_members=None) -> Enum:
	"""Converts string to one enum element.
	enum_members are optional to improve the performance for repeated conversions.
	If you do not provide them, they are generated inside the function."""
	value = Utilities.trim_str_response(string)
	if not enum_members:
		# noinspection PyTypeChecker
		enum_members = [x.name for x in enum_type]

	# Search in the enum member and return the index of the matched item
	ix = _find_in_enum_members(value, enum_members)
	if ix >= 0:
		# noinspection PyUnresolvedReferences
		return enum_type[enum_members[ix]]

	# If the result is -1 (not found), try to replace the special values and search again
	# This is done to improve the performance, since most of the enums have no special values
	enum_members_conv = [enum_value_to_scpi_string(x) for x in enum_members]
	ix = _find_in_enum_members(value, enum_members_conv)
	if ix >= 0:
		# noinspection PyUnresolvedReferences
		return enum_type[enum_members[ix]]

	# If not found, search in the special integer numbers:
	spec_value = str_special_values_to_int(value)
	if not spec_value:
		raise RsInstrException(f"String '{value}' can not be found in the enum type '{enum_type}'")
	# noinspection PyTypeChecker
	return spec_value


def str_to_simple_scalar_enum(string: str, enum_type, case_sensitive: bool = True, ignore_underscores: bool = False) -> Enum or None:
	"""Converts string to one enum element.
	Does not handle special value or non-mandatory parts."""
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


def str_to_list_enum_helper(string: str, enum_type: Enum, enum_members=None) -> List[Enum]:
	"""Converts string to list of enum elements.
	enum_members are optional to improve the performance for repeated conversions.
	If you do not provide them, they are generated inside the function."""
	if not enum_members:
		# noinspection PyTypeChecker
		enum_members = [x.name for x in enum_type]
	elements = string.split(',')
	return [str_to_scalar_enum_helper(x, enum_type, enum_members) for x in elements]


def enum_scalar_to_str(data, enum_type) -> str:
	"""Converts enum scalar value to string."""
	assert isinstance(data, enum_type), f"Expected command parameter {enum_type}, actual data type: {type(data)}. Value: {data}"
	return value_to_str(data)


def enum_list_to_str(data: List, enum_type) -> str:
	"""Converts enum list to csv-string."""
	# For enums, check that each element is an enum
	assert all(isinstance(x, enum_type) for x in data), f"Expected command parameter list of {enum_type}, detected one or more elements of non-enum type. Value: {data}"
	return list_to_csv_str(data)


def str_to_scalar_enum(string: str, enum_type) -> Enum:
	"""Converts string to one enum element."""
	return str_to_scalar_enum_helper(string, enum_type)


def str_to_list_enum(string: str, enum_type) -> List[Enum]:
	"""Converts string to list of enum elements."""
	return str_to_list_enum_helper(string, enum_type)
