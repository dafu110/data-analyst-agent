from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetProfile:
    path: Path
    rows: int
    columns: int
    column_names: list[str]
    dtypes: dict[str, str]
    missing_values: dict[str, int]
    numeric_summary: dict[str, dict[str, float]]
    categorical_summary: dict[str, dict[str, int]]
    warnings: list[str] = field(default_factory=list)
    quality_score: float = 1.0
    quality_dimensions: dict[str, float] = field(default_factory=dict)
    date_columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisStep:
    id: str
    title: str
    tool: str
    objective: str
    query: str | None = None
    code: str | None = None


@dataclass(frozen=True)
class AnalysisPlan:
    user_goal: str
    steps: list[AnalysisStep]


@dataclass(frozen=True)
class ToolResult:
    step_id: str
    title: str
    output: Any
    warning: str | None = None


@dataclass(frozen=True)
class ChartSpec:
    id: str
    title: str
    chart_type: str
    description: str
    data: list[dict[str, Any]]
    x: str
    y: str
    series: str | None = None


@dataclass(frozen=True)
class Insight:
    title: str
    detail: str
    severity: str = "info"
    insight_type: str = "finding"
    confidence: float = 0.75
    evidence: list[str] = field(default_factory=list)
    metric_value: str | None = None
    recommendation: str | None = None
    needs_review: bool = False


@dataclass(frozen=True)
class SemanticRole:
    role: str
    column: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class AnalysisIntent:
    intent: str
    label: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class TimeSeriesSummary:
    date_column: str
    metric_column: str
    periods: int
    first_period: str
    last_period: str
    first_value: float
    last_value: float
    absolute_change: float
    percent_change: float | None
    peak_period: str
    peak_value: float
    trough_period: str
    trough_value: float


@dataclass(frozen=True)
class TraceSpan:
    step_id: str
    label: str
    status: str
    started_at: str
    ended_at: str
    duration_ms: float
    tool: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class TableSummary:
    name: str
    rows: int
    columns: int
    column_names: list[str]


@dataclass(frozen=True)
class TableRelationship:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class ActionItem:
    priority: str
    title: str
    detail: str
    owner_hint: str = "业务负责人"
    evidence: list[str] = field(default_factory=list)
    next_step: str | None = None


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    formula: str
    columns: list[str]
    available: bool
    reason: str


@dataclass(frozen=True)
class AnalysisContext:
    business_scenario: str = "general"
    report_audience: str = "operator"
    analysis_depth: str = "standard"
    delivery_format: str = "business_report"


@dataclass(frozen=True)
class ExecutiveSummary:
    headline: str
    current_state: str
    key_takeaways: list[str]
    business_risks: list[str]
    recommended_focus: list[str]
    confidence: float


@dataclass(frozen=True)
class QualityGate:
    name: str
    status: str
    detail: str
    severity: str = "medium"


@dataclass(frozen=True)
class AgentResult:
    profile: DatasetProfile
    plan: AnalysisPlan
    tool_results: list[ToolResult]
    report_markdown: str
    chart_specs: list[ChartSpec] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    semantic_roles: list[SemanticRole] = field(default_factory=list)
    analysis_intent: AnalysisIntent | None = None
    time_series: list[TimeSeriesSummary] = field(default_factory=list)
    trace_spans: list[TraceSpan] = field(default_factory=list)
    table_summaries: list[TableSummary] = field(default_factory=list)
    table_relationships: list[TableRelationship] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    metric_definitions: list[MetricDefinition] = field(default_factory=list)
    analysis_context: AnalysisContext = field(default_factory=AnalysisContext)
    executive_summary: ExecutiveSummary | None = None
    quality_gates: list[QualityGate] = field(default_factory=list)
