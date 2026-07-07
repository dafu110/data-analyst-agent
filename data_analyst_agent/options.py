from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping


SCENARIO_CHOICES = {
    "general",
    "sales",
    "content",
    "ecommerce",
    "finance",
    "customer",
    "marketing",
}
AUDIENCE_CHOICES = {"operator", "manager", "executive", "client"}
DEPTH_CHOICES = {"quick", "standard", "deep"}
DELIVERY_CHOICES = {"business_report", "executive_brief", "diagnostic"}


@dataclass(frozen=True)
class AnalysisOptions:
    business_scenario: str = "general"
    report_audience: str = "operator"
    analysis_depth: str = "standard"
    delivery_format: str = "business_report"

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None, *, inferred_scenario: str = "general") -> "AnalysisOptions":
        values = values or {}
        return cls(
            business_scenario=normalize_choice(values.get("business_scenario"), SCENARIO_CHOICES, inferred_scenario),
            report_audience=normalize_choice(values.get("report_audience"), AUDIENCE_CHOICES, "operator"),
            analysis_depth=normalize_choice(values.get("analysis_depth"), DEPTH_CHOICES, "standard"),
            delivery_format=normalize_choice(values.get("delivery_format"), DELIVERY_CHOICES, "business_report"),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def agent_kwargs(self) -> dict[str, str]:
        return self.to_dict()


def normalize_choice(value: object, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else default


def parse_analysis_options(values: Mapping[str, object] | None, *, inferred_scenario: str = "general") -> AnalysisOptions:
    return AnalysisOptions.from_mapping(values, inferred_scenario=inferred_scenario)
