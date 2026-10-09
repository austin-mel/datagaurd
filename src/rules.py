import re
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class ConfigurationError(ValueError):
    """Invalid administrator-supplied rules; fail startup instead of passing data."""


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class BaseRule(ConfigModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    column: str = Field(min_length=1)
    severity: Literal["error", "warning"] = "error"
    explanation: str = Field(min_length=1)


class RequiredRule(BaseRule):
    kind: Literal["required"]


class UniqueRule(BaseRule):
    kind: Literal["unique"]


class PatternRule(BaseRule):
    kind: Literal["pattern"]
    pattern: str = Field(min_length=1, max_length=200)

    @field_validator("pattern")
    @classmethod
    def valid_pattern(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError("pattern must be a valid regular expression") from exc
        return value


class AllowedRule(BaseRule):
    kind: Literal["allowed_values"]
    values: list[str] = Field(min_length=1)

    @field_validator("values")
    @classmethod
    def valid_values(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values) or any(not value.strip() for value in values):
            raise ValueError("allowed values must be unique and nonblank")
        return values


class NumericRule(BaseRule):
    kind: Literal["numeric"]


class RangeRule(BaseRule):
    kind: Literal["range"]
    minimum: float
    maximum: float
    prerequisite: str

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        return self


DateFormat = Literal["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]


class DateRule(BaseRule):
    kind: Literal["date"]
    formats: list[DateFormat] = Field(min_length=1)

    @field_validator("formats")
    @classmethod
    def unique_formats(cls, formats: list[DateFormat]) -> list[DateFormat]:
        if len(set(formats)) != len(formats):
            raise ValueError("date formats must be unique")
        return formats


class NotFutureRule(BaseRule):
    kind: Literal["not_future"]
    latest: Literal["today"] = "today"
    prerequisite: str


Rule = Annotated[
    RequiredRule | UniqueRule | PatternRule | AllowedRule | NumericRule | RangeRule | DateRule | NotFutureRule,
    Field(discriminator="kind"),
]


class StatisticalSettings(ConfigModel):
    statistical_min_samples: int = Field(default=20, ge=1)
    iqr_multiplier: float = Field(default=1.5, ge=0)
    missingness_increase_percentage_points: float = Field(default=5, ge=0, le=100)
    row_count_change_percentage: float = Field(default=20, ge=0)
    category_share_change_percentage_points: float = Field(default=10, ge=0, le=100)


class RuleSet(ConfigModel):
    schema_version: Literal[1]
    name: str = Field(min_length=1)
    structural_rule_id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    required_columns: list[str]
    rules: list[Rule]
    identifier_column: str | None = None
    identifier_policy: Literal["configured", "auto"] = "configured"
    statistics: StatisticalSettings | None = None

    @model_validator(mode="after")
    def coherent_rules(self) -> Self:
        if not self.name.strip():
            raise ValueError("name must be nonblank")
        if self.identifier_policy == "configured" and (not self.required_columns or not self.rules):
            raise ValueError("configured rule sets require columns and rules")
        if self.identifier_policy == "auto" and {self.structural_rule_id, *(rule.id for rule in self.rules)} & {
            "GENERIC_ID_REQUIRED", "GENERIC_ID_UNIQUE"
        }:
            raise ValueError("GENERIC_ID_REQUIRED and GENERIC_ID_UNIQUE are reserved for automatic identifier checks")
        if self.identifier_column is not None and self.identifier_column not in self.required_columns:
            raise ValueError("identifier_column must be declared in required_columns")
        if len(set(self.required_columns)) != len(self.required_columns) or any(
            not column.strip() for column in self.required_columns
        ):
            raise ValueError("required_columns must be unique and nonblank")
        seen: dict[str, Rule] = {}
        for rule in self.rules:
            if rule.id in seen or rule.id == self.structural_rule_id:
                raise ValueError(f"duplicate rule ID: {rule.id}")
            if rule.column not in self.required_columns:
                raise ValueError(f"{rule.id}: rule column must be declared in required_columns")
            if isinstance(rule, (RangeRule, NotFutureRule)):
                parent = seen.get(rule.prerequisite)
                expected_type = NumericRule if isinstance(rule, RangeRule) else DateRule
                if not isinstance(parent, expected_type) or parent.column != rule.column:
                    raise ValueError(f"{rule.id}: prerequisite must be an earlier parsing rule on the same column")
            seen[rule.id] = rule
        return self


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate YAML keys instead of silently overwriting rules."""

    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[object, object]:
        if not isinstance(node, yaml.MappingNode):
            raise ConfigurationError("Expected a YAML mapping")
        self.flatten_mapping(node)
        mapping: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in mapping:
                    raise ConfigurationError(f"Duplicate YAML key: {key}")
                mapping[key] = self.construct_object(value_node, deep=deep)
            except TypeError as exc:
                raise ConfigurationError("YAML mapping keys must be scalar values") from exc
        return mapping


def load_rules(path: Path) -> RuleSet:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        return RuleSet.model_validate(document)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, ConfigurationError) as exc:
        raise ConfigurationError(f"Invalid rule configuration at {path}: {exc}") from exc

