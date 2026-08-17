"""MCP SCPI write policy: forbid / needs_confirmation / allowed."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

WriteOutcome = Literal["allowed", "needs_confirmation", "forbidden"]

_OUTCOME_RANK = {"allowed": 0, "needs_confirmation": 1, "forbidden": 2}

_FLOAT_ARG = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*([A-Za-z]*)$",
)


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
    model_substr: str = ""


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
    model_substr: str = ""
    float_gt: float | None = None
    allowed_units: frozenset[str] = field(
        default_factory=lambda: frozenset({"", "DBM", "DB"}),
    )
    string_values: frozenset[str] | None = None


class PatternRuleSpec(BaseModel):
    """JSON DTO for a pattern-based write rule."""

    rule_id: str
    pattern: str
    outcome: WriteOutcome
    reason: str
    model_substr: str = ""


class ValueRuleSpec(BaseModel):
    """JSON DTO for a value-based write rule."""

    rule_id: str
    header_pattern: str
    outcome: WriteOutcome
    reason_template: str
    model_substr: str = ""
    float_gt: float | None = None
    allowed_units: list[str] = Field(default_factory=lambda: ["", "DBM", "DB"])
    string_values: list[str] | None = None

    @model_validator(mode="after")
    def _exactly_one_value_gate(self) -> ValueRuleSpec:
        has_float = self.float_gt is not None
        has_strings = self.string_values is not None
        if has_float == has_strings:
            raise ValueError(
                "ValueRuleSpec requires exactly one of float_gt or string_values",
            )
        return self


class WriteRulesFile(BaseModel):
    """Top-level JSON schema for a write-rules file."""

    pattern_rules: list[PatternRuleSpec] = Field(default_factory=list)
    value_rules: list[ValueRuleSpec] = Field(default_factory=list)


def normalize_scpi_command(command: str) -> str:
    """Uppercase, strip leading colon, collapse whitespace, strip trailing ?."""
    normalized = " ".join(command.strip().upper().split())
    if normalized.startswith(":"):
        normalized = normalized[1:]
    if normalized.endswith("?"):
        normalized = normalized[:-1].rstrip()
    return normalized


def split_header_arg(normalized: str) -> tuple[str, str]:
    """Split a normalized SCPI write into header and argument at first whitespace."""
    parts = normalized.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


_POW_HEADER = re.compile(
    r"^(SOUR(CE)?(\d+)?:)?POW(ER)?$",
    re.IGNORECASE,
)

_PATTERN_RULES: tuple[_PatternRule, ...] = (
    _PatternRule(
        rule_id="global_forbid_syst_sec",
        pattern=re.compile(
            r"^SYST(EM)?:SEC(URITY)?:IMM(EDIATE)?(\s|$)",
            re.IGNORECASE,
        ),
        outcome="forbidden",
        reason=(
            "SYST:SEC:IMM is forbidden by MCP write policy and cannot be executed."
        ),
    ),
    _PatternRule(
        rule_id="global_confirm_rst",
        pattern=re.compile(r"^\*RST(\s|$)", re.IGNORECASE),
        outcome="needs_confirmation",
        reason="Instrument reset (*RST) requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_rcl",
        pattern=re.compile(r"^\*RCL(\s|$)", re.IGNORECASE),
        outcome="needs_confirmation",
        reason=(
            "Instrument recall (*RCL) restores arbitrary state and requires "
            "confirmation. Approve to proceed."
        ),
    ),
    _PatternRule(
        rule_id="global_confirm_rf_output_enable",
        pattern=re.compile(
            r"^OUTP\w*\d*(:STAT\w*)?\s+(ON|1)(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="RF output enable requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_all_rf_outputs_enable",
        pattern=re.compile(
            r"^OUTP\w*:ALL:STAT\w*\s+(ON|1)(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="RF output enable (all paths) requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_iq_output_enable",
        pattern=re.compile(
            r"^OUTP\w*\d*:IQ:STAT\w*\s+(ON|1)(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="IQ output enable requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_reference_level_change",
        pattern=re.compile(
            r"^DISP(LAY)?:TRAC(E)?:Y:SCAL(E)?:RLEV(EL)?(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="Reference level change requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_input_attenuation_change",
        pattern=re.compile(
            r"^INP(UT)?:ATT(ENUATION)?(:[A-Z]+)*(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="Input attenuation change requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_preamplifier_enable",
        pattern=re.compile(
            r"^INP(UT)?:GAIN(:STAT(E)?)?\s+(ON|1)(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="Preamplifier enable requires confirmation. Approve to proceed.",
    ),
    _PatternRule(
        rule_id="global_confirm_mmem_upload",
        pattern=re.compile(
            r"^MMEM(ORY)?:DATA(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="Instrument file upload (MMEM:DATA) requires confirmation.",
    ),
    _PatternRule(
        rule_id="global_confirm_mmem_delete",
        pattern=re.compile(
            r"^MMEM(ORY)?:DEL(ETE)?(\s|$)",
            re.IGNORECASE,
        ),
        outcome="needs_confirmation",
        reason="Instrument file delete (MMEM:DEL) requires confirmation.",
    ),
)

_VALUE_RULES: tuple[_ValueRule, ...] = (
    _ValueRule(
        rule_id="smw200a_pow_hard",
        header_pattern=_POW_HEADER,
        float_gt=20.0,
        outcome="forbidden",
        reason_template=(
            "RF output power {value} dBm exceeds the hard limit of 20 dBm for "
            "SMW200A. This command cannot be executed."
        ),
        model_substr="SMW200A",
    ),
    _ValueRule(
        rule_id="smw200a_pow_soft",
        header_pattern=_POW_HEADER,
        float_gt=0.0,
        outcome="needs_confirmation",
        reason_template=(
            "RF output power {value} dBm exceeds the soft limit of 0 dBm for "
            "SMW200A. Approve to proceed."
        ),
        model_substr="SMW200A",
    ),
)


def _model_matches(model: str, substr: str) -> bool:
    if not substr:
        return True
    return substr.upper() in (model or "").upper()


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
        model_substr=spec.model_substr,
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
        model_substr=spec.model_substr,
        float_gt=spec.float_gt,
        allowed_units=frozenset(u.upper() for u in spec.allowed_units),
        string_values=string_values,
    )


_RuleT = TypeVar("_RuleT", _PatternRule, _ValueRule)


def _merge_by_rule_id(
    defaults: tuple[_RuleT, ...],
    overlays: list[_RuleT],
) -> tuple[_RuleT, ...]:
    """Overlay rules onto defaults by ``rule_id`` (file wins); append new ids."""
    by_id: dict[str, _RuleT] = {rule.rule_id: rule for rule in defaults}
    order = [rule.rule_id for rule in defaults]
    for rule in overlays:
        if rule.rule_id not in by_id:
            order.append(rule.rule_id)
        by_id[rule.rule_id] = rule
    return tuple(by_id[rule_id] for rule_id in order)


@dataclass(frozen=True)
class ScpiWritePolicy:
    """Compiled write-policy rules used by MCP write tools."""

    pattern_rules: tuple[_PatternRule, ...]
    value_rules: tuple[_ValueRule, ...]

    def evaluate(self, command: str, *, model: str) -> WriteGateResult:
        """Evaluate a SCPI write against this policy.

        Multi-statement commands (``;``-separated) are evaluated statement by
        statement; the most restrictive outcome wins
        (forbidden > needs_confirmation > allowed).
        """
        segments = [part.strip() for part in command.split(";") if part.strip()]
        if not segments:
            segments = [command]
        best = WriteGateResult(
            outcome="allowed",
            reason="",
            rule_id="",
            command=normalize_scpi_command(command),
            model=model,
        )
        for segment in segments:
            candidate = self._evaluate_segment(segment, model=model)
            if _OUTCOME_RANK[candidate.outcome] > _OUTCOME_RANK[best.outcome]:
                best = candidate
        return best

    def _evaluate_segment(self, command: str, *, model: str) -> WriteGateResult:
        """Evaluate a single SCPI statement (no ``;`` chaining)."""
        normalized = normalize_scpi_command(command)
        best = WriteGateResult(
            outcome="allowed",
            reason="",
            rule_id="",
            command=normalized,
            model=model,
        )

        for rule in self.pattern_rules:
            if not _model_matches(model, rule.model_substr):
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
            if not _model_matches(model, rule.model_substr):
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
        )

    @classmethod
    def defaults(
        cls,
        exclude_rule_ids: Collection[str] = (),
    ) -> ScpiWritePolicy:
        """Built-in policy (compiled pattern and value rules)."""
        policy = cls(pattern_rules=_PATTERN_RULES, value_rules=_VALUE_RULES)
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
        """
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        file_model = WriteRulesFile.model_validate(data)
        pattern_overlays = [
            _compile_pattern_spec(spec) for spec in file_model.pattern_rules
        ]
        value_overlays = [_compile_value_spec(spec) for spec in file_model.value_rules]
        base = cls.defaults()
        return cls(
            pattern_rules=_merge_by_rule_id(base.pattern_rules, pattern_overlays),
            value_rules=_merge_by_rule_id(base.value_rules, value_overlays),
        )


def evaluate_write(
    command: str,
    *,
    model: str,
    policy: ScpiWritePolicy | None = None,
) -> WriteGateResult:
    """Evaluate a SCPI write; ``policy=None`` uses :meth:`ScpiWritePolicy.defaults`."""
    return (policy or ScpiWritePolicy.defaults()).evaluate(command, model=model)
