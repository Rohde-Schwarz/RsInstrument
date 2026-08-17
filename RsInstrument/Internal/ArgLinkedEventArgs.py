"""Class defining Linked argument Event."""


class ArgLinkedEventArgs(object):
	"""Contains event data for suppressed argument."""

	def __init__(self, link_name: str, arg_name: str, value: object | None = None, context: str = '', timestamp: float | None = None):
		self.link_name = link_name
		self.arg_name = arg_name
		self.value = value
		self.context = context
		self.timestamp = timestamp

	def __str__(self):
		result = f"ArgLinkedEventArgs '{self.link_name}'"
		if self.arg_name:
			result += f"argument name '{self.arg_name}'"
		# noinspection PyStringConversionWithoutDunderMethod
		result += f"value: {self.value}"
		return result
