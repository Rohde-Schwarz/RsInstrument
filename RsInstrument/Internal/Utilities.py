"""Utilities for string manipulation and string formatting for the user."""

from enum import Flag
from typing import Tuple

si_units = {-12: "T", -9: "G", -6: "M", -3: "k", 0: "", 3: "m", 6: "u", 9: "n", 12: "p", 15: "f"}


class TrimStringMode(Flag):
	"""Trimming mode for strings."""
	white_chars_only = 1
	white_chars_single_quotes = 2
	white_chars_double_quotes = 3
	white_chars_all_quotes = 4


def trim_str_response(text: str, mode=TrimStringMode.white_chars_all_quotes) -> str:
	"""Trims instrument string response.
	In modes white_chars_all_quotes, white_chars_single_quotes, white_chars_double_quotes:
	All the symmetrical leading and trailing quotation marks are trimmed,
	but only if there are none in the remaining text."""
	first_sq_ix = -1
	first_dq_ix = -1
	rem_sq = True if (mode == TrimStringMode.white_chars_all_quotes or mode == TrimStringMode.white_chars_single_quotes) else False
	rem_dq = True if (mode == TrimStringMode.white_chars_all_quotes or mode == TrimStringMode.white_chars_double_quotes) else False

	if not text:
		return text
	text = text.strip()
	if rem_sq and text == "''":
		return ''
	if rem_dq and text == '""':
		return ''
	start_ix = 0
	end_ix: int = len(text) - 1
	if end_ix - 2 < start_ix:
		return text
	if mode is not TrimStringMode.white_chars_only:
		# Loop to cut the outer paired quotation marks
		trimmed = True
		while trimmed:
			trimmed = False
			if rem_sq and text[start_ix] == "'" and text[end_ix] == "'":
				if first_sq_ix < 0:
					first_sq_ix = start_ix
				start_ix += 1
				end_ix -= 1
				trimmed = True
			if end_ix - 2 < start_ix:
				break
			if rem_dq and text[start_ix] == '"' and text[end_ix] == '"':
				if first_dq_ix < 0:
					first_dq_ix = start_ix
				start_ix += 1
				end_ix -= 1
				trimmed = True
			if end_ix - 2 < start_ix:
				break
		if start_ix == 0:
			return text

		final_cut_ix = start_ix
		shortened_text = text[start_ix: -start_ix]
		if first_sq_ix >= 0 and "'" in shortened_text:
			# The cut quotes are also in the shortened string, do not removed the quotes, and set the cutting to start_ix
			final_cut_ix = first_sq_ix
		if first_dq_ix >= 0 and '"' in shortened_text:
			if final_cut_ix > first_dq_ix:
				final_cut_ix = first_dq_ix

		if final_cut_ix == 0:
			return text

		text = text[final_cut_ix: -final_cut_ix]

	return text


def truncate_string_from_end(string: str, max_len: int) -> str:
	"""If the string len is below the max_len, the function returns the same string.
	If the string is above the max len, the function returns only the last max_len characters plus '...' at the beginning."""
	if len(string) <= max_len:
		return string
	return f'Last {max_len} chars: "...{string[-max_len:]}"'


def get_plural_string(word: str, amount: int) -> str:
	"""Returns singular or plural of the word depending on the amount.
	Example:
		word = 'piece', amount = 0 -> '0 pieces'
		word = 'piece', amount = 1 -> '1 piece'
		word = 'piece', amount = 5 -> '5 pieces'"""
	if amount == 1:
		return f'1 {word}'
	else:
		return f'{amount} {word}s'


def parse_token_to_key_and_value(token: str) -> Tuple[str, str]:
	"""Parses entered string to name and value with the delimiter '='.
	If the token is empty: name = None, value = None.
	If the '=' is not found: name = token, value = None.
	name is trimmed for white spaces.
	value is trimmed with trim_str_response()."""
	token = token.strip()
	if not token:
		# noinspection PyTypeChecker
		return None, None
	if '=' in token:
		data = token.split('=')
		name = data[0].strip()
		value = trim_str_response(data[1])
		return name, value

	# noinspection PyTypeChecker
	return token.strip(), None


def size_to_kb_mb_gb_string(data_size: int, as_additional_info: bool = False, allow_gb: bool = True) -> str:
	"""Returns human-readable string with kilobytes, megabytes or gigabytes
	depending on the data_size range. \n
		:param data_size: data size in bytes to convert
		:param allow_gb: allow also Gigabytes size
		:param as_additional_info:
		if True, the dynamic data appear in round bracket after the number in bytes. e.g. '12345678 bytes (11.7 MB)'
		if False, only the dynamic data is returned e.g. '11.7 MB' """
	size_abs = data_size
	if data_size < 0:
		size_abs = - data_size

	if size_abs < 1024:
		as_additional_info = False
		dynamic = f'{data_size} bytes'
	elif size_abs < 1048576:
		dynamic = f'{data_size / 1024:0.1f} kB'
	else:
		if size_abs < 1073741824 or allow_gb is False:
			dynamic = f'{data_size / 1048576:0.1f} MB'
		else:
			dynamic = f'{data_size / 1073741824:0.1f} GB'

	if as_additional_info:
		return f'{data_size} bytes ({dynamic})'
	else:
		return dynamic


def size_to_kb_mb_string(data_size: int, as_additional_info: bool = False) -> str:
	"""Returns human-readable string with kilobytes or megabytes depending on the data_size range. \n
		:param data_size: data size in bytes to convert
		:param as_additional_info:
		if True, the dynamic data appear in round bracket after the number in bytes. e.g. '12345678 bytes (11.7 MB)'
		if False, only the dynamic data is returned e.g. '11.7 MB' """
	return size_to_kb_mb_gb_string(data_size, as_additional_info, False)


def value_to_si_string(value: float, fmt: str = ".12g", min_decimal_places: int = 0, str_after_number: str = ' ') -> str:
	"""Returns the entered float value converted to string with SI notation.
		:param value: input float value
		:param fmt: formatting of the number. Default: '.12g'
		:param min_decimal_places: assures minimal number of decimal places.
		If you set the number > 0, the function makes sure the decimal places are kept, and
		if there are less of them, they are filled with nulls ('.000' or '000') Default: 0
		Examples:
			- value = 1, fmt = '.12g', min_decimal_places = 0, result -> '1'
			- value = 1, fmt = '.12g', min_decimal_places = 3, result -> '1.000'
		:param str_after_number: string after number, if the SI suffix is present. Default: ' '

		Examples:
			- 1.23 -> '1.23'
			- 1.23E3 -> '1.23 k'
			- 2.56E9 -> '2.56 G'
			- 11.3E-6 -> '-11.3 u'

		This function is useful for user-readable string outputs.
	"""
	if value == 0:
		num_result = ('{0:' + fmt + '}').format(value)
		k = 0
	else:
		k = -12
		minus = value < 0
		if minus:
			value = - value
		while value * 10.0 ** k < 1:
			k += 3
		if minus:
			value = -value

		fmt = '{0:' + fmt + '}'
		if k == 0:
			num_result = fmt.format(value)
		else:
			num_result = fmt.format(value * 10.0 ** k)

	# assure minimal decimal places
	if min_decimal_places > 0 and len(num_result) > 0:
		if num_result[-1].isdigit():
			pos = num_result.find('.')
			if pos == -1:
				num_result += "." + '0' * min_decimal_places
			else:
				to_fill = min_decimal_places - (len(num_result) - pos - 1)
				if to_fill > 0:
					num_result += '0' * to_fill

	if k == 0:
		return num_result
	else:
		return num_result + str_after_number + si_units[k]


def calculate_chunks_count(data_size: int, chunk_size: int) -> int:
	"""Returns number of chunks needed to transfer the data_size split to maximum of chunk_size blocks. \n
	:param data_size: total data size
	:param chunk_size: maximum size of one block"""
	return (data_size // chunk_size) + (1 if (data_size % chunk_size) > 0 else 0)


def escape_nonprintable_chars(string: str, encoding: str = 'charmap') -> str:
	"""
	Replace nonprintable characters in string s by its hex representation.
	"""
	if string.isprintable():
		return string
	new_string = ''
	for char in string:
		if char.isprintable():
			new_string += char
		elif char == '\n':
			new_string += r'\n'
		elif char == '\r':
			new_string += r'\r'
		elif char == '\t':
			new_string += r'\t'
		else:
			byte = bytes(char, encoding)
			char = byte.hex()
			new_string += r'\x' + char
	return new_string


def shorten_string_middle(string: str, max_len: int) -> str:
	"""If the length of the string is bigger than the max_len,
	the middle of the string is abbreviated with ' .... ' """
	count = len(string)
	if count <= max_len:
		return string
	half = int((max_len - 6) / 2)
	md = (max_len - 6) % 2
	return string[:half + md] + ' .... ' + string[(count - half):]
