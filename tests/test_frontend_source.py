from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendSourceTests(unittest.TestCase):
    def test_key_user_facing_files_are_utf8_chinese(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        state = (ROOT / "frontend" / "state.js").read_text(encoding="utf-8")

        self.assertIn("中文数据分析 Agent", readme)
        self.assertIn('lang="zh-CN"', index)
        self.assertIn("数据分析 Agent 工作台", index)
        self.assertIn('<script src="/state.js"></script>', index)
        self.assertIn("window.DataAnalystUI.elements", state)
        self.assertIn("window.DataAnalystUI.runtime", state)

    def test_high_risk_frontend_renderers_use_dom_nodes(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("followupAnswer.replaceChildren(article);", source)
        self.assertIn("previewTable.replaceChildren(table);", source)
        self.assertIn("qualityList.replaceChildren(", source)
        self.assertIn("toolResults.replaceChildren(", source)
        self.assertIn("jobTimeline.replaceChildren(", source)
        self.assertIn("jobList.replaceChildren(", source)
        self.assertIn("planApprovalSummary.replaceChildren(", source)
        self.assertIn("opsMetricGrid.replaceChildren(", source)
        self.assertIn("insightList.replaceChildren(", source)
        self.assertIn("actionList.replaceChildren(", source)
        self.assertIn("function createChip(value)", source)
        self.assertIn("function renderToolResultNode(result)", source)
        self.assertIn("function renderJobRowNode(job)", source)
        self.assertIn("function renderActionItemNode(item)", source)

    def test_field_role_selector_uses_compact_chinese_labels(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn('["", "不指定"]', source)
        self.assertIn('["revenue", "收入"]', source)
        self.assertNotIn('["", "unspecified"]', source)

    def test_result_mode_collapses_secondary_agent_details(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("agent-detail-disclosure", index)
        self.assertIn('removeAttribute("open")', source)
        self.assertIn(".has-result .agent-detail-disclosure:not([open]) .agent-transparency-panel", styles)

    def test_initial_state_hides_workbench_controls_until_dataset_exists(self) -> None:
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("body:not(.has-dataset):not(.has-result) .agent-command-bar", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .source-panel", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .preflight-panel", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .tabs", styles)

    def test_saas_usage_and_bi_controls_are_exposed(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        charts = (ROOT / "frontend" / "charts.js").read_text(encoding="utf-8")
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('id="accountUsageGrid"', index)
        self.assertIn('id="planName"', index)
        self.assertIn('value="department_brief"', index)
        self.assertIn('value="ppt_brief"', index)
        self.assertIn('apiFetch("/api/account")', app)
        self.assertIn('apiFetch("/api/alerts")', app)
        self.assertIn('createAccountUsageItem("估算成本"', app)
        self.assertIn("function renderAlerts", app)
        self.assertIn('id="alertList"', index)
        self.assertIn("DASHBOARD_STORAGE_KEY", charts)
        self.assertIn("saveDashboardView", charts)
        self.assertIn("applyChartEdit", charts)
        self.assertIn(".chart-editor-panel", styles)
        self.assertIn(".account-usage-grid", styles)
        self.assertIn(".alert-list", styles)


if __name__ == "__main__":
    unittest.main()
