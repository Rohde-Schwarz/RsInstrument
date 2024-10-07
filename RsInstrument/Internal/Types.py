"""Data type class for the variables containing all the methods related to data types."""

from enum import Enum, auto
from typing import Any


# noinspection PyArgumentList
class DataType(Enum):
	"""Data type of variable in the driver."""
	String = auto()
	RawString = auto()
	Integer = auto()
	IntegerExt = auto()
	Boolean = auto()
	Float = auto()
	FloatExt = auto()
	Enum = auto()
	EnumExt = auto()
	StringList = auto()
	RawStringList = auto()
	IntegerList = auto()
	IntegerExtList = auto()
	BooleanList = auto()
	FloatList = auto()
	FloatExtList = auto()
	EnumList = auto()
	EnumExtList = auto()

	@property
	def is_list(self) -> bool:
		"""Returns True, if the data type is a list."""
		return self in frozenset(
			{
				DataType.StringList,
				DataType.RawStringList,
				DataType.IntegerList,
				DataType.IntegerExtList,
				DataType.BooleanList,
				DataType.FloatList,
				DataType.FloatExtList,
				DataType.EnumList,
				DataType.EnumExtList
			})

	@property
	def is_scalar(self) -> bool:
		"""Returns True, if the data type is a scalar."""
		return not self.is_list

	@property
	def is_scalar_enum(self) -> bool:
		"""Returns True, if the data type is a scalar enum or enum_ext."""
		return self == DataType.Enum or self == DataType.EnumExt

	@property
	def is_list_enum(self) -> bool:
		"""Returns True, if the data type is a list enum or list enum_ext."""
		return self == DataType.EnumList or self == DataType.EnumExtList

	@property
	def is_enum(self) -> bool:
		"""Returns True, if the data type is enum or enum array - including the extended."""
		return self in [DataType.Enum, DataType.EnumExt, DataType.EnumList, DataType.EnumExtList]

	@property
	def is_raw_string(self) -> bool:
		"""Returns True for raw string and raw string list."""
		return self == DataType.RawString or self == DataType.RawStringList

	@property
	def is_boolean(self) -> bool:
		"""Returns True for boolean and boolean list."""
		return self == DataType.Boolean or self == DataType.BooleanList

	@property
	def is_string(self) -> bool:
		"""Returns True for string and string list."""
		return self == DataType.String or self == DataType.StringList

	@property
	def element_type(self):
		"""For lists, the property returns type of the element.
		For scalars, it returns the same type."""
		if self.is_scalar:
			return self
		elif self == DataType.StringList:
			return DataType.String
		elif self == DataType.RawStringList:
			return DataType.RawString
		elif self == DataType.RawStringList:
			return DataType.RawString
		elif self == DataType.BooleanList:
			return DataType.Boolean
		elif self == DataType.IntegerList:
			return DataType.Integer
		elif self == DataType.IntegerExtList:
			return DataType.IntegerExt
		elif self == DataType.FloatList:
			return DataType.Float
		elif self == DataType.FloatExtList:
			return DataType.FloatExt
		elif self == DataType.EnumList:
			return DataType.Enum
		elif self == DataType.EnumExtList:
			return DataType.EnumExt

	def get_default_value(self, enm: Enum = None) -> Any:
		"""Returns default value for the current type.
		If the data type is Enum or EnumString, you have to provide the enum class."""
		if self.is_list:
			return []
		if self == DataType.RawString:
			return ''
		elif self == DataType.String:
			return ''
		elif self == DataType.Boolean:
			return False
		elif self == DataType.Integer:
			return 0
		elif self == DataType.IntegerExt:
			return 0
		elif self == DataType.Float:
			return 0.0
		elif self == DataType.FloatExt:
			return 0.0
		elif self == DataType.Enum:
			return enm(0)
		elif self == DataType.EnumExt:
			return enm(0)
