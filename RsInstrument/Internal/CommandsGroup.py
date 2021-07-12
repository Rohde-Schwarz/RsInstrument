"""See the class docstring."""

from enum import Enum
from typing import List
from .Core import Core
from .RepeatedCapability import RepeatedCapability as RepCap
from .InstrumentErrors import DriverValueError


class CommandsGroup:
	"""Contains methods dealing with RepCaps and Group object cloning"""

	def __init__(self, group_name: str, core: Core, parent: 'CommandsGroup'):
		"""Constructor with header name, group property name and the start value"""

		self.group_name = group_name
		self._core = core
		self.parent = parent
		self.io = core.io
		self.existing_children = []
		self.rep_cap: RepCap or None = None
		self.multi_repcap_types: str = ''
		if parent:
			parent.existing_children.append(self)

	def __str__(self):
		"""String representation of the CommandsGroup"""
		out = f"SCPI Commands Group {self.group_name}"
		if self.has_repcap():
			out += f', RepCap {self.rep_cap.name} = {self.rep_cap.get_enum_value()}'
		return out

	def has_repcap(self) -> bool:
		"""Returns True, if the group has a RepCap.
		Returns False for a group with MultiRepCaps"""
		return self.rep_cap is not None

	def has_multi_repcaps(self) -> bool:
		"""Returns True for a group with MultiRepCaps"""
		return self.multi_repcap_types != ''

	def add_existing_child(self, child: 'CommandsGroup') -> None:
		"""Adds the child to the parent's list of created children.
		This is used when the group is cloned, where the whole existing tree of groups have to be recreated"""
		self.existing_children.append(child)

	def set_repcap_enum_value(self, enum_value: Enum) -> None:
		"""Sets RepCap value as enum
		Default is not allowed."""
		try:
			self.rep_cap.set_enum_value(enum_value)
		except ValueError:
			raise DriverValueError(self.io.resource_name, f"Commands group RepCap value '{self.rep_cap.name}.Default' cannot be set. Please select a concrete value.")

	def get_repcap_enum_value(self) -> Enum:
		"""Returns RepCap value as enum"""
		return self.rep_cap.get_enum_value()

	def get_repcap_cmd_value(self, enum_value: Enum, enum_type) -> str:
		"""Returns the current string of RepCapCmdValue for the entered RepCapEnumName
		The enum_value can be a repcap of the current CommandsGroup or any of their parents"""
		# Use the static functions of the RepeatedCapability to get the non-default value
		# It is faster, since there is no need to use the RepCap instance
		if not RepCap.clsm_is_default_value(enum_value, enum_type):
			return RepCap.clsm_get_cmd_string_value(enum_value, enum_type)
		# Default value - get it from the group or the parent groups
		group = self
		while group is not None:
			if group.has_repcap():
				if group.rep_cap.matches_type(enum_type):
					return group.rep_cap.get_cmd_string_value()
			group = group.parent

		# repCapEnumName not found in single repcaps. Check the multiRepCaps
		group = self
		while group is not None:
			if group.has_multi_repcaps():
				if str(enum_type.__name__) in group.multi_repcap_types.split(','):
					# Found in the multiple repcaps, create more fitting exception message
					raise DriverValueError(
						self.io.resource_name,
						f"You can not use the RepCap value '{enum_value}', "
						f"because its real value is not defined in any of the parent command groups. Please select a concrete value.")
			group = group.parent

		# repCapEnumName not found, create exception message
		group = self
		groups = []
		while group is not None:
			item = group.group_name
			if group.has_repcap():
				item += f' => {group.rep_cap.name}'
			groups.insert(0, item)
			group = group.parent

		groups_chain = str.join("\n", groups)
		raise DriverValueError(
			self.io.resource_name,
			f"Error replacing RepCaps in the SCPI command:"
			f"RepCap '{enum_type}' not found in the group chain:\n{groups_chain}")

	def get_owners_chain(self, stop: 'CommandsGroup' = None) -> List['CommandsGroup']:
		"""Returns the owners chain including itself up to the entered point or up to the root by default"""
		chain = []
		group = self
		while group != stop:
			chain.append(group)
			group = group.parent
		return chain

	def get_self_and_desc_existing_children(self) -> List['CommandsGroup']:
		"""Get all the existing descendant groups recursively"""
		all_descendants = [self]
		for x in self.existing_children:
			all_descendants.extend(x.get_self_and_desc_existing_children())
		return all_descendants

	def synchronize_repcaps(self, new_group) -> None:
		"""Clones the existing group repeated capabilities to the new one.
		Because of the lazy group properties, the group clones are created by accessing the repcaps in them"""
		all_existing = filter(lambda grp: grp.has_repcap(), self.get_self_and_desc_existing_children())
		for x in all_existing:
			chain = x.get_owners_chain(self)
			chain.reverse()
			group = new_group
			for item in chain:
				group = getattr(group, item.group_name)
			fnc = getattr(group, x.rep_cap.method_set_name)
			fnc(x.rep_cap.get_enum_value())

	def restore_repcaps(self) -> None:
		"""Sets RepCaps of the Group and its children groups to their initial values"""
		all_existing = filter(lambda grp: grp.has_repcap(), self.get_self_and_desc_existing_children())
		for x in all_existing:
			x.rep_cap.set_to_start_value()
