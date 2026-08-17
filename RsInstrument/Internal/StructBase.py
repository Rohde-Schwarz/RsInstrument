"""See the docstring for the StructBase class."""

from .Types import DataType


class StructBase:
	"""Base class for all the driver's argument structures."""
	def __init__(self, owner):
		self.__meta_args_link = dict()
		ix = 0
		for arg in self.__get_meta_args_list(owner):
			arg.argument_ix = ix
			ix += 1

			if arg.data_type in [DataType.Enum, DataType.EnumExt, DataType.EnumList, DataType.EnumExtList]:
				assert arg.enum_type, f"Struct Argument '{arg.name}' is of enum type, you must define the parameter 'enum_type'"
			else:
				assert not arg.enum_type, f"Struct Argument '{arg.name}' data type is '{arg.data_type.name}'. You must set the parameter 'enum_type' to None"

			if arg.is_optional:
				# set all optional values to None
				setattr(self, arg.name, None)
			else:
				# set all mandatory values to their default values
				default = arg.data_type.get_default_value(arg.enum_type)
				setattr(self, arg.name, default)

	# noinspection PyMethodMayBeStatic
	def __get_meta_args_list(self, owner):
		args_list = getattr(owner, f'_{owner.__class__.__name__}__meta_args_list')
		return args_list
