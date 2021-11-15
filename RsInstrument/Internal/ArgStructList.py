"""See the class docstring."""

from .ArgStringComposer import StructComposer, compose_cmd_string_from_struct_args
from .ArgStructStringParser import ArgStructStringParser
from .StructBase import StructBase
from .InstrumentErrors import RsInstrException


class ArgStructList(object):
	"""Contains methods for composing cmd string and parsing cmd response to the provided structure instance."""

	RAW_DATA_PROP_NAME = 'RawReturnData'

	def __init__(self, struct):
		self.__struct = struct
		self.args = self.__get_struct_arg_attrs()

	def __str__(self):
		return f"'{self.__struct.__class__.__name__}', {len(self.args)} args: [ {', '.join([self.args[x].name for x in self.args])} ]"

	def __get_struct_arg_attrs(self):
		"""Fills self.args with the dictionary of ArgStruct list.
		Dictionary key is the argument order (argument_ix)."""
		# noinspection PyUnresolvedReferences,PyProtectedMember
		args_list = StructBase._StructBase__get_meta_args_list(None, self.__struct)
		# meta_data = getattr(self.__struct, '_{}__meta_args_list'.format(self.__struct.__class__.__name__))
		args = dict()
		for x in args_list:
			args[x.argument_ix] = x

		return args

	def parse_from_cmd_response(self, content: str):
		"""Fills the structure from the entered string content (command response)."""
		if hasattr(self.__struct, ArgStructList.RAW_DATA_PROP_NAME):
			setattr(self.__struct, ArgStructList.RAW_DATA_PROP_NAME, content)

		parser = ArgStructStringParser(self.__struct, content)
		arg_count = len(self.args)
		arg_ix = 0

		# Non-repeated arguments
		while arg_ix < arg_count and self.args[arg_ix].is_open_list is False:
			arg = self.args[arg_ix]
			if arg.repetition <= 1:
				# No list, but scalar value
				parser.to_scalar_value(arg)
			else:
				# List with a fixed size, not repeated
				parser.to_list_value(arg, True, 0, arg.repetition, arg.repetition, 1)

			arg_ix += 1

		if arg_ix < arg_count:
			arg = self.args[arg_ix]
			# Still some args to go
			if arg.is_open_list is True:
				# The previous loop ended because the next argument had is_open_list True
				if arg_ix == (arg_count - 1):
					# This is the last argument, ignore the repetitions and take the whole rest of the elements
					parser.to_list_value(arg, True, 0, parser.remaining, parser.remaining, 1)
				else:
					# More than one arguments remaining. Loop through them interleaving the result strings
					open_list_args = {key: value for key, value in self.args.items() if key >= arg_ix}

					# Accumulate the number of repetitions from all the open_list_args
					period: int = sum(open_list_args[ix].repetition for ix in open_list_args)
					reminder: int = parser.remaining % period
					if reminder != 0:
						raise RsInstrException(
							f'Arguments parsing is not aligned - source string elements remaining to parse {parser.remaining}'
							f'is not dividable by the summary Period {period} of all the open list arguments:\n' + '\n'.join(['{}'.format(x) for x in open_list_args]))
					# Go through the arguments and accumulate the list content
					offset = 0
					for x in open_list_args:
						arg = open_list_args[x]
						parser.to_list_value(arg, False, offset, arg.repetition, period, -1)
						offset += arg.repetition

	def compose_cmd_string(self):
		"""Composes the string argument from the structure for sending to the instrument."""
		return compose_cmd_string_from_struct_args(self.args, StructComposer(self.__struct), self.__struct)
