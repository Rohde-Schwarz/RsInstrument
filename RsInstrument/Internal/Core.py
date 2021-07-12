"""See the class docstring."""

import re
from typing import Callable

from . import InstrumentOptions as Options, Conversions as Conv
from .ArgSingle import ArgSingle
from .ArgSingleList import ArgSingleList
from .Conversions import BinFloatFormat, BinIntFormat
from .Instrument import Instrument
from .InstrumentSettings import InstrViClearMode, InstrumentSettings, WaitForOpcMode
from .Utilities import parse_token_to_key_and_value, trim_str_response
from .ScpiLogger import LoggingMode
from .InstrumentErrors import RsInstrException


class Core(object):
	"""Main driver component. Provides: \n
		- Main core constructor
		- 'io' interface for all the write / query operations
		- Command parameters string composer for single arguments...
		- Link handlers adding / changing / deleting

		Version history:

		1.14.0 (build 53) 12.07.2021
			- Scpi logger time entries now support not only datetime tuples, but also float timestamps
			- changed handling of the syst:err? responses - now they are always Tuple (code, message)
			- StatusException has new field errors_list: List[ Tuple[code, message] ]
			- Added logger.log_status_check_ok property. This allows for skipping lines with 'Status check: OK'


		1.12.0 (build 50) 26.06.2021
			- Added SCPI Logger
			- Simplified constructor's options string format - removed DriverSetup=() syntax:
			Instead of "DriverSetup=(TerminationCharacter='\n')", you use "TerminationCharacter='\n'"
			The original format is still supported.

			- Fixed calling SYST:ERR? even if *STB? returned 0
			- Replaced @ni backend with @ivi for resource manager - this is necessary for the future pyvisa version 1.12+

		1.11.0 (build 49) 09.06.2021
			- Added is_connection_active() + reconnect()

		1.10.1 (build 47) 01.06.2021
			- Fixed bug with error checking when events are defined

		1.10.0 (build 46) 03.05.2021
			- Added methods to Instrument: query_struct_with_opc(), query_str_suppressed_with_opc()

		1.9.0 (build 45) 13.04.2021
			- Added option to set callbacks before_write and before_query
			- When a RepCap has a member with integer number 0 defined, the command string interpretation of such member is '0', not empty string

		1.8.0 (build 43) 19.01.2021
			- Added matching of Enum instrument responses also in short/long form

		1.7.7 (build 42) 26.11.2020
			- Extended ArgSingleList.compose_cmd_string() to 9 arguments

		1.7.6 (build 41) 23.11.2020
			- Extended data types for IntegerExt, FloatExt, IntegerExtArray, FloatExtArray

		1.7.5 (build 40) 12.11.2020
			- Extended Conversions method str_to_str_list() by parameter 'clear_one_empty_item' with default value False

		1.7.4 (build 39) 11.09.2020
			- Fixed parsing of the instrument errors when an error message contains two double quotes

		1.7.3 (build 38) 21.10.2020
			- Added 'UND' to the list of float numbers that are represented as NaN

		1.7.2 (build 37) 10.10.2020
			- SCPI response string conversion to scalar enum: if the string contains ',', the content after it inclusive the comma is ignored

		1.7.1 (build 36) 08.10.2020
			- Fixed Python 3.8.5+ warnings

		1.7.0 (build 34) 30.09.2020
			- Added option to set the termination characters for reading and writing. Until now, it was fixed to '\n' (Linefeed)
			- Replaced 'import visa' with 'import pyvisa' to remove Python 3.8 pyvisa warnings

		Version History:
		1.6.0 (build 33) 17.09.2020
			- Added special characters encoding/decoding in enums

		1.4.0 (build 32) 17.09.2020
			- Added recognition of RsVisa library location for linux when using options string 'SelectVisa=rs'
			- Fixed bug in reading binary data 16 bit

		1.3.0 (build 31) 04.09.2020
			- added DRIVERSETUP_QUERYOPT to the driver's option string
			- *OPT? is no longer performed at the init, but only at the first access to options string.
				In addition, the *OPT? query is executed with 1000 ms timeout, and the errors are suppressed

		1.2.0 (build 30), 03.08.2020
			- Fixed NRP-Z session parameters: vxi_capable = False, io_segment_size = 1000000

		1.1.0 (build 29), 20.06.2020
			- Added RepeatedCapability and base class CommandsGroup
			- Fixed simulation mode switching

		0.9.3 (build 25), 23.04.2020 - Fixed composition of optional arguments in ArgSingleList and ArgSingle
		0.9.2 (build 24), 13.11.2019 - Added recognition of special values for enum return strings
		0.9.1 - Added read / write to file, refactored internals to work with streams
		0.9.0 - First Version created."""

	driver_version: str = ''
	"""Placeholder for the driver version string."""

	def __init__(
			self,
			resource_name: str,
			id_query: bool = True,
			reset: bool = False,
			driver_options: str = None,
			user_options: str = None,
			direct_session: object = None):
		"""Initializes new driver session. For cleaner code, use the class methods: \n
		- Core.from_existing_session() - initializes a new Core with an existing pyvisa session."""

		self.core_version = '1.14.0'
		self.simulating = False
		self.supported_idn_patterns = []
		self.supported_instr_models = []
		self.resource_name = resource_name

		self._args_single_list = ArgSingleList()
		self.sett_dr = self._parse_init_settings_string(driver_options)
		self._apply_settings_to_core(self.sett_dr)
		self.sett_user = self._parse_init_settings_string(user_options)
		self._apply_settings_to_core(self.sett_user)

		# Typical settings for the Core
		self._instrumentSettings = InstrumentSettings(
			InstrViClearMode.execute_on_all,  # Instrument viClear mode
			False,  # Full model name. True: SMW200A, False: SMW
			0,  # Delay by each write
			0,  # Delay by each read
			100000,  # Max chunk read / write size in bytes
			WaitForOpcMode.stb_poll,  # Waiting for OPC Mode: Status byte polling
			30000,  # OPC timeout
			10000,  # VISA timeout
			60000,  # Self-test timeout
			Options.ParseMode.Auto,  # *OPT? response parsing mode
			BinFloatFormat.Single_4bytes,  # Format for parsing of binary float numbers
			BinIntFormat.Integer32_4bytes,  # Format for parsing of binary integer numbers
			False,  # OPC query after each setting
			LoggingMode.Off  # Logging mode
		)

		self._instrumentSettings.apply_option_settings(self.sett_dr)
		self._instrumentSettings.apply_option_settings(self.sett_user)

		handle = self._resolve_direct_session(direct_session)
		self.io = Instrument(self.resource_name, self.simulating, self._instrumentSettings, handle)
		self.io.query_instr_status = True
		# Update the resource name if it changed, for example because of the direct session
		self.resource_name = self.io.resource_name
		self.allow_reconnect = self.io.allow_reconnect

		self._apply_settings_to_instrument(self.sett_dr)
		self._apply_settings_to_instrument(self.sett_user)

		self.io.set_simulating_cmds()

		if id_query:
			self.io.fits_idn_pattern(self.supported_idn_patterns, self.supported_instr_models)

		if reset:
			self.io.reset()
		else:
			self.io.check_status()

	@classmethod
	def from_existing_session(cls, session: object, driver_options: str = None) -> 'Core':
		"""Creates a new Core object with the entered 'session' reused."""
		# noinspection PyTypeChecker
		return cls(resource_name=None, id_query=False, reset=False, driver_options=driver_options, user_options=None, direct_session=session)

	def __str__(self):
		return f"Core session '{self.io.resource_name}'"

	def _resolve_direct_session(self, direct_session):
		# Resolve the direct_session to handle. Options for direct_session type:
		# - VisaSession object, retrieved from the driver's RsInstrument.get_session_handle() method
		# - string in case of a simulation session
		handle = direct_session
		if not direct_session:
			return None
		# Check if the entered 'direct_session' is either the driver object or the Visa session
		if hasattr(direct_session, 'get_session_handle'):
			if not hasattr(direct_session, '_core'):
				raise RsInstrException('Direct session is a class type. It must be an instance of the top-level driver class.')
			handle = direct_session.get_session_handle()
		# If the handle is a simulating session, change the session to simulating and set disable the 'from existing session' feature
		if isinstance(handle, str):
			mand_string = 'Simulating session, resource name '
			if mand_string in handle:
				self.resource_name = handle[len(mand_string):].strip().strip("'").strip()
				self.simulating = True
				handle = None
		return handle

	def set_link_handler(self, link_name: str, handler: Callable) -> Callable:
		"""Adds / Updates link handler for the entered link_name.
		Handler API: handler(event_args: ArgLinkedEventArgs)
		Returns the previous registered handler, or None if no handler was registered before."""
		return self.io.set_link_handler(link_name, handler)

	def del_link_handler(self, link_name: str) -> Callable:
		"""Deletes link handler for the link_name.
		Returns the deleted handler, or None if none existed."""
		return self.io.del_link_handler(link_name)

	def del_all_link_handlers(self) -> int:
		"""Deletes all the link handlers.
		Returns number of deleted links."""
		return self.io.del_all_link_handlers()

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
			m = re.search(literal_pattern, text)
			if not m:
				break
			lit_part = '"' + m.group(1).replace(',', '<COMMA_ESC>') + '"'
			text = text.replace(m.group(0), lit_part)

		# Remove all the class-options enclosed by round brackets e.g. "<groupName>=(<groupTokens>)"
		group_pattern = r'(\w+)\s*=\s*\(([^\)]*)\)'
		# Match class-settings, add them as separate keys with groupName_Key
		while True:
			# Group loop
			m = re.search(group_pattern, text)
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

	def _apply_settings_to_core(self, settings: dict) -> None:
		"""Applies settings relevant for the Core from the dictionary."""
		value = settings.get('SIMULATE')
		if value:
			self.simulating = Conv.str_to_bool(value)

		value = settings.get('SUPPORTEDINSTRMODELS')
		if value:
			self.supported_instr_models = [*map(trim_str_response, value.split('/'))]

		value = settings.get('SUPPORTEDIDNPATTERNS')
		if value:
			self.supported_idn_patterns = [*map(trim_str_response, value.split('/'))]

	def _apply_settings_to_instrument(self, settings: dict) -> None:
		"""Applies settings relevant for the Instrument from the dictionary."""
		value = settings.get('QUERYINSTRUMENTSTATUS')
		if value:
			self.io.query_instr_status = Conv.str_to_bool(value)

		value = settings.get('SIMULATIONIDNSTRING')
		if value and self.simulating:
			# Use the '*' instead of the ',' in the value to avoid comma as token delimiter
			self.io.idn_string = value.replace('*', ',')

	def compose_cmd_arg_param(
			self, arg1: ArgSingle, arg2: ArgSingle = None, arg3: ArgSingle = None, arg4: ArgSingle = None, arg5: ArgSingle = None, arg6: ArgSingle = None) -> str:
		"""Composes command parameter string based on the single arguments definition."""
		return self._args_single_list.compose_cmd_string(arg1, arg2, arg3, arg4, arg5, arg6)

	def get_last_sent_cmd(self) -> str:
		"""Returns the last commands sent to the instrument. Only works in simulation mode"""
		return self.io.get_last_sent_cmd()

	def get_session_handle(self):
		"""Returns the underlying pyvisa session."""
		return self.io.get_session_handle()

	def close(self):
		"""Closes the Core session."""
		self.io.close()
		self.io = None
