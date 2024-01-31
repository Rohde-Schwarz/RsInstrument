"""Contains definition for an argument that is suppressed and not exposed to the user.
Usually such arguments are also linked to a callback."""

from .Types import DataType


class ArgSingleSuppressed(object):
	"""Single suppressed Argument - used in Query_XxXx_Suppressed() to remove it from the returned value.
	It does not contain:
	- 'value' attribute, since this is discarded or linked internally directly  in the Query_XxXx_Suppressed().
	- 'is_optional' attribute, since it is always mandatory."""

	def __init__(self, argument_ix: int, data_type: DataType, is_open_list: bool = False, repetition: int = 1, intern_link: str = None):
		self.name = ''
		self.argument_ix = argument_ix
		self.data_type = data_type
		self.is_open_list = is_open_list
		self.repetition = repetition
		self.intern_link = intern_link

	def __str__(self):
		out = f"{self.data_type.name} '{self.name}' SuppressedArg"
		if self.is_open_list is False and self.repetition > 1:
			out += f' [{self.repetition}]'
		elif self.is_open_list is True:
			out += f' [{self.repetition}...]'

		if self.intern_link:
			out += f", Linking: '{self.intern_link}'"

		return out
