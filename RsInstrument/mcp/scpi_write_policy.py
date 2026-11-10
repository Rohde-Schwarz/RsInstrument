"""MCP SCPI write policy: forbid / needs_confirmation / allowed."""

from __future__ import annotations

import fnmatch
import functools
import importlib.resources
import json
import logging
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

logger = logging.getLogger(__name__)

WriteOutcome = Literal["allowed", "needs_confirmation", "forbidden"]

_OUTCOME_RANK = {"allowed": 0, "needs_confirmation": 1, "forbidden": 2}

_FLOAT_ARG = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?)\s*([A-Za-z]*)$",
)

_SCPI_MAX_KEYWORDS: frozenset[str] = frozenset({"MAX", "MAXIMUM", "UP"})


@dataclass(frozen=True)
class WriteGateResult:
    """Result of evaluating a SCPI write against policy rules."""

    outcome: WriteOutcome
    reason: str
    rule_id: str
    command: str
    model: str = ""


@dataclass(frozen=True)
class _PatternRule:
    """Match the full normalized command (typically header-only writes)."""

    rule_id: str
    pattern: re.Pattern[str]
    outcome: WriteOutcome
    reason: str
    models: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ValueRule:
    """Match a command header, then gate on the whitespace-separated argument.

    Exactly one of ``float_gt`` or ``string_values`` must be set:

    * ``float_gt`` — parse ``<number> [unit]`` and trigger when value > threshold.
    * ``string_values`` — trigger when the argument token is in the set.
    """

    rule_id: str
    header_pattern: re.Pattern[str]
    outcome: WriteOutcome
    reason_template: str
    models: tuple[str, ...] = ()
    float_gt: float | None = None
    allowed_units: frozenset[str] = field(
        default_factory=lambda: frozenset({"", "DBM", "DB"}),
    )
    string_values: frozenset[str] | None = None


@dataclass(frozen=True)
class _ExclusionRecord:
    """Compiled form of an ExcludeSpec for runtime scope matching."""

    rule_id: str
    models: tuple[str, ...]
    resources: tuple[str, ...]


class PatternRuleSpec(BaseModel):
    """JSON DTO for a pattern-based write rule."""

    rule_id: str
    pattern: str
    outcome: WriteOutcome
    reason: str
    model_substr: str = ""
    models: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fold_model_substr(self, info: ValidationInfo) -> PatternRuleSpec:
        if self.model_substr and self.model_substr not in self.models:
            self.models.append(self.model_substr)
        if self.model_substr:
            source = (info.context or {}).get("source", "")
            if source != "shipped":
                logger.warning("model_substr is deprecated, use models")
        return self


class ValueRuleSpec(BaseModel):
    """JSON DTO for a value-based write rule."""

    rule_id: str
    header_pattern: str
    outcome: WriteOutcome
    reason_template: str
    model_substr: str = ""
    models: list[str] = Field(default_factory=list)
    float_gt: float | None = None
    allowed_units: list[str] = Field(default_factory=lambda: ["", "DBM", "DB"])
    string_values: list[str] | None = None

    @model_validator(mode="after")
    def _fold_model_substr(self, info: ValidationInfo) -> ValueRuleSpec:
        if self.model_substr and self.model_substr not in self.models:
            self.models.append(self.model_substr)
        if self.model_substr:
            source = (info.context or {}).get("source", "")
            if source != "shipped":
                logger.warning("model_substr is deprecated, use models")
        return self

    @model_validator(mode="after")
    def _exactly_one_value_gate(self) -> ValueRuleSpec:
        has_float = self.float_gt is not None
        has_strings = self.string_values is not None
        if has_float == has_strings:
            raise ValueError(
                "ValueRuleSpec requires exactly one of float_gt or string_values",
            )
        return self


class ExcludeSpec(BaseModel):
    """Spec to exclude a rule, optionally scoped by model substring or resource glob.

    A bare string entry is accepted and treated as a global exclusion.
    """

    rule_id: str
    models: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_string(cls, data: object) -> object:
        if isinstance(data, str):
            return {"rule_id": data}
        return data


class WriteRulesFile(BaseModel):
    """Top-level JSON schema for a write-rules file."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str | None = Field(default=None, alias="$schema")
    families: dict[str, list[str]] = Field(default_factory=dict)
    exclude_rules: list[ExcludeSpec] = Field(default_factory=list)
    pattern_rules: list[PatternRuleSpec] = Field(default_factory=list)
    value_rules: list[ValueRuleSpec] = Field(default_factory=list)


def normalize_scpi_command(command: str) -> str:
    """Uppercase, strip leading colon, collapse whitespace, strip trailing ?."""
    normalized = " ".join(command.strip().upper().split())
    normalized = normalized.removeprefix(":")
    if normalized.endswith("?"):
        normalized = normalized[:-1].rstrip()
    return normalized


def split_header_arg(normalized: str) -> tuple[str, str]:
    """Split a normalized SCPI write into header and argument at first whitespace."""
    parts = normalized.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


_COMMAND_AFTER_QUERY = re.compile(r"^\*?:?[A-Za-z][\w:]*\s+\S")


def _query_argument_is_command(arg: str) -> bool:
    """True when text after a query header looks like a second "HEADER VALUE" command.

    Single parameters (``MAX``) and comma-separated lists (``FDATA, 1``) are not
    commands. This is a heuristic, and it is deliberately narrow.
    """
    return bool(arg) and _COMMAND_AFTER_QUERY.match(arg) is not None


def contains_query_marker(command: str) -> bool:
    """True when a ``?`` outside quoted text appears anywhere in the message.

    Used to route a message to the read path, so its response is always read.
    """
    in_single = False
    in_double = False
    for ch in command:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "?" and not in_single and not in_double:
            return True
    return False


def iter_write_segments(command: str) -> list[str]:
    """Return non-query SCPI write statements resolved to their absolute form.

    Implements IEEE 488.2 / SCPI compound-header path tracking across a program
    message (a `;`-separated sequence of statements):

    * A segment whose header starts with ``:`` is **absolute**: the leading ``:``
      is stripped and both path trackers reset to that header.
    * A segment whose header starts with ``*`` is a **common command**: it is used
      as-is and does **not** change the current path.
    * A ``\\r``, ``\\n``, or ``\\r\\n`` delimiter starts a **new program message**:
      the path resets to root.
    * Any other segment is **relative**.  Two sub-cases:

      * **Single-node header** (no ``:`` inside the raw keyword): the
        *instrument-correct parent* (from ``_instr_path``) is prepended as the
        primary emission.  If the raw-path tracker (``_raw_path``) has diverged from
        the instrument-correct tracker (e.g. after a preceding multi-node relative),
        the raw-path-derived form is also emitted as a secondary entry for backward
        compatibility and extra rule coverage.
        ``OUTP:STAT OFF;STAT ON`` → ``OUTP:STAT ON`` (single emission);
        ``SOUR:POW:STAT OFF;GEN:STAT OFF;STAT ON`` →
        primary ``SOUR:POW:GEN:STAT ON`` *and* secondary ``GEN:STAT ON``.
      * **Multi-node header** (contains ``:`` but does not start with ``:``): **both**
        the raw form and the instrument-correct parent-resolved form are emitted; the
        gate takes the max rank over both.  Crucially, ``_instr_path`` advances to the
        parent-resolved form so that subsequent single-node relatives resolve from the
        correct instrument root (e.g.
        ``SOUR:POW:STAT OFF;GEN:STAT OFF;STAT ON`` correctly gates ``SOUR:POW:GEN:STAT ON``).
        ``_raw_path`` retains the raw header for backward-compat dual emission above.

    Query segments (header token ending with ``?``) are **dropped** from the
    returned list but **still advance** both path trackers.

    .. note::
        Multi-node relative segments and single-node relatives following a diverged path
        each contribute two entries to the returned list.  The 25-statement approval
        guard counts these separately.
    """
    # Split while keeping delimiters so we can distinguish ';' from newlines.
    # \r\n is matched as a unit before \r and \n to avoid a spurious empty token.
    parts = re.split(r"(;|\r\n|\r|\n)", command)

    result: list[str] = []
    _instr_path: str = ""  # instrument-correct absolute header of the last segment
    _raw_path: str = ""    # raw-form header (for dual emission from subsequent single-node relatives)
    new_message: bool = True  # True at the start of each program message (root context)

    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            # Delimiter token — decide whether it ends the current program message.
            if part != ";":
                new_message = True   # any newline form resets path to root
            continue

        seg = part.strip()
        if not seg:
            continue

        tokens = seg.split(maxsplit=1)
        raw_header = tokens[0]
        arg = tokens[1] if len(tokens) > 1 else ""
        is_query = raw_header.endswith("?")
        resolved_extra = None  # secondary emission form for dual-emission segments

        # Default: path unchanged (used only by common commands).
        next_instr = _instr_path
        next_raw = _raw_path

        # Resolve the raw header to its absolute canonical form.
        if new_message:
            # First segment of a new program message — already in root context.
            # An explicit leading ':' (absolute form) is stripped for consistency
            # with normalize_scpi_command.
            resolved = raw_header.removeprefix(":")
            next_instr = next_raw = resolved
        elif raw_header.startswith(":"):
            # Explicit absolute path — strip the leading ':'; both trackers reset.
            resolved = raw_header[1:]
            next_instr = next_raw = resolved
        elif raw_header.startswith("*"):
            # Common command — use as-is; path trackers are unchanged (see default above).
            resolved = raw_header
        else:
            # Relative path: derive parents from both instrument-correct and raw paths.
            colon_i = _instr_path.rfind(":")
            parent_i = _instr_path[:colon_i] if colon_i != -1 else ""

            colon_r = _raw_path.rfind(":")
            parent_r = _raw_path[:colon_r] if colon_r != -1 else ""

            if ":" not in raw_header:
                # Single-node relative.
                # Primary: instrument-correct parent prepended.
                resolved = f"{parent_i}:{raw_header}" if parent_i else raw_header
                # Secondary: raw-path-derived form (backward compat / extra coverage).
                raw_derived = f"{parent_r}:{raw_header}" if parent_r else raw_header
                if raw_derived != resolved:
                    resolved_extra = raw_derived
                next_instr = resolved
                next_raw = raw_derived
            else:
                # Multi-node relative.
                # Primary: raw form (backward compat for rules written against it).
                resolved = raw_header
                # Secondary: instrument-correct parent-resolved form (closes bypass).
                if parent_i:
                    resolved_extra = f"{parent_i}:{raw_header}"
                # Advance instrument-correct path to the parent-resolved form so that
                # subsequent single-node relatives start from the right root.
                next_instr = resolved_extra if resolved_extra is not None else resolved
                next_raw = resolved  # raw tracker retains the raw header

        # Advance both path trackers (queries and writes both update them; common
        # commands ('*') do not — their path is not a compound SCPI header).
        if not raw_header.startswith("*"):
            # Strip a trailing '?' so queries still contribute the header path.
            _instr_path = next_instr.removesuffix("?")
            _raw_path = next_raw.removesuffix("?")

        new_message = False

        if is_query and _query_argument_is_command(arg):
            # "FREQ? OUTP ON": the text after a query header can still be parsed as
            # a command by the instrument, so it is gated as a write statement too.
            # A single parameter ("MEAS? MAX") is not a command and is not gated.
            result.append(arg)

        if not is_query:
            full_seg = f"{resolved} {arg}" if arg else resolved
            result.append(full_seg)
            if resolved_extra is not None:
                extra_seg = f"{resolved_extra} {arg}" if arg else resolved_extra
                result.append(extra_seg)

    return result


def _model_matches(models: tuple[str, ...], idn_model: str | None) -> bool:
    if not models:
        return True
    if not (idn_model or "").strip():
        return True  # unknown identity: apply model-scoped rules conservatively
    return any(m.casefold() in idn_model.casefold() for m in models)


def _exclusion_model_matches(models: tuple[str, ...], idn_model: str) -> bool:
    """For exclusions: empty models = global; non-empty requires a known model match.

    When the model is unknown, model-scoped exclusions are NOT applied (stay conservative).
    """
    if not models:
        return True
    idn = (idn_model or "").strip()
    if not idn:
        return False
    return any(m.casefold() in idn.casefold() for m in models)


def _exclusion_resource_matches(resources: tuple[str, ...], resource: str) -> bool:
    """Empty resources = global; otherwise any fnmatch glob must match lowercased resource."""
    if not resources:
        return True
    resource_lower = resource.lower()
    return any(fnmatch.fnmatchcase(resource_lower, r.lower()) for r in resources)


def _exclusion_active(exc: _ExclusionRecord, model: str, resource: str) -> bool:
    """Return True when both model and resource scopes match (or are empty)."""
    return _exclusion_model_matches(exc.models, model) and _exclusion_resource_matches(
        exc.resources, resource
    )


def _parse_float_arg(arg: str, allowed_units: frozenset[str]) -> float | None:
    """Parse ``value [unit]``; return None when unparseable or unit not allowed."""
    match = _FLOAT_ARG.match(arg.strip())
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "").upper()
    if unit not in allowed_units:
        logger.warning("Skipping float threshold for unit %r in argument %r", unit, arg)
        return None
    return value


def _match_value_rule(
    rule: _ValueRule,
    header: str,
    arg: str,
) -> str | float | None:
    """Return the matched display value when the rule triggers, else None."""
    if not re.search(rule.header_pattern, header):
        return None
    if not arg:
        return None

    if rule.string_values is not None:
        token = arg.split(None, 1)[0]
        if token in rule.string_values:
            return token
        return None

    if rule.float_gt is not None:
        token = arg.split(None, 1)[0].upper()
        if token in _SCPI_MAX_KEYWORDS:
            return token  # conservative: treat as exceeding any threshold
        value = _parse_float_arg(arg, rule.allowed_units)
        if value is not None and value > rule.float_gt:
            return value
        return None

    return None


def _compile_pattern_spec(spec: PatternRuleSpec) -> _PatternRule:
    return _PatternRule(
        rule_id=spec.rule_id,
        pattern=re.compile(spec.pattern, re.IGNORECASE),
        outcome=spec.outcome,
        reason=spec.reason,
        models=tuple(spec.models),
    )


def _compile_value_spec(spec: ValueRuleSpec) -> _ValueRule:
    string_values = (
        frozenset(spec.string_values) if spec.string_values is not None else None
    )
    return _ValueRule(
        rule_id=spec.rule_id,
        header_pattern=re.compile(spec.header_pattern, re.IGNORECASE),
        outcome=spec.outcome,
        reason_template=spec.reason_template,
        models=tuple(spec.models),
        float_gt=spec.float_gt,
        allowed_units=frozenset(u.upper() for u in spec.allowed_units),
        string_values=string_values,
    )


def _validate(file: WriteRulesFile, source: str) -> None:
    """Compile all regexes and enforce unique rule_id across both rule lists."""
    seen_ids: set[str] = set()
    for spec in file.pattern_rules:
        if spec.rule_id in seen_ids:
            raise ValueError(f"{source}: rule {spec.rule_id}: duplicate rule_id")
        seen_ids.add(spec.rule_id)
        try:
            re.compile(spec.pattern)
        except re.error as exc:
            raise ValueError(
                f"{source}: rule {spec.rule_id}: invalid pattern: {exc}"
            ) from exc
    for spec in file.value_rules:
        if spec.rule_id in seen_ids:
            raise ValueError(f"{source}: rule {spec.rule_id}: duplicate rule_id")
        seen_ids.add(spec.rule_id)
        try:
            re.compile(spec.header_pattern)
        except re.error as exc:
            raise ValueError(
                f"{source}: rule {spec.rule_id}: invalid header_pattern: {exc}"
            ) from exc


def _warn_exclusions(
    exclusions: list[ExcludeSpec],
    *,
    all_known_ids: set[str],
    forbidden_ids: set[str],
) -> None:
    for spec in exclusions:
        if spec.rule_id not in all_known_ids:
            logger.warning(
                "Exclusion for unknown rule_id %r; exclusion has no effect", spec.rule_id
            )
        elif spec.rule_id in forbidden_ids:
            logger.warning(
                "Excluding a forbidden rule %r; this is the explicit escape hatch but may reduce safety",
                spec.rule_id,
            )


def _resolve_family_refs(
    models: list[str],
    families: dict[str, list[str]],
    source: str,
    rule_id: str,
) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for entry in models:
        if entry.startswith("@"):
            name = entry[1:]
            if name not in families:
                raise ValueError(
                    f"{source}: rule {rule_id}: unknown family '@{name}'"
                )
            for m in families[name]:
                if m not in seen:
                    seen.add(m)
                    resolved.append(m)
        else:
            if entry not in seen:
                seen.add(entry)
                resolved.append(entry)
    return resolved


def _apply_family_resolution(
    file_model: WriteRulesFile,
    families: dict[str, list[str]],
    source: str,
) -> None:
    for spec in file_model.pattern_rules:
        spec.models = _resolve_family_refs(spec.models, families, source, spec.rule_id)
    for spec in file_model.value_rules:
        spec.models = _resolve_family_refs(spec.models, families, source, spec.rule_id)


def _policy_from_write_rules_file(file_model: WriteRulesFile) -> ScpiWritePolicy:
    pattern_rules = tuple(
        _compile_pattern_spec(spec) for spec in file_model.pattern_rules
    )
    value_rules = tuple(_compile_value_spec(spec) for spec in file_model.value_rules)
    return ScpiWritePolicy(pattern_rules=pattern_rules, value_rules=value_rules)


@functools.cache
def _load_shipped_default_policy() -> ScpiWritePolicy:
    data_path = (
        importlib.resources.files("RsInstrument.mcp") / "data" / "default_write_rules.json"
    )
    if not data_path.is_file():
        msg = f"Shipped write rules data file not found: {data_path}"
        raise FileNotFoundError(msg)
    text = data_path.read_text(encoding="utf-8")
    data = json.loads(text)
    file_model = WriteRulesFile.model_validate(data, context={"source": "shipped"})
    _apply_family_resolution(file_model, file_model.families, "shipped default_write_rules.json")
    _validate(file_model, "shipped default_write_rules.json")
    return _policy_from_write_rules_file(file_model)


_RuleT = TypeVar("_RuleT", _PatternRule, _ValueRule)


def _merge_by_rule_id(
    defaults: tuple[_RuleT, ...],
    overlays: list[_RuleT],
) -> tuple[_RuleT, ...]:
    """Overlay rules onto defaults by ``rule_id`` (file wins); append new ids.

    A custom rule whose ``rule_id`` matches a default with ``outcome=="forbidden"``
    is ignored entirely; only ``exclude_rule_ids`` can remove such a rule.
    """
    by_id: dict[str, _RuleT] = {rule.rule_id: rule for rule in defaults}
    order = [rule.rule_id for rule in defaults]
    for rule in overlays:
        if rule.rule_id in by_id and by_id[rule.rule_id].outcome == "forbidden":
            logger.warning(
                "custom rule %s cannot override a forbidden default; use exclude_rule_ids",
                rule.rule_id,
            )
            continue
        if rule.rule_id not in by_id:
            order.append(rule.rule_id)
        by_id[rule.rule_id] = rule
    return tuple(by_id[rule_id] for rule_id in order)


@dataclass(frozen=True)
class ScpiWritePolicy:
    """Compiled write-policy rules used by MCP write tools."""

    pattern_rules: tuple[_PatternRule, ...]
    value_rules: tuple[_ValueRule, ...]
    exclusions: tuple[_ExclusionRecord, ...] = ()

    def evaluate(
        self, command: str, *, model: str, resource: str = ""
    ) -> WriteGateResult:
        """Evaluate a SCPI write against this policy.

        Multi-statement commands (``;``-separated) are evaluated statement by
        statement; the most restrictive outcome wins
        (forbidden > needs_confirmation > allowed).
        """
        segments = iter_write_segments(command)
        if not segments:
            return WriteGateResult(
                outcome="allowed",
                reason="",
                rule_id="",
                command=normalize_scpi_command(command),
                model=model,
            )
        best = WriteGateResult(
            outcome="allowed",
            reason="",
            rule_id="",
            command=normalize_scpi_command(command),
            model=model,
        )
        for segment in segments:
            candidate = self._evaluate_segment(segment, model=model, resource=resource)
            if _OUTCOME_RANK[candidate.outcome] > _OUTCOME_RANK[best.outcome]:
                best = candidate
        return best

    def _evaluate_segment(
        self, command: str, *, model: str, resource: str = ""
    ) -> WriteGateResult:
        """Evaluate a single SCPI statement (no ``;`` chaining)."""
        normalized = normalize_scpi_command(command)
        best = WriteGateResult(
            outcome="allowed",
            reason="",
            rule_id="",
            command=normalized,
            model=model,
        )

        excluded = frozenset(
            exc.rule_id
            for exc in self.exclusions
            if _exclusion_active(exc, model, resource)
        )

        for rule in self.pattern_rules:
            if rule.rule_id in excluded:
                continue
            if not _model_matches(rule.models, model):
                continue
            if re.search(rule.pattern, normalized):
                candidate = WriteGateResult(
                    outcome=rule.outcome,
                    reason=rule.reason,
                    rule_id=rule.rule_id,
                    command=normalized,
                    model=model,
                )
                if _OUTCOME_RANK[candidate.outcome] > _OUTCOME_RANK[best.outcome]:
                    best = candidate

        header, arg = split_header_arg(normalized)
        for rule in self.value_rules:
            if rule.rule_id in excluded:
                continue
            if not _model_matches(rule.models, model):
                continue
            matched = _match_value_rule(rule, header, arg)
            if matched is None:
                continue
            candidate = WriteGateResult(
                outcome=rule.outcome,
                reason=rule.reason_template.format(value=matched),
                rule_id=rule.rule_id,
                command=normalized,
                model=model,
            )
            if _OUTCOME_RANK[candidate.outcome] > _OUTCOME_RANK[best.outcome]:
                best = candidate

        return best

    def without_rules(self, rule_ids: Collection[str]) -> ScpiWritePolicy:
        """Return a copy with the given ``rule_id`` values removed (unknown ignored)."""
        drop = set(rule_ids)
        return ScpiWritePolicy(
            pattern_rules=tuple(r for r in self.pattern_rules if r.rule_id not in drop),
            value_rules=tuple(r for r in self.value_rules if r.rule_id not in drop),
            exclusions=self.exclusions,
        )

    def with_exclusions(
        self, new_exclusions: Collection[_ExclusionRecord]
    ) -> ScpiWritePolicy:
        """Return a copy with additional scoped exclusions appended."""
        return ScpiWritePolicy(
            pattern_rules=self.pattern_rules,
            value_rules=self.value_rules,
            exclusions=self.exclusions + tuple(new_exclusions),
        )

    @classmethod
    def defaults(
        cls,
        exclude_rule_ids: Collection[str] = (),
    ) -> ScpiWritePolicy:
        """Built-in policy (compiled pattern and value rules)."""
        policy = _load_shipped_default_policy()
        if exclude_rule_ids:
            return policy.without_rules(exclude_rule_ids)
        return policy

    @classmethod
    def from_file(cls, path: Path) -> ScpiWritePolicy:
        """Load JSON → Pydantic DTOs → compile → merge onto defaults by ``rule_id``.

        Raises:
            FileNotFoundError: Path does not exist.
            json.JSONDecodeError: File is not valid JSON.
            pydantic.ValidationError: JSON does not match the write-rules schema.
            ValueError: Duplicate rule_id or invalid regex in the custom file.
        """
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        file_model = WriteRulesFile.model_validate(data, context={"source": str(path)})
        _validate(file_model, str(path))

        # Merge families: shipped base then custom (custom redefines warn, custom wins).
        shipped_data_path = (
            importlib.resources.files("RsInstrument.mcp") / "data" / "default_write_rules.json"
        )
        shipped_families: dict[str, list[str]] = json.loads(
            shipped_data_path.read_text(encoding="utf-8")
        ).get("families", {})
        merged_families: dict[str, list[str]] = dict(shipped_families)
        for name, models in file_model.families.items():
            if name in shipped_families:
                logger.warning(
                    "Custom rules %s redefines shipped family '%s'; custom definition wins",
                    path,
                    name,
                )
            merged_families[name] = models
        _apply_family_resolution(file_model, merged_families, str(path))

        pattern_overlays = [
            _compile_pattern_spec(spec) for spec in file_model.pattern_rules
        ]
        value_overlays = [_compile_value_spec(spec) for spec in file_model.value_rules]
        base = cls.defaults()
        exclusions = tuple(
            _ExclusionRecord(
                rule_id=spec.rule_id,
                models=tuple(spec.models),
                resources=tuple(spec.resources),
            )
            for spec in file_model.exclude_rules
        )
        _warn_exclusions(
            file_model.exclude_rules,
            all_known_ids=(
                {r.rule_id for r in base.pattern_rules}
                | {r.rule_id for r in base.value_rules}
                | {spec.rule_id for spec in file_model.pattern_rules}
                | {spec.rule_id for spec in file_model.value_rules}
            ),
            forbidden_ids=(
                {r.rule_id for r in base.pattern_rules if r.outcome == "forbidden"}
                | {r.rule_id for r in base.value_rules if r.outcome == "forbidden"}
            ),
        )
        return cls(
            pattern_rules=_merge_by_rule_id(base.pattern_rules, pattern_overlays),
            value_rules=_merge_by_rule_id(base.value_rules, value_overlays),
            exclusions=exclusions,
        )


def evaluate_write(
    command: str,
    *,
    model: str,
    resource: str = "",
    policy: ScpiWritePolicy | None = None,
) -> WriteGateResult:
    """Evaluate a SCPI write; ``policy=None`` uses :meth:`ScpiWritePolicy.defaults`."""
    return (policy or ScpiWritePolicy.defaults()).evaluate(
        command, model=model, resource=resource
    )
