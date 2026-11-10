"""Status-error suppression rules used by instrument status checking.

This module filters instrument status errors *after* they are read from
``SYST:ERR?`` and *before* :class:`StatusException` is raised.

Rule input formats:
- ``(code, pattern)``: suppress only when both code and message match.
- ``pattern``: suppress by message regardless of code.
- ``code`` (int): suppress by error code regardless of message.

Each ``pattern`` can be:
- regex source string, or
- compiled ``re.Pattern[str]``.

Matching uses ``re.search()`` semantics.
"""

from __future__ import annotations

import re
import threading
from typing import Iterable, List, Pattern, Tuple

# The input rule definition can be:
# - a tuple of (code, regex pattern)
# - a tuple of (code, string) - string is compiled to a regex pattern
# - a regex pattern - code is not relevant
# - a string, will be compiled to a regex pattern, code is not relevant
# - an integer, only the error code will be considered, message is not relevant
RawSuppressionRule = Tuple[int, str | Pattern[str]] | str | Pattern[str] | int


class InstrumentStatusErrorRule:
	"""Base suppression rule for one instrument status-error matching strategy."""

	def __init__(self, owner: InstrumentStatusErrorSuppressor, code: int | None, pattern: str | Pattern[str] | None):
		self._owner: InstrumentStatusErrorSuppressor = owner

		self._code: int | None = code
		self._resolve_pattern(pattern)

	@property
	def code(self) -> int | None:
		"""Read-only property for instrument error code."""
		return self._code

	@property
	def message_pattern(self) -> re.Pattern | None:
		"""Read-only property for instrument message as regex pattern."""
		return self._message_pattern

	def remove(self) -> None:
		"""Removes itself from the list of suppression rules."""
		self._owner.remove_rule(self)

	def matches(self, code: int, message: str) -> bool:
		"""Return True when the entered error tuple should be suppressed."""
		# Code evaluation
		if self._code is not None:
			if self._code != code:
				return False
		# Message evaluation
		if self._message_pattern is not None:
			return self._message_pattern.search(message) is not None

		return True

	def _eq_key(self) -> tuple:
		"""Return the hashable value-identity key used for equality and hashing.

		Two rules are equal when they have the same code and the same message
		pattern (its source string and flags). A missing code or pattern is
		represented by ``None`` so the different rule kinds never collide."""
		if self._message_pattern is None:
			pattern_key = None
		else:
			pattern_key = (self._message_pattern.pattern, self._message_pattern.flags)
		return self._code, pattern_key

	def _resolve_pattern(self, pattern: str | Pattern[str] | None) -> None:
		"""Compiles a regex source string once or pass through compiled patterns."""
		if pattern is None:
			self._message_pattern = None
		elif isinstance(pattern, str):
			self._message_pattern = re.compile(pattern)
		elif isinstance(pattern, re.Pattern):
			self._message_pattern = pattern
		else:
			raise TypeError(f"Pattern must be str or re.Pattern[str], got '{type(pattern).__name__}'")

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, InstrumentStatusErrorRule):
			return NotImplemented
		if self.__class__ is not other.__class__:
			return NotImplemented
		return self._eq_key() == other._eq_key()

	def __hash__(self) -> int:
		return hash((self.__class__, self._eq_key()))

	def __repr__(self) -> str:
		if (self._code is not None) and (self._message_pattern is not None):
			return f"InstrumentStatusErrorRule(code={self._code}, pattern={self._message_pattern.pattern!r})"
		if self._code is not None:
			return f"InstrumentStatusErrorRule(code={self._code})"
		return f"InstrumentStatusErrorRule(pattern={self._message_pattern.pattern!r})"


class InstrumentStatusErrorSuppressor:
	"""Holds status-error suppression rules and answers matching queries.

	Rules are managed with :meth:`add_rule` / :meth:`add_rules` /
	:meth:`remove_rule` / :meth:`clear_rules`. Use :meth:`matches_any` to test
	whether an error (code, message) should be suppressed.

	The instance is thread-safe: all access to the internal rule list is guarded
	by a re-entrant lock, so rules can be added/removed from one thread while
	another thread runs status checking.
	"""

	def __init__(self):
		self._rules: List[InstrumentStatusErrorRule] = []
		self._lock = threading.RLock()

	def add_rule(self, rule: RawSuppressionRule) -> InstrumentStatusErrorRule:
		"""Adds one suppression rule and returns the created rule object.

		The ``rule`` argument can be one of the following:

		- ``(code, pattern)`` tuple: suppress only when the error code equals ``code``
			AND the message matches ``pattern`` (logical AND). Either element may be
			``None`` to ignore that dimension (but not both).
		- ``pattern`` (``str`` or ``re.Pattern``): suppress by message only, for any
			error code.
		- ``code`` (``int``): suppress by error code only, for any message.
		- an already-built :class:`InstrumentStatusErrorRule`: stored as-is.

		All forms produce an :class:`InstrumentStatusErrorRule`.

		A ``pattern`` is either a regex source string (compiled with ``re.compile``)
		or an already-compiled ``re.Pattern``. Message matching uses ``re.search()``,
		so the pattern only has to be found *somewhere* in the message, not match it
		in full.

		Rules are de-duplicated by value: adding a rule that is equal to one already
		in the list (same code and/or same pattern source string and flags) does not
		create a second entry, and the existing/normalized rule is returned.

		:param rule: The rule definition, in any of the forms listed above.
		:return: The normalized :class:`InstrumentStatusErrorRule` that was added
			(or the equal one already present). Keep this reference to remove the
			rule later with :meth:`remove_rule`.
		:raises TypeError: If ``rule`` (or a tuple's code/pattern) has an unsupported type.
		:raises ValueError: If a tuple rule does not have exactly two elements.
		"""
		resolved = self._create_rule(rule)
		with self._lock:
			if resolved not in self._rules:
				self._rules.append(resolved)
		return resolved

	def remove_rule(self, rule: InstrumentStatusErrorRule) -> bool:
		"""Removes the entered rule from the error suppression list.
		Returns true, if the rule existed in the list."""
		with self._lock:
			if rule in self._rules:
				self._rules.remove(rule)
				return True
			return False

	def add_rules(self, rules: Iterable[RawSuppressionRule]) -> None:
		"""Same as the ``add_rule()``, but the parameter is a collection of rules."""
		with self._lock:
			for rule in rules:
				self.add_rule(rule)

	def clear_rules(self) -> None:
		"""Clears all the existing rules."""
		with self._lock:
			self._rules.clear()

	@property
	def rules(self) -> List[InstrumentStatusErrorRule]:
		"""Return copy of the configured, normalized rule objects."""
		with self._lock:
			return list(self._rules)

	def has_rules(self) -> bool:
		"""Returns true, if the suppressor has at least one rule."""
		with self._lock:
			return bool(self._rules)

	def matches_any(self, code: int, message: str) -> bool:
		"""Return true if any of the rules match."""
		# Take a snapshot under the lock, then match without holding it, so a slow
		# regex cannot block concurrent add_rule()/remove_rule() calls.
		with self._lock:
			rules = tuple(self._rules)
		for rule in rules:
			if rule.matches(code, message):
				return True
		return False

	def _create_rule(self, raw_rule: RawSuppressionRule) -> InstrumentStatusErrorRule:
		"""Convert the different rule input types into a concrete rule object it returns.

		Accepted formats:
		- ``InstrumentStatusErrorRule`` instance
		- ``(int, str | re.Pattern[str])`` tuple
		- ``str | re.Pattern[str]`` message-only pattern
		- ``int`` code only
		"""
		if isinstance(raw_rule, InstrumentStatusErrorRule):
			return raw_rule

		if isinstance(raw_rule, tuple):
			# Tuple entered, split it to code and message, both have to be non-None
			if len(raw_rule) != 2:
				raise ValueError(f"Tuple suppression rule must have length 2 (code, message_patter), got {len(raw_rule)}")

			# Split the tuple to code and message
			code, pattern = raw_rule
			if code is None and pattern is None:
				raise ValueError(f"Tuple suppression rule must have either code or pattern")
			if code is not None and not isinstance(code, int):
				raise TypeError(f"Tuple suppression rule first parameter code must be int, got '{type(code).__name__}'")
			if pattern is not None and not isinstance(pattern, (str, re.Pattern)):
				raise TypeError(f"Tuple suppression rule second parameter message must be string or regex pattern, got '{type(pattern).__name__}'")

			return InstrumentStatusErrorRule(self, code, pattern)

		if isinstance(raw_rule, (str, re.Pattern)):
			# String or regex pattern entered
			return InstrumentStatusErrorRule(self, None, raw_rule)

		if isinstance(raw_rule, int):
			return InstrumentStatusErrorRule(self, raw_rule, None)

		raise TypeError(
			f"Unsupported suppression rule type '{type(raw_rule).__name__}'. "
			"Allowed: tuple(code, pattern) / str (regex pattern) / re.Pattern / int (code)"
		)
