"""See the class docstring."""

import re
from enum import Enum
from typing import List

from .Utilities import trim_str_response


class ParseMode(Enum):
	"""Options parse mode enum."""
	Skip = 0
	KeepOriginal = 1
	KeepBeforeDash = 2
	KeepAfterDash = 3
	Auto = 4


class Options(object):
	"""Class for handling the instrument options - parsing from the *OPT? string and providing methods:
	- get_all()
	- contains()
	- contains_regex()
	- has_k0()"""
	_optionsList = []
	_optionsListUc = []
	_has_k0: bool = False
	_parse_patt = r'(.?)(K|B)(\d+)(.*)$'

	def __init__(self, options_str: str, mode=ParseMode.Auto):
		"""Initializes the options with the *OPT? return string."""
		self._initialize_from_string(options_str, mode)

	def __str__(self):
		return ','.join(self._optionsList)

	def _initialize_from_string(self, options_str: str, mode: ParseMode):
		"""Fills the self._optionsList from the entered 'options_str'."""
		if mode == ParseMode.Skip:
			return

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
					found_before = re.match(self._parse_patt, before)
					found_after = re.match(self._parse_patt, after)
					if found_before is not None and found_after is not None:
						x = after if len(found_after.group(0)) >= len(found_before.group(0)) else before
					elif found_before is not None:
						x = before
					elif found_after is not None:
						x = after

			if len(x) > 0:
				new_opts.append(x)

		self._regenerate(new_opts)

	def _regenerate(self, options: List[str]):
		"""Regenerates the options again from the entered ones."""
		# Remove duplicates
		options = set(options)
		# Create a weighting number
		result = []
		for x in options:
			sort_value = x
			m = re.match(self._parse_patt, x)
			if m:
				kb_weight = '02' if m.group(2) == 'B' else '01'
				sort_value = '{0}{1}{2:09d}{3}'.format(m.group(1), kb_weight, int(m.group(3)), m.group(4))

			result.append('{0} -> {1}'.format(sort_value, x))

		# Sort keys in that dictionary and then reconstruct the original options
		result.sort()
		self._optionsList = [x.split(' -> ')[1] for x in result]
		self._optionsListUc = [x.upper() for x in self._optionsList]
		self._has_k0 = 'K0' in self._optionsListUc

	def add(self, option: str) -> None:
		"""Adds new option if not already existing."""
		self._optionsList.append(option)
		self._regenerate(self._optionsList)

	def remove(self, option: str) -> None:
		"""Removes the option if exists."""
		try:
			self._optionsList.remove(option.upper())
			self._regenerate(self._optionsList)
		except ValueError:
			pass

	def get_all(self) -> List[str]:
		"""Returns all the options."""
		return self._optionsList

	def has_k0(self) -> bool:
		"""Returns true, if the instrument has K0 installed."""
		return self._has_k0

	# noinspection PyMethodMayBeStatic
	def _get_list_of_search_elements(self, options) -> List[str]:
		"""Internal method to convert the options input to list of strings"""
		if not isinstance(options, list):
			if '/' not in options:
				# Simple string, no list, create list of one element
				return [options]
			else:
				# String with '/' delimiter, create list out of it
				return re.split(r'\s*/\s*', options)
		else:
			return options

	def has(self, options: str or List[str]) -> bool:
		"""Returns true, if the entered options (case-insensitive) matches at least one of the installed options (or-logic).
		You can enter either a string with one option, or more options '/'-separated, or more options as a list of strings.
		If K0 is present, all the K-options are reported as present. B-options are not affected by K0.
		Example 1: options='k23' returns true, if the instrument has the option 'K23'.
		Example 2: options='k23 / K23e' returns true, if the instrument has either the option 'K23' or the option 'K23E'.
		Example 3: options=['k11','K22'] returns true, if the instrument has either the option 'K11' or the option 'K22'."""
		els = self._get_list_of_search_elements(options)
		for el in els:
			el = el.upper().strip()
			if el.startswith('K') and self._has_k0:
				return True

			if el in self._optionsListUc:
				return True
		return False

	def has_regex(self, re_options: str or List[str]) -> bool:
		"""Returns true, if the entered regex string (case-insensitive) matches at least one of the installed options.
		The match must be complete, not just partial (search).
		You can enter either a string with one option, or more options '/'-separated, or more options as a list of strings.
		Example 1: re_options='k10.' returns true, if the instrument contains any option 'K100' ... up to 'K109' .
		Example 2: re_options='k10. / k20.*' returns true, if the instrument contains any of the options 'K10x' or 'K20xxx'.
		Example 3: re_options=['k10.', 'k20.*'] returns true, if the instrument contains any options 'K10x' or 'K20xxx'."""
		els = self._get_list_of_search_elements(re_options)

		for el in els:
			el = el.strip()
			if el.upper().startswith('K') and self._has_k0:
				return True
			for opt in self._optionsList:
				matches = re.match(el, opt, re.IGNORECASE)
				if matches:
					if matches.group() == opt:
						return True
		return False
