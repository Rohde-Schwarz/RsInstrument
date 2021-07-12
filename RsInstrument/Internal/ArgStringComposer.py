"""Provides:
- class SingleComposer - for composing SCPI string parameters from ArgSingle
- class StructComposer - for composing SCPI string parameters from ArgStruct
- function compose_cmd_string_from_struct_args - takes ArgStruct values and converts it to a SCPI string parameter.
- function compose_cmd_string_from_single_args - takes ArgSingle[] values and converts them to a SCPI string parameter.
The composing of the SCPI parameter string is similar for the ArgStruct and ArgSingle[] objects, therefore they share the same module."""

from typing import Dict

from .ArgSingle import ArgSingle
from .ArgStruct import ArgStruct
from .Utilities import get_plural_string
from .InstrumentErrors import RsInstrException


class SingleComposer:
	"""Composes strings for single argument.
	Provides Composer interface with 3 functions:
	- from_scalar_arg
	- from_list_arg
	- get_arg_list_size"""

	@staticmethod
	def from_scalar_arg(arg: ArgSingle) -> str:
		"""Takes argument's scalar value and converts it to a SCPI parameter string."""
		if not arg.is_optional and arg.value is None:
			raise ValueError(f"StructArgComposer.from_scalar_arg() - mandatory argument's '{arg.name}' value is None")
		assert arg.data_type.is_scalar, f"StructArgComposer.from_scalar_arg() - argument '{arg.name}' must be scalar. Data type: '{arg.data_type}'"
		if arg.value is None:
			return ''
		return arg.conv_to_scpi_string.get_value(arg.value)

	@staticmethod
	def from_list_arg(arg: ArgSingle, start_ix=0, items_count=-1) -> str:
		"""Takes argument's List of elements and converts it to a csv-string of SCPI parameters.
		start_ix defines where to start in the list.
		items_count defines how many items to take. -1 means all of them"""
		if not arg.is_optional and arg.value is None:
			raise ValueError(f"StructArgComposer.from_list_arg() - mandatory argument's '{arg.name}' value is None")
		assert arg.data_type.is_list, f"StructArgComposer.from_list_arg() - argument must be list. Data type: '{arg.data_type}'"
		if not arg.is_optional:
			assert arg.value is not None, f"StructArgComposer.from_list_arg() - mandatory argument's '{arg.name}' value is None"
		if arg.value is None:
			return ''
		if start_ix == 0 and items_count < 0:
			return arg.conv_to_scpi_string.get_value(arg.value)
		elif items_count < 0:
			return arg.conv_to_scpi_string.get_value(arg.value[start_ix])
		elif items_count == 0:
			return ''
		elif items_count > 0:
			return arg.conv_to_scpi_string.get_value(arg.value[start_ix: start_ix + items_count])

	@staticmethod
	def get_arg_list_size(arg: ArgSingle) -> int:
		"""Returns list size of the argument assuming it is a list.
		If the argument is not a list, the method returns -1."""
		if arg.data_type.is_scalar:
			return -1
		else:
			return len(arg.value)


class StructComposer:
	"""Composes strings for structure arguments.
	Provides Composer interface with 3 functions:
	- from_scalar_arg
	- from_list_arg
	- get_arg_list_size \n
	The StructComposer constructor has the owning struct instance as parameter, because this is needed to access the argument value."""

	def __init__(self, struct):
		self.struct = struct

	def from_scalar_arg(self, arg: ArgStruct) -> str:
		"""Returns a single argument value converted to string."""
		assert arg.data_type.is_scalar, f"StructArgComposer.from_scalar_arg() - argument must be scalar. Data type: '{arg.data_type}'"
		return arg.conv_to_scpi_string.get_value(getattr(self.struct, arg.name))

	def from_list_arg(self, arg: ArgStruct, start_ix=0, items_count=-1) -> str:
		"""Returns csv-string with all the elements from the argument value."""
		assert arg.data_type.is_list, f"StructArgComposer.from_list_arg() - argument must be list. Data type: '{arg.data_type}'"
		if start_ix == 0 and items_count < 0:
			return arg.conv_to_scpi_string.get_value(getattr(self.struct, arg.name))
		elif items_count < 0:
			return arg.conv_to_scpi_string.get_value(getattr(self.struct, arg.name)[start_ix])
		elif items_count == 0:
			return ''
		elif items_count > 0:
			return arg.conv_to_scpi_string.get_value(getattr(self.struct, arg.name)[start_ix: start_ix + items_count])

	def get_arg_list_size(self, arg: ArgStruct) -> int:
		"""Returns list size of the argument assuming it is a list.
		If the argument is not a list, the method returns -1."""
		if arg.data_type.is_scalar:
			return -1
		else:
			return len(getattr(self.struct, arg.name))


def compose_cmd_string_from_struct_args(args: Dict[int, ArgStruct], composer: StructComposer, values_obj: object) -> str:
	"""Returns SCPI-composed string based on the structure args specification."""
	arg_count = len(args)
	string_arg = []
	arg_ix = 0
	opt_null_ix = -1

	# Non-repeated arguments - single values or arrays which are not open lists
	# Non-open lists or scalars must be at the beginning of the definition
	# Once the first open list argument is detected, continue further
	while arg_ix < arg_count and args[arg_ix].is_open_list is False:
		arg = args[arg_ix]
		if arg.has_value(values_obj) is False:
			arg.assert_is_optional(values_obj)
			# The optional argument, which has no value. End the entire string_arg composition
			opt_null_ix = arg_ix
			break

		if arg.repetition <= 1:
			# No list, but scalar value
			string_arg.append(composer.from_scalar_arg(arg))
		else:
			string_arg.append(composer.from_list_arg(arg, 0, arg.repetition))

		arg_ix += 1
	# End of non-repeated arguments

	# If the optional argument without a value was not found, check if there are some more arguments to go through
	if opt_null_ix < 0 and arg_ix < arg_count:
		# Still some args to go
		arg = args[arg_ix]
		if arg.is_open_list:
			# The previous loop ended because the next argument had is_open_list = True
			if arg_ix == (arg_count - 1):
				if arg.has_value(values_obj):
					# The last argument, ignore the repetitions and convert the whole list to string
					string_arg.append(composer.from_list_arg(arg))
				else:
					# The optional argument, which has no value. End the entire string_arg composition
					arg.assert_is_optional(values_obj)
					opt_null_ix = arg_ix
			else:
				# More than one arguments remaining. Loop through them interleaving the result strings
				# Interleaving arguments must all have values

				# Check if each list has at least Repetition number of elements
				cycles_error = False
				alignments_error = False
				cycle = -1
				data = {}
				for x in range(arg_ix, arg_count):
					arg = args[x]
					curr_size: int = composer.get_arg_list_size(arg)
					curr_cycle: int = curr_size // arg.repetition
					curr_align: int = curr_size % arg.repetition
					data[x] = (curr_size, curr_cycle, curr_align)

					if curr_size < 0:
						raise RsInstrException(f"Argument '{arg.name}' has repetitions, therefore it must be declared as a list. Current Declaration: '{arg.data_type}'")

					if arg.repetition > curr_size:
						raise RsInstrException(f"Argument '{arg.name}' has repetitions {arg.repetition}, but its list size is only {curr_size}")

					# noinspection PyChainedComparisons
					if cycle >= 0 and curr_cycle != cycle:
						cycles_error = True

					cycle = curr_cycle

					if curr_align != 0:
						alignments_error = True

				if cycles_error:
					message = 'Arguments interleaving is not aligned - all the cycles must be the same. Actual cycles:\n'
					for x in range(arg_ix, arg_count):
						message += f'{args[x].name}[{data[x][0]}] sliced by {get_plural_string("element", args[x].repetition)} ' \
							f'results in {data[x][0] / args[x].repetition} cycles\n'
					raise RsInstrException(message)

				if alignments_error:
					message = 'At least one argument has a list size not dividable by the defined repetitions:\n'
					for x in range(arg_ix, arg_count):
						message += f'{args[x].name}[{data[x][0]}] modulo {args[x].repetition}x results in {data[x][0] % args[x].repetition}\n'
					raise RsInstrException(message)

				for x in range(cycle):
					for y in range(arg_ix, arg_count):
						arg = args[y]
						string_arg.append(composer.from_list_arg(arg, arg.repetition * x, arg.repetition))

	if opt_null_ix >= 0:
		# Check the rest of the optional values, all of them must be without a value
		rest = []
		for y in range(opt_null_ix, arg_count):
			arg = args[y]
			if arg.has_value(values_obj):
				rest.append(arg.name)

		if len(rest):
			msg = f"Optional Argument '{args[opt_null_ix].name}' has no value, but the further ones do. " \
				f"If you skip an optional argument, you have to skip all the ones following it. " \
				f"Clear the values for the rest of the argument(s):\n{', '.join(rest)}"
			raise RsInstrException(msg)

	return ','.join(string_arg)


def compose_cmd_string_from_single_args(args: Dict[int, ArgSingle]) -> str:
	"""Returns SCPI-composed string based on the single args specification.
	We can use the same function as for the struct arguments, with the difference of providing a SingleComposer.
	Parameter value_obj is set to None, since each argument holds the value itself."""
	# noinspection PyTypeChecker
	return compose_cmd_string_from_struct_args(args, SingleComposer(), None)
