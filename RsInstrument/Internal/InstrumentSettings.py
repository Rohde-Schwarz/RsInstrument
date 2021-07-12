"""See the docstring for the InstrumentSettings class."""

from enum import Enum
from enum import Flag

from . import InstrumentOptions as Opts
from . import Conversions as Conv
from .ScpiLogger import LoggingMode


class InstrViClearMode(Flag):
	"""Mode for executing viClear() method."""
	disabled = 0x00
	ignore_error = 0x01
	execute_on_all = 0x02
	execute_on_socket = 0x04
	execute_on_serial = 0x08
	execute_on_usb = 0x10
	execute_on_gpib = 0x20
	execute_on_tcpvxi = 0x40


class WaitForOpcMode(Enum):
	"""Mode that is used for OPC-sync commands/queries"""
	stb_poll = 1
	stb_poll_slow = 2
	stb_poll_superslow = 3
	opc_query = 4


class InstrumentSettings(object):
	"""Defines settings of the instrument session."""

	def __init__(
			self,
			viclear_exe_mode: InstrViClearMode,
			idn_model_full_name: bool,
			write_delay: int,
			read_delay: int,
			io_segment_size: int,
			opc_wait_mode: WaitForOpcMode,
			opc_timeout: int,
			visa_timeout: int,
			self_test_timeout: int,
			instr_options_parse_mode: Opts.ParseMode,
			bin_float_numbers_format: Conv.BinFloatFormat,
			bin_int_numbers_format: Conv.BinIntFormat,
			opc_query_after_write: bool,
			logging_mode: LoggingMode):

		self.viclear_exe_mode = viclear_exe_mode
		self.idn_model_full_name = idn_model_full_name
		self.write_delay = write_delay
		self.read_delay = read_delay
		self.io_segment_size = io_segment_size
		self.opc_wait_mode = opc_wait_mode
		self.opc_timeout = opc_timeout
		self.visa_timeout = visa_timeout
		self.selftest_timeout = self_test_timeout
		self.instr_options_parse_mode = instr_options_parse_mode
		self.bin_float_numbers_format = bin_float_numbers_format
		self.bin_int_numbers_format = bin_int_numbers_format
		self.opc_query_after_write = opc_query_after_write
		self.logging_mode = logging_mode
		self.logging_name = None

		self.assure_write_with_tc = False
		self.term_char = '\n'
		self.add_term_char_to_write_bin_block = False

		self.stb_in_error_check = True
		self.disable_opc_query = False
		self.visa_select = None
		self._last_settings = None

	def _get_driversetup_item(self, name: str) -> str:
		"""Looks for a token that either has the name with prefix DRIVERSETUP_ or no prefix.
		Example: Keynames DRIVERSETUP_WRITEDELAY and WRITEDELAY are equivalent.
		If both keynames are present, the one with DRIVERSETUP_ has priority."""
		name = name.upper()
		value = self._last_settings.get(f'DRIVERSETUP_{name}')
		if value is None:
			value = self._last_settings.get(name)
		return value

	def _get_item(self, name: str) -> str:
		"""Returns a token value with the keyname name (case insensitive) from the last settings dictionary.
		If the keyname does not exist, the method returns None."""
		value = self._last_settings.get(name.upper())
		return value

	def apply_option_settings(self, settings: dict) -> None:
		"""Takes options from the settings dictionary and applies them to the InstrumentSettings class properties."""
		self._last_settings = settings
		value = self._get_item('SelectVisa')
		if value:
			self.visa_select = value

		value = self._get_driversetup_item('WriteDelay')
		if value:
			self.write_delay = Conv.str_to_int(value)

		value = self._get_driversetup_item('ReadDelay')
		if value is not None:
			self.read_delay = Conv.str_to_int(value)

		value = self._get_driversetup_item('OpcWaitMode')
		if value:
			value = value.upper()
			if value == 'STBPOLLING':
				self.opc_wait_mode = WaitForOpcMode.stb_poll
			elif value == 'STBPOLLINGSLOW':
				self.opc_wait_mode = WaitForOpcMode.stb_poll_slow
			elif value == 'STBPOLLINGSUPERSLOW':
				self.opc_wait_mode = WaitForOpcMode.stb_poll_superslow
			elif value == 'OPCQUERY':
				self.opc_wait_mode = WaitForOpcMode.opc_query
			else:
				raise ValueError(
					f"Unknown value in InitWithOptions string DriverSetup key 'WaitForOPC'. Value '{value}' is not recognized. "
					"Valid values: 'StbPolling', 'StbPollingSlow', 'StbPollingSuperSlow', 'OpcQuery'")

		value = self._get_driversetup_item('AddTermCharToWriteBinBlock')
		if value:
			self.add_term_char_to_write_bin_block = Conv.str_to_bool(value)

		# Obsolete, use the AssureWriteWithTermChar
		value = self._get_driversetup_item('AssureWriteWithLf')
		if not value:
			value = self._get_driversetup_item('AssureWriteWithTermChar')
		if value:
			self.assure_write_with_tc = Conv.str_to_bool(value)

		# Obsolete, use the DataChunkSize
		value = self._get_driversetup_item('IoSegmentSize')
		if not value:
			value = self._get_driversetup_item('DataChunkSize')
		if value:
			self.io_segment_size = Conv.str_to_int(value)

		value = self._get_driversetup_item('TerminationCharacter')
		if value:
			self.term_char = value

		value = self._get_driversetup_item('OpcTimeout')
		if value:
			self.opc_timeout = Conv.str_to_int(value)

		value = self._get_driversetup_item('VisaTimeout')
		if value:
			self.visa_timeout = Conv.str_to_int(value)

		value = self._get_driversetup_item('ViClearExeMode')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, InstrViClearMode, case_sensitive=False, ignore_underscores=True)
			if enum_value is None:
				try:
					enum_value = InstrViClearMode(Conv.str_to_int(value))
				except ValueError:
					raise ValueError(
						f"Unknown value in InitWithOptions string DriverSetup key 'ViClearExeMode'. Value '{value}' is not recognized. "
						f"Valid values: ExecuteOnAll, Disabled, IgnoreError or integer bit-wise value.")
			self.viclear_exe_mode = enum_value

		value = self._get_driversetup_item('OpcQueryAfterWrite')
		if value:
			self.opc_query_after_write = Conv.str_to_bool(value)

		value = self._get_driversetup_item('StbInErrorCheck')
		if value:
			self.stb_in_error_check = Conv.str_to_bool(value)

		value = self._get_driversetup_item('DisableOpcQuery')
		if value:
			self.disable_opc_query = Conv.str_to_bool(value)

		value = self._get_driversetup_item('LoggingMode')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, LoggingMode, case_sensitive=False)
			if not enum_value:
				raise ValueError(
					f"Unknown value in InitWithOptions string DriverSetup key 'LoggingMode'. Value '{value}' is not recognized. "
					f"Valid values: {', '.join([x.name for x in LoggingMode])}")
			self.logging_mode = enum_value

		value = self._get_driversetup_item('LoggingName')
		if value:
			self.logging_name = value

		value = self._get_driversetup_item('QueryOpt')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, Opts.ParseMode, case_sensitive=False)
			if not enum_value:
				raise ValueError(
					f"Unknown value in InitWithOptions string DriverSetup key 'QueryOpt'. Value '{value}' is not recognized. "
					f"Valid values: {', '.join([x.name for x in Opts.ParseMode])}")
			self.instr_options_parse_mode = enum_value
