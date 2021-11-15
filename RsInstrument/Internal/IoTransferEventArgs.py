"""See the docstring for the IoTransferEventArgs class."""

import itertools
from typing import AnyStr

from .Utilities import size_to_kb_mb_string


class IoTransferEventArgs(object):
	"""Contains event data for driver read or write operations."""
	# first generated is 100
	id_generator = itertools.count(100)

	# noinspection PyTypeChecker
	def __init__(self, reading: bool, opc_sync: bool, total_size: int or None, context: str):
		"""Initializes new instance of IoTransferEventArgs
		:param reading: True: reading operation, False: writing operation
		:param opc_sync: defines if the command is OPC-synchronised
		:param total_size: total size of the data received
		:param context: SCPI query. It is truncated to maximum of 100 characters"""
		self._transfer_id = next(self.id_generator)
		self.end_of_transfer = False
		self.reading = reading
		self.opc_sync = opc_sync

		self.total_size = total_size
		self.transferred_size: int = 0
		self.context: str = (context[:100] + '..') if len(context) > 100 else context

		# Data to set after the object has been created.
		self.chunk_size: int = None
		"""Size of one chunk of data. This number does not change during the transfer."""
		self.chunk_ix: int = None
		"""0-based index of the chunk."""
		self.total_chunks: int = None
		"""Expected number of chunks."""
		self.resource_name: str = None
		"""Visa Resource Name of the instrument that generated the data."""
		self.binary: bool = None
		"""True: Binary data, False: string data"""
		self.data: AnyStr = None
		"""If the feature of transferring data over R/W event is switched ON, this field contains the whole data."""

	@classmethod
	def read_chunk(cls, opc_sync: bool, context: str) -> 'IoTransferEventArgs':
		"""Creates new IoTransferEventArgs of read string \n
		:param opc_sync: defines if the command is OPC-synchronised
		:param context: SCPI query. It is truncated to maximum of 100 characters.
		:return: IoTransferEventArgs object of a read string operation."""
		return cls(True, opc_sync, None, context)

	@classmethod
	def write_str(cls, opc_sync: bool, total_size: int, context: str) -> 'IoTransferEventArgs':
		"""Creates new IoTransferEventArgs of write string \n
		:param opc_sync: defines if the command is OPC-synchronised
		:param total_size: size of the data to write
		:param context: SCPI command write. It is truncated to maximum of 100 characters.
		:return: IoTransferEventArgs object of a write string operation."""
		obj = cls(False, opc_sync, total_size, context)
		obj.binary = False
		return obj

	@classmethod
	def write_bin(cls, context: str) -> 'IoTransferEventArgs':
		"""Creates new IoTransferEventArgs of read binary data \n
		:param context: SCPI command. It is truncated to maximum of 100 characters.
		:return: IoTransferEventArgs object of a write binary data operation."""
		# noinspection PyTypeChecker
		obj = cls(False, False, None, context.rstrip())
		obj.binary = True
		return obj

	def __str__(self):
		if self.binary:
			type_info = 'binary'
		else:
			type_info = 'ascii'
		if self.opc_sync:
			type_info += ' (opc-synced)'
		if not self.total_chunks:
			chunk_info = f' chunk nr. {self.chunk_ix + 1}'
		elif self.total_chunks > 1:
			chunk_info = f' chunk nr. {self.chunk_ix + 1}/{self.total_chunks}'
		else:
			chunk_info = ' chunk nr. 1/1'
		eot = ' (EOT)' if self.end_of_transfer else ''
		if self.reading:
			result = f'IoTransferArgs ID {self._transfer_id}: reading {type_info}, {chunk_info} {size_to_kb_mb_string(self.chunk_size, True)}, ' \
					f'sum {size_to_kb_mb_string(self.transferred_size, True)} / {size_to_kb_mb_string(self.total_size, True) if self.total_size else "<N.A.>"}{eot}.'
		else:
			result = f'IoTransferArgs ID {self._transfer_id}: writing {type_info}, {chunk_info} {size_to_kb_mb_string(self.chunk_size, True)}, ' \
						f'sum {size_to_kb_mb_string(self.transferred_size, True)} / {size_to_kb_mb_string(self.total_size, True)}{eot}.'
		if self.context:
			result += f' Cmd: {self.context}'
		return result

	@property
	def transfer_id(self) -> int:
		"""Unique number for each transfer for this Instrument.
		If the transfer is performed in more chunks, the transfer_id stays the same during the whole transfer."""
		return self._transfer_id

	def set_end_of_transfer(self):
		"""Sets fields to signal end of transfer."""
		self.transferred_size = self.total_size
		self.end_of_transfer = True
