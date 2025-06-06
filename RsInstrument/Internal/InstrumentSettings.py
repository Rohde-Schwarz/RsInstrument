"""See the docstring for the InstrumentSettings class."""

from enum import Enum
from enum import Flag
from re import search
from typing import List

from . import InstrumentOptions as Opts
from . import Conversions as Conv
from .ScpiLogger import LoggingMode
from .Utilities import parse_token_to_key_and_value, trim_str_response


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


class OpcSyncQueryMechanism(Enum):
	"""Mechanism to use when querying with OPC."""
	standard = 0  # Sends the command with ;*OPC at the end, and waits for the ESB or ERRQ bits.
	also_check_mav = 1  # Same as Standard, but for queries additionally ends the OPC-waiting queue on MAV bit set to 1.
	cls_only_check_mav_err_queue = 2  # ClearBeforeRead, does not send the ';*OPC' as the command suffix. In the wait loop, checks the MAV and ERRQ.
	only_check_mav_err_queue = 3  # Same as above, but skips the ClearBeforeRead()


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
			logging_mode: LoggingMode,
			opc_query_sync_mechanism: OpcSyncQueryMechanism):

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
		self.opc_query_sync_mechanism = opc_query_sync_mechanism

		self.logging_mode = logging_mode
		self.logging_name = None
		self.logging_format = None
		self.log_to_global_target = False
		self.log_to_console = False
		self.log_to_udp = False
		self.log_udp_port = 49200
		self.log_relative_time_of_first_entry = False

		self.assure_write_with_tc = False
		self.term_char = '\n'
		self.encoding = 'charmap'
		self.add_term_char_to_write_bin_block = False
		self.open_timeout = 0
		self.exclusive_lock = False
		self.vxi_capable = True
		self.scpi_quotes: str or None = None

		self.cmd_idn = '*IDN?'
		self.first_cmds = ''
		self.idn_custom_parse = ''
		self.each_cmd_prefix = ''
		self.each_cmd_suffix = ''
		self.strip_str_trailing_ws = False
		self.cmd_reset = '*RST'
		self.skip_status_system_setting = False
		self.skip_clear_status = False
		self.stb_in_error_check = True
		self.each_cmd_as_query = False
		self.instr_status_check = False
		self.disable_opc_query = False

		self.visa_select = None
		self._last_settings = None

		# Instrument object settings
		self.instrument_status_check = None
		self.instrument_simulation_idn_string = None

		# Core object settings
		self.simulating = False
		self.supported_instr_models: List[str] = []
		self.supported_idn_patterns: List[str] = []

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
		"""Returns a token value with the keyname name (case-insensitive) from the last settings dictionary.
		If the keyname does not exist, the method returns None."""
		value = self._last_settings.get(name.upper())
		return value

	# noinspection PyMethodMayBeStatic
	def _parse_init_settings_string(self, text: str) -> dict:
		"""Parses init string to a dictionary of settings: name -> value."""
		tokens = {}
		if not text:
			return tokens

		# Text enclosed in single brackets '' must have the commas escaped
		literal_pattern = r"'([^']+)'"
		while True:
			# literal loop
			m = search(literal_pattern, text)
			if not m:
				break
			lit_part = '"' + m.group(1).replace(',', '<COMMA_ESC>') + '"'
			text = text.replace(m.group(0), lit_part)

		# Remove all the class-options enclosed by round brackets e.g. "<groupName>=(<groupTokens>)"
		group_pattern = r'(\w+)\s*=\s*\(([^\)]*)\)'
		# Match class-settings, add them as separate keys with groupName_Key
		while True:
			# Group loop
			m = search(group_pattern, text)
			if not m:
				break
			text = text.replace(m.group(0), '')
			group_name = m.group(1).upper()
			group_tokens = m.group(2).strip().split(',')
			for token in group_tokens:
				key, value = parse_token_to_key_and_value(token)
				if value:
					tokens[f'{group_name}_{key.upper()}'] = value

		# All groups are removed from the text, now we can use splitting on commas and remove white-space-only elements
		for token in text.split(','):
			key, value = parse_token_to_key_and_value(token.replace('<COMMA_ESC>', ','))
			if value:
				tokens[key.upper()] = value
		return tokens

	# noinspection PyMethodMayBeStatic
	def _resolve_escape_chars(self, value: str) -> str:
		"""Resolves complicated escape characters. Used for termination character or command prefix/suffix."""
		val_lc = value.lower()
		if value == '\\r' or val_lc == 'cr':
			return '\r'
		elif value == '\\n' or val_lc == 'lf':
			return '\n'
		elif value == '\\t' or val_lc == 'tab':
			return '\t'
		elif value == '\\0' or val_lc == 'null':
			return '\0'
		elif val_lc.startswith("0x") and len(val_lc) >= 4:
			return chr(int(value[2:], 16))

		return value

	def apply_option_settings(self, text: str or None) -> None:
		"""Takes options from the settings dictionary and applies them to the InstrumentSettings class properties."""
		if not text:
			return
		if len(text) == 0:
			return
		self._last_settings = self._parse_init_settings_string(text)

		value = self._get_item('SelectVisa')
		if value:
			self.visa_select = value

		value = self._get_driversetup_item('WriteDelay')
		if value:
			self.write_delay = Conv.str_to_int(value)

		value = self._get_driversetup_item('ReadDelay')
		if value is not None:
			self.read_delay = Conv.str_to_int(value)

		# OpcWaitMode
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

		value = self._get_driversetup_item('OpenTimeout')
		if value:
			self.open_timeout = Conv.str_to_int(value)

		value = self._get_driversetup_item('ExclusiveLock')
		if value:
			self.exclusive_lock = Conv.str_to_bool(value)

		value = self._get_driversetup_item('VxiCapable')
		if value:
			self.vxi_capable = Conv.str_to_bool(value)

		# ScpiQuotes
		value = self._get_driversetup_item('ScpiQuotes')
		if value:
			if value.lower() == 'single':
				self.scpi_quotes = "'"
			elif value.lower() == 'double':
				self.scpi_quotes = '"'
			else:
				self.scpi_quotes = value

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

		# TerminationCharacter
		value = self._get_driversetup_item('TerminationCharacter')
		if value:
			self.term_char = self._resolve_escape_chars(value)

		value = self._get_driversetup_item('Encoding')
		if value:
			self.encoding = value

		value = self._get_driversetup_item('OpcTimeout')
		if value:
			self.opc_timeout = Conv.str_to_int(value)

		value = self._get_driversetup_item('VisaTimeout')
		if value:
			self.visa_timeout = Conv.str_to_int(value)

		# ViClearExeMode
		value = self._get_driversetup_item('ViClearExeMode')
		if value:
			if value.lower() == 'disabled':
				enum_value = InstrViClearMode.disabled  # Have to do it this way because the Flag enumeration does not include 0-value elements
			else:
				enum_value = Conv.str_to_simple_scalar_enum(value, InstrViClearMode, case_sensitive=False, ignore_underscores=True)
			if enum_value is None:
				try:
					enum_value = InstrViClearMode(Conv.str_to_int(value))
				except ValueError:
					raise ValueError(
						f"Unknown value in InitWithOptions string DriverSetup key 'ViClearExeMode'. Value '{value}' is not recognized. "
						f"Valid values: ExecuteOnAll, Disabled, IgnoreError or integer bit-wise value.")
			self.viclear_exe_mode = enum_value

		# OpcSyncQueryMechanism
		value = self._get_driversetup_item('OpcSyncQueryMechanism')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, OpcSyncQueryMechanism, case_sensitive=False, ignore_underscores=True)
			if enum_value is None:
				try:
					enum_value = OpcSyncQueryMechanism(Conv.str_to_int(value))
				except ValueError:
					raise ValueError(
						f"Unknown value in InitWithOptions string DriverSetup key 'OpcSyncQueryMechanism'. Value '{value}' is not recognized. "
						f"Valid values: Standard, AlsoCheckMav, ClsOnlyCheckMavErrQueue, OnlyCheckMavErrQueue.")
			self.opc_query_sync_mechanism = enum_value

		value = self._get_driversetup_item('OpcQueryAfterWrite')
		if value:
			self.opc_query_after_write = Conv.str_to_bool(value)

		value = self._get_driversetup_item('StbInErrorCheck')
		if value:
			self.stb_in_error_check = Conv.str_to_bool(value)

		value = self._get_driversetup_item('EachCmdAsQuery')
		if value:
			self.each_cmd_as_query = Conv.str_to_bool(value)

		value = self._get_driversetup_item('DisableOpcQuery')
		if value:
			self.disable_opc_query = Conv.str_to_bool(value)

		# LoggingMode
		value = self._get_driversetup_item('LoggingMode')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, LoggingMode, case_sensitive=False)
			if not enum_value:
				raise ValueError(
					f"Unknown value in InitWithOptions string 'options', key 'LoggingMode'. Value '{value}' is not recognized. "
					f"Valid values: {', '.join([x.name for x in LoggingMode])}")
			self.logging_mode = enum_value

		# Logging
		value = self._get_driversetup_item('LoggingName')
		if value:
			self.logging_name = value

		value = self._get_driversetup_item('LoggingFormat')
		if value:
			self.logging_format = value

		value = self._get_driversetup_item('LogToGlobalTarget')
		if value:
			self.log_to_global_target = Conv.str_to_bool(value)

		value = self._get_driversetup_item('LoggingToConsole')
		if value:
			self.log_to_console = Conv.str_to_bool(value)

		value = self._get_driversetup_item('LoggingToUdp')
		if value:
			self.log_to_udp = Conv.str_to_bool(value)

		value = self._get_driversetup_item('LoggingUdpPort')
		if value:
			self.log_udp_port = Conv.str_to_int(value)

		value = self._get_driversetup_item('LoggingRelativeTimeOfFirstEntry')
		if value:
			self.log_relative_time_of_first_entry = Conv.str_to_bool(value)

		# Others
		value = self._get_driversetup_item('CmdIdn')
		if value:
			self.cmd_idn = '' if value.lower() == '<none>' else value

		value = self._get_driversetup_item('CmdReset')
		if value:
			self.cmd_reset = value

		value = self._get_driversetup_item('SkipStatusSystemSettings')
		if value:
			self.skip_status_system_setting = Conv.str_to_bool(value)

		value = self._get_driversetup_item('SkipClearStatus')
		if value:
			self.skip_clear_status = Conv.str_to_bool(value)

		# QueryOpt
		value = self._get_driversetup_item('QueryOpt')
		if value:
			enum_value = Conv.str_to_simple_scalar_enum(value, Opts.ParseMode, case_sensitive=False)
			if not enum_value:
				raise ValueError(
					f"Unknown value in InitWithOptions string 'options', key 'QueryOpt'. Value '{value}' is not recognized. "
					f"Valid values: {', '.join([x.name for x in Opts.ParseMode])}")
			self.instr_options_parse_mode = enum_value

		# Instrument object settings
		value = self._get_driversetup_item('QueryInstrumentStatus')
		if value:
			self.instrument_status_check = Conv.str_to_bool(value)

		value = self._get_driversetup_item('SimulationIdnString')
		if value:
			# Use the '*' instead of the ',' in the value to avoid comma as token delimiter
			self.instrument_simulation_idn_string = value.replace('*', ',')

		# Core object settings
		value = self._get_driversetup_item('Simulate')
		if value:
			self.simulating = Conv.str_to_bool(value)

		value = self._get_driversetup_item('SupportedInstrModels')
		if value:
			self.supported_instr_models = [*map(trim_str_response, value.split('/'))]

		value = self._get_driversetup_item('SupportedIdnPatterns')
		if value:
			self.supported_idn_patterns = [*map(trim_str_response, value.split('/'))]

		value = self._get_driversetup_item('StripStringTrailingWhitespaces')
		if value:
			self.strip_str_trailing_ws = Conv.str_to_bool(value)

		# Profiles
		value = self._get_driversetup_item('Profile')
		if value:
			val_low = value.lower()

			if val_low == 'hm8123':
				self.term_char = '\r'
				self.assure_write_with_tc = True
				self.cmd_idn = 'IDN'
				self.cmd_reset = 'RST'
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.stb_in_error_check = False

			elif val_low == 'cmq':
				self.term_char = '\r'
				self.assure_write_with_tc = True
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.stb_in_error_check = False
				self.each_cmd_as_query = True

			elif val_low == 'minimal':
				self.assure_write_with_tc = True
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.stb_in_error_check = False

			elif val_low == 'ats':
				self.term_char = '\0'
				self.assure_write_with_tc = True
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.stb_in_error_check = False
				self.each_cmd_as_query = True

			elif val_low == 'xk41':
				self.assure_write_with_tc = True
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.stb_in_error_check = False
				self.each_cmd_prefix = '\n'
				self.first_cmds = '<q>M:REMOTE SENTER1'
				self.cmd_idn = 'M:GR GVER'
				self.idn_custom_parse = 'gVER"([^"]+)"->Rohde&Schwarz,M3SR,100000,\\1'
				self.term_char = '\r'
				self.each_cmd_as_query = True

			elif val_low == 'radest':
				self.assure_write_with_tc = True
				self.skip_status_system_setting = True
				self.skip_clear_status = True
				self.disable_opc_query = True
				self.instrument_status_check = False
				self.each_cmd_suffix = '\r'
				self.each_cmd_as_query = True
				self.strip_str_trailing_ws = True
				self.term_char = '\n'

			else:
				raise ValueError(f"Unknown value in InitWithOptions string 'options', key 'Profile', value '{value}'. Valid values (case-insensitive): HM8123, CMQ, Minimal, XK41, ATS")

		# Following values can still be overwritten on top of the profiles
		value = self._get_driversetup_item('FirstCmds')
		if value:
			self.first_cmds = value

		value = self._get_driversetup_item('IdnCustomParse')
		if value:
			self.idn_custom_parse = value

		value = self._get_driversetup_item('EachCmdPrefix')
		if value:
			self.each_cmd_prefix = self._resolve_escape_chars(value)

		value = self._get_driversetup_item('EachCmdSuffix')
		if value:
			self.each_cmd_suffix = self._resolve_escape_chars(value)
