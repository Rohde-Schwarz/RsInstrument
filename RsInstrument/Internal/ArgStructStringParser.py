"""See the class docstring."""

from . import Utilities
from .ArgStruct import ArgStruct
from .InstrumentErrors import RsInstrException


class ArgStructStringParser:
	"""Class for parsing a response from the instrument to an output structure of arguments.
	It is used by the ArgStructList class for filling structures with return values."""

	def __init__(self, struct, value: str):
		self.struct = struct
		self.elements = value.split(',')
		self.count = len(self.elements)
		self.position = 0

	@property
	def remaining(self) -> int:
		"""Remaining items to parse."""
		return self.count - self.position

	def to_scalar_value(self, arg: ArgStruct):
		"""Parses the current element to a scalar argument."""
		assert arg.data_type.is_scalar, f'to_scalar_value() method only works with scalar values. Data type: {arg.data_type}'
		if self.position >= self.count:
			raise RsInstrException(
				f"Cannot parse a scalar value to structure argument. Response contains only {self.count} elements, "
				f"argument '{arg.name}' has position {self.position + 1}.\n"
				f"Response (commas replaced by new lines):\n" + Utilities.truncate_string_from_end('\n'.join(self.elements), 1000))
		string = self.elements[self.position]
		value = arg.conv_from_scpi_string.get_one_element_value(string)
		setattr(self.struct, arg.name, value)
		self.position += 1

	def to_list_value(self, arg: ArgStruct, increase_pos: bool, offset: int, count: int, period: int, cycles: int) -> None:
		"""Parses more elements to the list argument - slicing."""
		assert arg.data_type.is_list, f'to_list_value method only works with list values. Data type: {arg.data_type}'
		if cycles < 0:
			cycles = self.remaining // period
		if self.position >= self.count:
			raise RsInstrException(
				f"Cannot parse an list value to the argument '{arg.name}', "
				f"because the element position {self.position} is over the parsed list length {self.count}")
		if (self.position + offset + count) > self.count:
			raise RsInstrException(
				f"Cannot parse the whole list value to the argument '{arg.name}', because the element position {self.position} "
				f"plus the argument offset {offset} and argument length {count} would be over the parsed list length {self.count}")

		result = []
		for cycle in range(cycles):
			start_ix = self.position + (cycle * period) + offset
			for i in range(count):
				result.append(arg.conv_from_scpi_string.get_one_element_value(self.elements[start_ix + i]))

		if increase_pos:
			self.position += count

		setattr(self.struct, arg.name, result)
