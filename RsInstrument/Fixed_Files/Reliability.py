"""Class for R&S Mobile Radio Test instruments that use reliability indicators."""


import time
from typing import Callable

from ..Internal import ArgLinkedEventArgs
from ..Internal import Core

codes_table = {
				0:       'OK',
				1:       'Measurement Timeout',
				2:       'Capture Buffer Overflow',
				3:       'Over-driven',
				4:       'Under-driven',
				6:       'Trigger Timeout',
				7:       'Acquisition Error',
				8:       'Sync Error',
				9:       'Uncalibrated',
				15:      'Reference Frequency Error',
				16:      'RF Not Available',
				17:      'RF Level not Settled',
				18:      'RF Frequency not Settled',
				19:      'Call not Established',
				20:      'Call Type not Usable',
				21:      'Call Lost',
				23:      'Missing Option',
				24:      'Invalid RF Setting',
				26:      'Resource Conflict',
				27:      'No Sensor Connected',
				28:      'Unexpected Parameter Change',
				30:      'File not Found',
				31:      'No DTM reply',
				32:      'ACL Disconnected',
				40:      'ARB File CRC Error',
				42:      'ARB Header Tag Invalid',
				43:      'ARB Segment Overflow',
				44:      'ARB File not Found',
				45:      'ARB Memory Overflow',
				46:      'ARB Sample Rate out of Range',
				47:      'ARB Cycles out of Range',
				50:      'Startup Error',
				51:      'No Reply',
				52:      'Connection Error',
				53:      'Configuration Error',
				54:      'Filesystem Error',
				60:      'Invalid RF-Connector Setting',
				93:      'OCXO Oven Temperature too low',
				101:     'Firmware Error',
				102:     'Unidentified Error',
				103:     'Parameter Error',
				104:     'Not Functional'}


class ReliabilityEventArgs:
	"""Arguments for reliability indicator event."""

	def __init__(self, timestamp, code: int, message: str, context: str):
		self.timestamp = timestamp
		self.message = message
		self.code = code
		self.message = message
		self.context = context


class Reliability:
	"""Reliability class that handles all the necessary tasks related to reliability indicator."""

	def __init__(self, core: Core):
		self._core: Core = core
		self._last_value: int = 0
		self._last_context: str = ''
		self._last_timestamp = None
		self._exception_on_error = False
		# noinspection PyTypeChecker
		self._on_update_handler: Callable = None
		self._core.set_link_handler('Reliability', self._permanent_on_update_handler)

	@property
	def last_value(self) -> int:
		"""Returns the last updated Reliability code."""
		return self._last_value

	@property
	def last_context(self) -> str:
		"""Returns the last updated Context of the reliability code - usually the SCPI query on which the instrument responded with the Reliability code."""
		return self._last_context

	@property
	def last_timestamp(self) -> time:
		"""Returns the time of the last Reliability update."""
		return self._last_timestamp

	@property
	def last_message(self) -> str:
		"""Returns the LastValue of the reliability table converted to human-readable string."""
		if self._last_value in codes_table:
			return codes_table[self._last_value]
		else:
			return f'Undefined reliability code {self._last_value}.'

	@property
	def exception_on_error(self) -> bool:
		"""If True, (default is False) the object throws an exception if the updated reliability is not 0 (non-OK)."""
		return self._exception_on_error

	@exception_on_error.setter
	def exception_on_error(self, value) -> None:
		"""If True, (default is False) the object throws an exception if the updated reliability is not 0 (non-OK)."""
		self._exception_on_error = value

	def on_update_handler(self, handler: Callable) -> None:
		"""Register the handler for on_update event.
		This handler is invoked with each update of the reliability indicator.
		Handler API: handler(event_args: ReliabilityEventArgs)"""
		self._on_update_handler = handler

	def _permanent_on_update_handler(self, event_args: ArgLinkedEventArgs) -> None:
		"""Permanent on_update handler. Takes care of updating all the 'last_xxx' values and calling a user-defined updated_handler."""
		self._last_value = int(str(event_args.value))
		self._last_context = event_args.context
		self._last_timestamp = event_args.timestamp
		if self._on_update_handler:
			# Call the additional handler if registered
			rel_events_args = ReliabilityEventArgs(self._last_timestamp, self._last_value, self.last_message, self._last_context)
			self._on_update_handler(rel_events_args)
		if self._exception_on_error and self._last_value != 0:
			raise Exception(
				f'Reliability indicator error. Time: {time.strftime("%H:%M:%S", time.localtime(self._last_timestamp))}, '
				f'Context: {self._last_context}, Value {self._last_value}: {self.last_message}')

	def sync_from(self, source: 'Reliability') -> None:
		"""Synchronises this Reliability with the source."""
		self.exception_on_error = source.exception_on_error
		self.on_update_handler(source._on_update_handler)
