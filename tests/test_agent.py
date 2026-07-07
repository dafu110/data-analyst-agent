from __future__ import annotations

from pathlib import Path
import time
import unittest

import pandas as pd

from data_analyst_agent.agent import DataAnalystAgent
from data_analyst_agent.executor import ToolRouter, run_guarded_python, run_sql
from data_analyst_agent.followup import answer_followup, suggest_followups
from data_analyst_agent.guardrails import GuardrailError
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

    def test_sql_allows_select_only(self) -> None:
        df = pd.DataFrame({"region": ["North", "South"], "revenue": [10, 20]})

        self.assertEqual(
            run_sql(df, "select region, revenue from data order by revenue desc limit 1"),
            [{"region": "South", "revenue": 20}],
        )

        with self.assertRaises(ValueError):
            run_sql(df, "delete from data")

    def test_agent_stops_when_cancelled_before_work(self) -> None:
        with self.assertRaises(TimeoutError):
            DataAnalystAgent().analyze_csv(
                ROOT / "examples" / "sales.csv",
                "分析销售数据",
                is_cancelled=lambda: True,
            )

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
