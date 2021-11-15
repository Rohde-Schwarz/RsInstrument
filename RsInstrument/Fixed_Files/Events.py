"""Event-related methods and properties. Here you can set all the event handlers."""

from typing import Callable

from ..Internal import Core


class Events:
	"""Common Events class.
	Event-related methods and properties. Here you can set all the event handlers."""
	def __init__(self, core: Core):
		self._core = core

	@property
	def io_events_include_data(self) -> bool:
		"""Returns the current state of the io_events_include_data See the setter for more details."""
		return self._core.io.io_events_include_data

	@io_events_include_data.setter
	def io_events_include_data(self, value: bool) -> None:
		"""If True, the on_write and on_read events include also the sent/received data.
		Default value is False, to avoid handling potentially big data."""
		self._core.io.io_events_include_data = value

	@property
	def before_write_handler(self) -> Callable:
		"""Returns the handler of before_write events. \n
		:return: current ``before_write_handler``"""
		return self._core.io.before_write_handler

	@before_write_handler.setter
	def before_write_handler(self, handler: Callable) -> None:
		"""Sets handler for before_write events.
		The before_write event is invoked before each write operation (only once, not for every chunk)
		Event prototype: handler(io: Instrument, cmd: str)
		:param handler: new handler"""
		self._core.io.before_write_handler = handler

	@property
	def on_write_handler(self) -> Callable:
		"""Returns the handler of on_write events. \n
		:return: current ``on_write_handler``"""
		return self._core.io.on_write_handler

	@on_write_handler.setter
	def on_write_handler(self, handler: Callable) -> None:
		"""Sets handler for on_write events.
		The on_write event is invoked every time the driver performs a write operation to the instrument (for each write chunk)
		Event arguments type: IoTransferEventArgs
		By default, the event_args do not contain the actual data sent. If you wish to receive them, set the driver.Events.io_events_include_data to True \n
		:param handler: new handler for all write operations"""
		self._core.io.on_write_handler = handler

	@property
	def on_read_handler(self) -> Callable:
		"""Returns the handler of on_read events. \n
		:return: current ``on_read_handler``"""
		return self._core.io.on_read_handler

	@on_read_handler.setter
	def on_read_handler(self, handler: Callable) -> None:
		"""Sets handler for on_read events.
		The on_read event is invoked every time the driver performs a read operation to the instrument.
		Event arguments type: IoTransferEventArgs
		By default, the event_args do not contain the actual data sent. If you wish to receive them, set the driver.Events.io_events_include_data to True \n
		:param handler: new handler for all read operations"""
		self._core.io.on_read_handler = handler

	@property
	def before_query_handler(self) -> Callable:
		"""Returns the handler of before_query events. \n
		:return: current ``before_query_handler``"""
		return self._core.io.before_query_handler

	@before_query_handler.setter
	def before_query_handler(self, handler: Callable) -> None:
		"""Sets handler for before_query events.
		The before_query event is invoked before each query operation (only once, not for every chunk)
		Event prototype: handler(io: Instrument, query: str)
		:param handler: new handler"""
		self._core.io.before_query_handler = handler
