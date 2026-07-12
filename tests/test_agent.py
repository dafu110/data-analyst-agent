from __future__ import annotations

from pathlib import Path
import os
import time
import unittest
from unittest.mock import patch

import pandas as pd

from data_analyst_agent.agent import DataAnalystAgent
from data_analyst_agent.executor import ToolRouter, run_guarded_python, run_sql
from data_analyst_agent.followup import answer_followup, suggest_followups
from data_analyst_agent.guardrails import GuardrailError
from data_analyst_agent.analysis_profile import detect_date_columns
from data_analyst_agent.profiler import profile_dataframe
from data_analyst_agent.guardrails import GuardrailPolicy
from data_analyst_agent.semantics import infer_semantic_roles
from data_analyst_agent.models import AnalysisPlan, AnalysisStep
from data_analyst_agent.options import parse_analysis_options
from data_analyst_agent.serialization import agent_result_to_dict


ROOT = Path(__file__).resolve().parents[1]


class DataAnalystAgentTests(unittest.TestCase):
    def test_agent_generates_report_for_csv(self) -> None:
        result = DataAnalystAgent().analyze_csv(ROOT / "examples" / "sales.csv", "找出销售模式。")

        self.assertEqual(result.profile.rows, 10)
        self.assertTrue(result.plan.steps)
        self.assertIn("数据分析智能体报告", result.report_markdown)
        self.assertIn("管理摘要", result.report_markdown)
        self.assertNotIn("NaN", result.report_markdown)
        self.assertTrue(result.chart_specs)
        self.assertTrue(result.insights)
        self.assertTrue(result.semantic_roles)
        self.assertIsNotNone(result.analysis_intent)
        self.assertGreater(result.profile.quality_score, 0)
        self.assertTrue(result.trace_spans)
        self.assertTrue(all(insight.evidence or insight.insight_type == "recommendation" for insight in result.insights))
        self.assertTrue(all(insight.source_step_ids for insight in result.insights))
        self.assertTrue(all(item.source_step_ids for item in result.action_items))
        self.assertTrue(all(0 <= insight.confidence <= 1 for insight in result.insights))
        self.assertIn("关键结论", result.report_markdown)
        self.assertIn("业务字段识别", result.report_markdown)
        self.assertIn("数据质量评分", result.report_markdown)
        self.assertIn("分析质量门禁", result.report_markdown)

    def test_small_dataset_analysis_stays_within_performance_budget(self) -> None:
        started = time.monotonic()
        result = DataAnalystAgent().analyze_csv(ROOT / "examples" / "sales.csv", "分析销售数据")
        duration = time.monotonic() - started

        self.assertEqual(result.profile.rows, 10)
        self.assertLess(duration, 10)

    def test_data_dictionary_overrides_semantic_roles(self) -> None:
        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "分析收入",
            data_dictionary={"revenue": "profit"},
        )

        role_map = {role.role: role.column for role in result.semantic_roles}
        self.assertEqual(role_map["profit"], "revenue")

    def test_month_string_columns_are_detected_as_dates(self) -> None:
        df = pd.DataFrame({"month": ["2026-01", "2026-02", "2026-03"], "mrr": [10, 20, 30]})

        self.assertIn("month", detect_date_columns(df))

    def test_mrr_is_treated_as_revenue_semantic_role(self) -> None:
        df = pd.DataFrame({"month": ["2026-01", "2026-02"], "mrr": [1000, 1200]})
        profile = profile_dataframe(df, "subscription.csv", GuardrailPolicy())
        roles = infer_semantic_roles(profile)

        self.assertIn(("revenue", "mrr"), {(role.role, role.column) for role in roles})

    def test_quality_score_counts_each_constant_column(self) -> None:
        df = pd.DataFrame(
            {
                "constant_a": ["same", "same", "same"],
                "constant_b": [1, 1, 1],
                "varying": [1, 2, 3],
            }
        )
        profile = profile_dataframe(df, "quality.csv", GuardrailPolicy())

        self.assertEqual(profile.quality_dimensions["variability"], 0.3333)

    def test_analysis_options_are_normalized_and_affect_report_shape(self) -> None:
        options = parse_analysis_options(
            {
                "business_scenario": "ecommerce",
                "report_audience": "executive",
                "analysis_depth": "quick",
                "delivery_format": "executive_brief",
            }
        )
        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "分析销售数据",
            analysis_options=options,
        )

        self.assertEqual(result.analysis_context.business_scenario, "ecommerce")
        self.assertEqual(result.analysis_context.report_audience, "executive")
        self.assertEqual(result.analysis_context.analysis_depth, "quick")
        self.assertEqual(result.analysis_context.delivery_format, "executive_brief")
        self.assertIn("管理摘要", result.report_markdown)
        self.assertNotIn("执行 Trace", result.report_markdown)
        self.assertNotIn("分析发现原始结果", result.report_markdown)

    def test_sales_analysis_returns_assignable_actions_without_claiming_automatic_execution(self) -> None:
        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "完成销售经营复盘，识别收入、订单和客单价变化，并给出本周优先动作。",
            business_scenario="sales",
        )

        self.assertEqual(result.analysis_context.business_scenario, "sales")
        self.assertTrue(result.action_items)
        self.assertTrue(all(item.owner_hint for item in result.action_items))
        self.assertTrue(all(item.expected_impact for item in result.action_items))
        self.assertTrue(all(item.deadline_hint for item in result.action_items))
        self.assertIn("建议负责人：", result.report_markdown)
        self.assertIn("预期影响：", result.report_markdown)
        self.assertNotIn("自动执行", result.report_markdown)

    def test_deep_report_includes_trace_and_raw_results(self) -> None:
        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "分析销售数据",
            analysis_depth="deep",
            delivery_format="business_report",
        )

        self.assertIn("执行 Trace", result.report_markdown)
        self.assertIn("分析发现原始结果", result.report_markdown)

    def test_followup_answer_is_grounded_in_result(self) -> None:
        result = DataAnalystAgent().analyze_csv(ROOT / "examples" / "sales.csv", "分析销售数据")
        payload = agent_result_to_dict(result)

        answer = answer_followup(payload, result.report_markdown, "数据质量有什么风险？")

        self.assertIn("answer", answer)
        self.assertIn("数据质量", answer["answer"])
        self.assertTrue(answer["citations"])
        self.assertGreaterEqual(answer["confidence"], 0.5)
        self.assertTrue(suggest_followups(payload))

    def test_python_guardrails_block_imports(self) -> None:
        with self.assertRaises(GuardrailError):
            run_guarded_python(pd.DataFrame(), "import os\nresult = 1")

    def test_tool_result_records_local_guardrail_evidence(self) -> None:
        router = ToolRouter()
        result = router.run_step(
            pd.DataFrame({"revenue": [10, 20]}),
            AnalysisStep(id="sum", title="Revenue sum", tool="python", objective="Sum revenue", code="result = int(df['revenue'].sum())"),
        )

        self.assertEqual(result.output, 30)
        self.assertEqual(result.safety["executor"], "guarded_python")
        self.assertTrue(result.safety["ast_validated"])

        report = DataAnalystAgent().analyze_csv(ROOT / "examples" / "sales.csv", "分析销售趋势").report_markdown
        self.assertIn("安全执行证据", report)
        self.assertIn("计算步骤：", report)

    def test_docker_execution_branch_records_isolation_evidence(self) -> None:
        router = ToolRouter()
        step = AnalysisStep(id="sum", title="Revenue sum", tool="python", objective="Sum revenue", code="result = 30")
        with patch.dict(os.environ, {"DATA_ANALYST_AGENT_EXECUTOR_MODE": "docker"}):
            with patch("data_analyst_agent.executor.run_python_in_docker", return_value=30):
                result = router.run_step(pd.DataFrame({"revenue": [10, 20]}), step)

        self.assertEqual(result.safety["executor"], "docker_sandbox")
        self.assertEqual(result.safety["network"], "disabled")
        self.assertIn("read-only", result.safety["filesystem"])

    def test_report_includes_preflight_input_safety_findings(self) -> None:
        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "分析销售趋势",
            input_security_findings=[{"kind": "spreadsheet_formula", "detail": "检测到公式前缀。"}],
        )

        self.assertIn("输入预检：spreadsheet_formula", result.report_markdown)

    def test_python_guardrails_block_dunder_subscript_escape(self) -> None:
        with self.assertRaises(GuardrailError):
            run_guarded_python(pd.DataFrame(), "result = (1).__getattribute__('__class__')")

        with self.assertRaises(GuardrailError):
            run_guarded_python(pd.DataFrame(), "result = globals()['__builtins__']")

    def test_sql_allows_select_only(self) -> None:
        df = pd.DataFrame({"region": ["North", "South"], "revenue": [10, 20]})

        self.assertEqual(
            run_sql(df, "select region, revenue from data order by revenue desc limit 1"),
            [{"region": "South", "revenue": 20}],
        )

        with self.assertRaises(ValueError):
            run_sql(df, "delete from data")

        with self.assertRaises(ValueError):
            run_sql(df, "select region from data; select revenue from data")

        with self.assertRaises(ValueError):
            run_sql(df, "select region from data -- hidden operation")

    def test_agent_stops_when_cancelled_before_work(self) -> None:
        with self.assertRaises(TimeoutError):
            DataAnalystAgent().analyze_csv(
                ROOT / "examples" / "sales.csv",
                "分析销售数据",
                is_cancelled=lambda: True,
            )

    def test_agent_adds_fixed_fallback_when_approved_plan_has_no_output(self) -> None:
        plan = AnalysisPlan(
            user_goal="分析销售数据",
            steps=[
                AnalysisStep(
                    id="empty-approved-step",
                    title="Empty output",
                    tool="python",
                    objective="Exercise execution verification.",
                    code="result = {}",
                )
            ],
        )

        result = DataAnalystAgent().analyze_csv(
            ROOT / "examples" / "sales.csv",
            "分析销售数据",
            approved_plan=plan,
        )

        self.assertEqual(result.execution_review["status"], "supplemented")
        self.assertEqual(result.execution_review["supplemental_steps"][0]["step_id"], "verification-fallback")
        self.assertEqual(result.tool_results[-1].step_id, "verification-fallback")

    def test_tool_router_checks_cancellation_before_steps(self) -> None:
        router = ToolRouter(is_cancelled=lambda: True)
        plan = AnalysisPlan(
            user_goal="分析销售数据",
            steps=[
                AnalysisStep(
                    id="shape",
                    title="数据规模",
                    tool="python",
                    objective="统计行列数",
                    code="result = {'rows': len(df)}",
                )
            ],
        )

        with self.assertRaises(TimeoutError):
            router.run_plan(pd.DataFrame({"a": [1]}), plan)


if __name__ == "__main__":
    unittest.main()
