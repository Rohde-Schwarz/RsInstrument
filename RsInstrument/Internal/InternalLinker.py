"""Links a variable from a structure to a callback in the driver."""

from time import time
from typing import Dict, Callable

from . import ArgSingle, ArgSingleSuppressed
from .ArgLinkedEventArgs import ArgLinkedEventArgs
from .Utilities import get_plural_string
from .InstrumentErrors import RsInstrException


class InternalLinker(object):
	"""Class for:
		- cutting out suppressed arguments from a device response.
		- invoking a handler if the argument has InternalLinking defined.
		- holds dictionary of handlers where the dict_key is the InternalLinking string.
	Handlers registration/deleting is done with:
		- set_handler()
		- del_handler()
		- del_all_handlers()"""

	def __init__(self):
		self._handlers = {}

	def __str__(self):
		if len(self._handlers) == 0:
			return 'Linker, no handlers'
		return f"Linker, {get_plural_string('handler', len(self._handlers))}: {','.join(self._handlers)}"

	def set_handler(self, link_name: str, handler: Callable) -> Callable:
		"""Adds / Updates handler for the link_name.
		Returns the previous registered handler, or None if no handler was registered before."""
		previous = None if link_name not in self._handlers else self._handlers[link_name]
		self._handlers[link_name] = handler
		return previous

	def del_handler(self, link_name: str) -> Callable:
		"""Deletes handler for the link_name.
		Returns the deleted handler, or None if none existed."""
		current = None if link_name not in self._handlers else self._handlers[link_name]
		if current:
			del self._handlers[link_name]
		return current

	def del_all_handlers(self) -> int:
		"""Deletes all the handlers.
		Returns number of deleted links."""
		count = len(self._handlers)
		self._handlers = {}
		return count

	def cut_from_response_string(self, arg: ArgSingleSuppressed, response: str, context: str) -> str:
		"""Takes the string 'response', removes the suppressed argument value from it and returns the rest.
		The cut-out part is sent via handler if the internal linking exists for that argument exists."""
		result = ''
		if arg.argument_ix is None:
			raise RsInstrException(f'Argument has argument_ix attribute not assigned (equals None). Argument: {arg}')
		if arg.argument_ix != 0:
			raise RsInstrException(f'Only arguments with index 0 can be suppressed. Argument: {arg}')
		if arg.is_open_list:
			raise RsInstrException(f'Open List arguments can not be suppressed. Argument: {arg}')
		repetition = 0
		i = 0
		for c in response:
			if c == ',':
				repetition += 1
			if repetition == arg.repetition:
				break
			i += 1

		suppressed_part = response[0:i]
		i += 1
		if i < len(response):
			result = response[i:]

		self.invoke_single_intern_link(arg, context, suppressed_part)
		return result

	def invoke_single_intern_link(self, arg: ArgSingleSuppressed or ArgSingle, context: str, value: str) -> None:
		"""Invokes the registered handler for the internal linked argument."""
		if arg.intern_link and arg.intern_link in self._handlers:
			event_args = ArgLinkedEventArgs(arg.intern_link, arg.name, value, context, time())
			self._handlers[arg.intern_link](event_args)

	def invoke_struct_intern_links(self, struct, args: Dict, context: str) -> None:
		"""Invokes handler for each of the Structure arguments that have internal linking."""
		for arg in args.values():
			if arg.intern_link and arg.intern_link in self._handlers:
				event_args = ArgLinkedEventArgs(arg.intern_link, arg.name, getattr(struct, arg.name), context, time())
				self._handlers[arg.intern_link](event_args)
