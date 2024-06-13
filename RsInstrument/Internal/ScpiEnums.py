"""Provides conversions between SCPI enums and strings."""

from enum import Enum
from typing import List

enum_spec_prefixes = {'_minus': '-', '_plus': '+', '_': ''}
enum_spec_strings = {'_dash_': '-', '_dot_': '.', '_cma_': ','}


class ScpiEnum:
    """Provides methods for enum members search including the ones with custom SCPI strings."""

    def __init__(self, enum_type):
        self.enum_type = enum_type
        self._members_raw = [x.name for x in self.enum_type]
        self.has_custom_values = any(isinstance(x.value, str) for x in self.enum_type)
        self.has_quotes = False
        self._custom_values = None
        self._members_special = None
        if self.has_custom_values:
            self.members = []
            self._custom_values = {}
            for x in self.enum_type:
                item = x.value if isinstance(x.value, str) else x.name
                if self.has_quotes is False:
                    self.has_quotes = "'" in item
                self.members.append(item)
                self._custom_values[x.name] = item
        else:
            self.members = self._members_raw

    def get_scpi_value(self, enum_value: str) -> str:
        """Returns the SCPI value of the enum item: name for the integer value and value for the string value."""
        if not self.has_custom_values:
            return enum_value
        return self._custom_values[enum_value]

    def find_in_enum_members(self, item: str, force_comma_remove: bool) -> Enum or None:
        """Returns either an EnumMember item or null if not found.
        The matching is done against the Members, and if unsuccessful, then against the _members_special
        The response is always a _members_raw item."""
        ix = self._find_ix_in_enum_members(item, force_comma_remove, self.members)
        if ix >= 0:
            return self.enum_type[self._members_raw[ix]]

        self._init_special_values()
        ix = self._find_ix_in_enum_members(item, force_comma_remove, self._members_special)
        if ix >= 0:
            return self.enum_type[self._members_raw[ix]]
        return None

    @staticmethod
    def _find_ix_in_enum_members(item: str, force_comma_remove: bool, enum_members: List[str]) -> int:
        """Matches an item in the provided list of enum_member strings.
        The item must be not fully matched.
        The item is matched if a member string starts with the item (the item is a prefix of the member).
        Example: item='CONN' matches the enum_member 'CONNected'.
        If the item contains a comma, the function checks if there is a comma defined in the enum_members.
        - If no, the comma and all after it is removed.
        - If yes, the comma is kept.
        You can override the behaviour by forcing the removal of the comma
        Returns found index in the enum_members list."""
        if ',' in item:
            trim_comma = True
            if force_comma_remove is False:
                for x in enum_members:
                    if '_cma_' in x or ',' in x:
                        trim_comma = False
                        break
            if trim_comma:
                item = item[:item.index(',')].strip()
        i = 0
        for x in enum_members:
            if x.startswith(item):
                return i
            i += 1

        # smart matching:
        # item = 'MAX' matches enum_member 'MAXpeak'
        # item = 'SPECtrum1' matches enum_member 'SPEC1'
        # item = 'SPEC' matches enum_member 'SPECtrum1'

        item = ''.join([c for c in item if not c.islower()])
        # item must be longer than 1 character
        if len(item) < 2:
            return -1
        i = 0
        for x in enum_members:
            x_uc = ''.join([c for c in x if not c.islower()])
            if x_uc == item:
                return i
            i += 1
        return -1

    def _init_special_values(self):
        """Convert the members to the SCPI values - values to be sent to the instrument
        Resolves escapes:
        '^_' => ''
        '^_minus' => '-'
        '_dash_' => '-'
        '_dot_' => '.'
        '_cma_' => ','
        This is a lazy init of the self._members_special property, since most of the enums do not have any special values.
        """
        if self._members_special is not None:
            return
        self._members_special = []
        for i in range(len(self.members)):
            mem = self.members[i]
            for key in enum_spec_prefixes:
                if mem.startswith(key):
                    mem = enum_spec_prefixes[key] + mem[len(key):]
            for key in enum_spec_strings:
                mem = mem.replace(key, enum_spec_strings[key])
            self._members_special.append(mem)
