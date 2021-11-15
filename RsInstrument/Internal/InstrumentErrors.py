"""Definition of RsInstrument exceptions, assert functions, and other error-related functions."""

from typing import List, Tuple


class RsInstrException(Exception):
	"""Exception base class for all the RsInstrument exceptions."""
	def __init__(self, message: str):
		super(RsInstrException, self).__init__(message)
		self.message = message


class TimeoutException(RsInstrException):
	"""Exception for timeout errors."""
	def __init__(self, message: str):
		super(TimeoutException, self).__init__(message)


class StatusException(RsInstrException):
	"""Exception for instrument status errors.
	Tje field  errors_list contains the complete list of all the errors with messages and codes."""
	def __init__(self, rsrc_name: str, message: str, errors_list: List[Tuple[int, str]], first_exc: Exception = None):
		self.rsrc_name: str = rsrc_name
		self.first_exc: Exception = first_exc
		self.errors_list: List[Tuple[int, str]] = errors_list
		super(StatusException, self).__init__(message)


class UnexpectedResponseException(RsInstrException):
	"""Exception for instrument unexpected responses."""
	def __init__(self, rsrc_name: str, message: str):
		self.rsrc_name: str = rsrc_name
		super(UnexpectedResponseException, self).__init__(message)


class ResourceError(RsInstrException):
	"""Exception for resource name - e.g. resource not found."""
	def __init__(self, rsrc_name: str, message: str):
		self.rsrc_name: str = rsrc_name
		super(ResourceError, self).__init__(message)


class DriverValueError(RsInstrException):
	"""Exception for different driver value settings e.g. RepCap values or Enum values."""
	def __init__(self, rsrc_name: str, message: str):
		self.rsrc_name: str = rsrc_name
		super(DriverValueError, self).__init__(message)


def get_instrument_status_errors(rsrc_name: str, errors: List[Tuple[int, str]], context: str = '') -> str or None:
	"""Checks the errors list and of it contains at least one element, it returns the error message.
	Otherwise returns None."""
	if errors is None or len(errors) == 0:
		return
	if context:
		message = f"'{rsrc_name}': {context} "
	else:
		message = f"'{rsrc_name}': "
	errors_msg = '\n'.join([f'{x[0]},"{x[1]}"' for x in errors])
	if len(errors) == 1:
		message += f'Instrument error detected: {errors_msg}'
		return message
	if len(errors) > 1:
		message += f'{len(errors)} Instrument errors detected:\n{errors_msg}'
		return message


def assert_no_instrument_status_errors(rsrc_name: str, errors: List[Tuple[int, str]], context: str = '', first_exc=None) -> None:
	"""Checks the errors list and of it contains at least one element, it throws StatusException."""
	msg = get_instrument_status_errors(rsrc_name, errors, context)
	if msg:
		raise StatusException(rsrc_name, msg, errors, first_exc=first_exc)


def throw_opc_tout_exception(opc_tout: int, used_tout: int, context: str = '') -> None:
	"""Throws TimeoutException - use it for any timeout error."""
	if not context:
		message = ''
	else:
		message = f'{context} '
	if used_tout < 0 or used_tout == opc_tout:
		message = message + f"Timeout expired before the operation completed. Current OPC timeout is set to {opc_tout} milliseconds. " \
							"Change it with the property '_driver.UtilityFunctions.opc_timeout'. " \
							"Optionally, if the method API contains an optional timeout parameter, set it there."
	else:
		message = message + f"Timeout expired before the operation completed. Used timeout: {used_tout} ms"
	raise TimeoutException(message)


def throw_bin_block_unexp_resp_exception(rsrc_name: str, received_data: str) -> None:
	"""Throws InvalidDataException - use it in case an instrument response is not a binary block."""
	if received_data.endswith('\n'):
		raise UnexpectedResponseException(
			rsrc_name, "Expected binary data header starting with #(hash), received data '{}'".format(received_data.replace('\n', '\\n')))
	else:
		raise UnexpectedResponseException(
			rsrc_name, f"Expected binary data header starting with #(hash), received data starting with '{received_data}'...")


def assert_query_has_qmark(query: str, context: str = '') -> None:
	"""Throws Exception if the query does not contain any question marks."""
	if '?' in query:
		return
	message = ''
	if context:
		message = context.strip() + ': '
	message = message + "Query commands must contain question-marks. Sent query: '{0}'".format(query.strip('\n'))
	raise RsInstrException(message)


def assert_cmd_has_no_qmark(command: str, context: str = '') -> None:
	"""Throws Exception if the query contains a question marks."""
	if '?' not in command:
		return
	message = ''
	if context:
		message = context.strip() + ': '
	message = message + "Set commands must not contain question-marks. Sent command: '{0}'".format(command.strip('\n'))
	raise RsInstrException(message)
