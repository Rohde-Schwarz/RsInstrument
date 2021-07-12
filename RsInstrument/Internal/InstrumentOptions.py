"""See the class docstring."""

import re
from enum import Enum

from .Utilities import trim_str_response


class ParseMode(Enum):
	"""Options parse mode enum."""
	Skip = 0
	KeepOriginal = 1
	KeepBeforeDash = 2
	KeepAfterDash = 3
	Auto = 4


class Options(object):
	"""Class for handling the instrument options - parsing from the *OPT? string and providing method get_all()"""
	_optionsList = []

	def __init__(self, options_str: str, mode=ParseMode.Auto):
		"""Initializes the options with the *OPT? return string."""
		self._initialize_from_string(options_str, mode)

	def __str__(self):
		return ','.join(self._optionsList)

	def _initialize_from_string(self, options_str: str, mode: ParseMode):
		"""Fills the self._optionsList from the entered 'options_str'."""
		if mode == ParseMode.Skip:
			return

		parse_patt = r'(.?)(K|B)(\d+)(.*)$'
		options = trim_str_response(options_str).split(',')
		new_opts = []
		for x in options:
			has_dash = '-' in x
			if has_dash:
				dash_ix = x.index('-')
				before = x[0:dash_ix + 1].strip('-')
				after = x[dash_ix:].strip('-')

				if mode is ParseMode.KeepBeforeDash:
					x = before

				elif mode is ParseMode.KeepAfterDash:
					x = after

				elif mode is ParseMode.Auto:
					found_before = re.match(parse_patt, before)
					found_after = re.match(parse_patt, after)
					if found_before is not None and found_after is not None:
						x = after if len(found_after.group(0)) >= len(found_before.group(0)) else before
					elif found_before is not None:
						x = before
					elif found_after is not None:
						x = after

			if len(x) > 0:
				new_opts.append(x)

		# Remove duplicates
		new_opts = set(new_opts)

		# Create a weighting number
		result = []
		for x in new_opts:
			sort_value = x
			m = re.match(parse_patt, x)
			if m:
				kb_weight = '02' if m.group(2) == 'B' else '01'
				sort_value = '{0}{1}{2:09d}{3}'.format(m.group(1), kb_weight, int(m.group(3)), m.group(4))

			result.append('{0} -> {1}'.format(sort_value, x))

		# Sort keys in that dictionary and then reconstruct the original options
		result.sort()
		self._optionsList = [x.split(' -> ')[1] for x in result]

	def get_all(self):
		"""Returns all the options."""
		return self._optionsList
