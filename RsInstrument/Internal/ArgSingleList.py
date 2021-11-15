"""Single argument definition for a list argument."""

from .ArgSingle import ArgSingle
from .ArgStringComposer import compose_cmd_string_from_single_args


class ArgSingleList(object):
	"""Contains methods for composing cmd string for the list of single arguments.
	Used in methods with 1+ set or query arguments.
	The instance does not have a fixed args list, you can use the instance method compose_cmd_string with different arguments."""

	def __init__(self):
		self.args = None

	def compose_cmd_string(self, arg1: ArgSingle, arg2: ArgSingle = None, arg3: ArgSingle = None, arg4: ArgSingle = None, arg5: ArgSingle = None, arg6: ArgSingle = None, arg7: ArgSingle = None, arg8: ArgSingle = None, arg9: ArgSingle = None):
		"""Composes the string cmd argument from the arguments list.
		Same treatment as in the ArgStructList.compose_cmd_string().
		The difference is in handling the value of the argument."""
		self.args = dict()

		ix = 0
		for arg in [arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9]:
			if arg:
				self.args[ix] = arg
				ix += 1

		return compose_cmd_string_from_single_args(self.args)
