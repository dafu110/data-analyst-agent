from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendSourceTests(unittest.TestCase):
    def test_key_user_facing_files_are_utf8_chinese(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (ROOT / "docs" / "QUICKSTART.zh-CN.md").read_text(encoding="utf-8")
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        state = (ROOT / "frontend" / "state.js").read_text(encoding="utf-8")

        self.assertIn("中文数据分析 Agent", readme)
        self.assertIn("快速使用指南", quickstart)
        self.assertNotIn("涓", quickstart)
        self.assertIn('lang="zh-CN"', index)
        self.assertIn("数据分析 Agent 工作台", index)
        self.assertIn('<script src="/state.js"></script>', index)
        self.assertIn("window.DataAnalystUI.elements", state)
        self.assertIn("window.DataAnalystUI.runtime", state)
        self.assertIn('<script src="/labels.js"></script>', index)

    def test_github_portfolio_docs_are_linked_from_readme(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        api_doc = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("actions/workflows/ci.yml/badge.svg", readme)
        self.assertIn("docs/API.md", readme)
        self.assertIn("CHANGELOG.md", readme)
        self.assertIn("# API Surface", api_doc)
        self.assertIn("POST /api/analyze", api_doc)
        self.assertIn("GET /api/reports/{job_id}", api_doc)
        self.assertIn("## [0.2.0] - 2026-07-09", changelog)

    def test_frontend_labels_are_split_from_main_app_file(self) -> None:
        labels = (ROOT / "frontend" / "labels.js").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("window.DataAnalystUI.labels", labels)
        self.assertIn("agentCommandStates", labels)
        self.assertIn("statusLabels", labels)
        self.assertIn("const {", app)
        self.assertIn("} = window.DataAnalystUI.labels;", app)
        self.assertNotIn("const statusLabels = {", app)

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

    def test_csv_preview_supports_utf8_and_gb18030(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function decodeCsvPreview(buffer)", source)
        self.assertIn('new TextDecoder("utf-8", { fatal: true })', source)
        self.assertIn('new TextDecoder("gb18030")', source)
        self.assertIn("reader.readAsArrayBuffer(file.slice(0, 512 * 1024))", source)

    def test_result_cards_link_back_to_execution_trace(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function appendTraceLinks(parent, stepIds)", source)
        self.assertIn('activateTab("trace")', source)
        self.assertIn("insight.source_step_ids", source)

    def test_preflight_ui_ignores_stale_requests_and_binds_approved_contract(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        state = (ROOT / "frontend" / "state.js").read_text(encoding="utf-8")

        self.assertIn("preflightRequestId", source)
        self.assertIn("requestId !== runtime.preflightRequestId", source)
        self.assertIn("planInputVersion !== runtime.planInputVersion", source)
        self.assertIn('payload.set("preflight_contract", runtime.approvedPlan.execution_contract)', source)
        self.assertIn("function invalidateApprovedPlan()", source)
        self.assertIn("preflightLoading", state)

    def test_navigation_separates_workflow_analysis_and_management_layers(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn('class="advanced-tabs analysis-tabs"', index)
        self.assertIn('class="advanced-tabs management-tabs"', index)
        self.assertIn('class="settings-disclosure access-disclosure management-disclosure"', index)
        self.assertIn('activeTab?.closest("details")?.setAttribute("open", "")', source)

    def test_sales_workspace_shows_assignable_actions(self) -> None:
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

        self.assertIn('businessScenario.value = "sales"', source)
        self.assertIn("className = \"action-assignment\"", source)
        self.assertIn("负责人：${item.owner_hint", source)
        self.assertIn("预期：${item.expected_impact", source)
        self.assertIn('name="goal" rows="5" placeholder=', index)
        self.assertIn('data-goal-template=', index)
        self.assertIn('value="manager" selected', index)
        self.assertIn('value="quick" selected', index)

    def test_safety_evidence_is_visible_in_the_result_workspace(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="executionSafetyBlock"', index)
        self.assertIn("function renderExecutionSafety(data)", source)
        self.assertIn("data.preflight_contract?.security_findings", source)

    def test_result_mode_collapses_secondary_agent_details(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("agent-detail-disclosure", index)
        self.assertIn('removeAttribute("open")', source)
        self.assertIn(".has-result .agent-detail-disclosure:not([open]) .agent-transparency-panel", styles)

    def test_default_workflow_keeps_plan_approval_and_evidence_on_demand(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        source = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('class="overview-evidence-disclosure"', index)
        self.assertIn('planApprovalBlock?.classList.remove("hidden")', source)
        self.assertIn('activateTab("overview")', source)
        self.assertIn(".has-dataset:not(.has-result) .dictionary-disclosure:not([open])", styles)

    def test_initial_state_hides_workbench_controls_until_dataset_exists(self) -> None:
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("body:not(.has-dataset):not(.has-result) .agent-command-bar", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .source-panel", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .preflight-panel", styles)
        self.assertIn("body:not(.has-dataset):not(.has-result) .tabs", styles)

    def test_empty_state_prioritizes_upload_and_disables_plan_until_a_dataset_exists(self) -> None:
        index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
        styles = (ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

        self.assertIn('aria-describedby="planActionHint"', index)
        self.assertIn('id="emptyUseExampleData"', index)
        self.assertIn('setStatus("idle", "等待上传")', app)
        self.assertIn("function updatePlanActionAvailability()", app)
        self.assertIn("submitButton.disabled = !hasDataset || isBusy", app)
        self.assertIn("align-content: start", styles)

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
