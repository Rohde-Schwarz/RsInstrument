"""See the docstring for the RepeatedCapability class."""

from enum import Enum


# Command integer value that signals Default value "DEFAULT"
VALUE_DEFAULT = -1

# Command integer value that signals "EMPTY"
VALUE_EMPTY = -2


class RepeatedCapability(object):
	"""Represents Repeated Capability value and type"""

	def __init__(self, header_name: str, method_get_name: str, method_set_name: str, start_value: Enum):
		"""Constructor with header name, group property name and the start value"""

		self._enum_value = None
		self.enum_type = start_value.__class__
		self.name = self.enum_type.__name__
		self.header_name = header_name
		self.method_get_name = method_get_name
		self.method_set_name = method_set_name
		self._start_value = start_value
		self.set_to_start_value()

	def __str__(self) -> str:
		out = f'RepCap {self.name}'
		if self._enum_value is not None:
			out += f" = {self._enum_value}"
		return out

	@classmethod
	def clsm_assert_type(cls, enum_value: Enum, enum_type) -> None:
		"""Static assertion function to check if the entered value is a member of the defined repcap enum"""
		if not isinstance(enum_value, enum_type):
			raise TypeError(f"RepCap value must be of type '{enum_type}'. Entered value type: {type(enum_value)}, value '{enum_value}'")

	@classmethod
	def clsm_get_direct_cmd_value_int(cls, enum_value: Enum, enum_type) -> int:
		"""Static function to get an integer interpretation of a direct enum value
		Does not work with Empty or Default"""
		RepeatedCapability.clsm_assert_type(enum_value, enum_type)
		return enum_value.value

	@classmethod
	def clsm_is_default_value(cls, enum_value: Enum, enum_type) -> bool:
		"""Returns True, if the entered value is enum.Default"""
		return cls.clsm_get_direct_cmd_value_int(enum_value, enum_type) == VALUE_DEFAULT

	def is_default_value(self) -> bool:
		"""Returns True, if the repcap value is enum.Default"""
		return RepeatedCapability.clsm_is_default_value(self._enum_value, self.enum_type)

	def set_enum_value(self, enum_value: Enum) -> None:
		"""Sets new enum value. Can not be Default"""
		if RepeatedCapability.clsm_is_default_value(enum_value, self.enum_type):
			raise ValueError(f"Setting RepCap enum value '{enum_value}' is not allowed. Please select a concrete value")
		self._enum_value = enum_value

	def get_enum_value(self) -> Enum:
		"""Returns the actual enum value"""
		return self._enum_value

	def set_to_start_value(self) -> None:
		"""Sets back to the value entered in the constructor"""
		self.set_enum_value(self._start_value)

	def matches_type(self, enum_type) -> bool:
		"""Returns true, if the entered type matches the EnumType"""
		return self.enum_type == enum_type

	@classmethod
	def clsm_get_cmd_string_value(cls, enum_value: Enum, enum_type) -> str:
		"""Converts RepCap integer value to string
		ValueEmpty is converted to "" (Not valid, but tolerated)
		ValueDefault throws an exception
		0 is converted to "" (Not valid, but tolerated)
		Positive numbers are converted to integer strings e.g. 1 => '1' """
		number = cls.clsm_get_direct_cmd_value_int(enum_value, enum_type)
		if number == VALUE_EMPTY:
			return ''
		if number == 0:
			# return empty string, if the enum definition does not contain a valid element with value 0
			enum_values = [x.value for x in enum_type]
			return '0' if 0 in enum_values else ''
		if number == VALUE_DEFAULT:
			raise ValueError(f"RepCap enum value Default can not be converted to the command string value. RepCap: {enum_type}")
		return str(number)

	def get_cmd_string_value(self) -> str:
		"""Converts RepCap integer value to string
		ValueEmpty is converted to "" (Not valid, but tolerated)
		ValueDefault throws an exception
		0 is converted to "" (Not valid, but tolerated)
		Positive numbers are converted to integer strings e.g. 1 => '1' """
		return RepeatedCapability.clsm_get_cmd_string_value(self._enum_value, self.enum_type)
