from __future__ import annotations

import unittest
from pathlib import Path

from backend.authz import Principal, has_permission
from backend.metrics_exporter import metrics_to_prometheus
from backend.usage import build_account_usage, usage_summary_for_metrics
from data_analyst_agent.options import parse_analysis_options


class SaaSReadinessTests(unittest.TestCase):
    def test_account_usage_policy_reports_quota_cost_and_features(self) -> None:
        payload = build_account_usage(
            principal=Principal(actor="alice", role="analyst", organization="acme", workspace="finance"),
            metrics={
                "total_jobs": 12,
                "active_jobs": 1,
                "completed_jobs": 10,
                "failed_jobs": 1,
                "generated_reports": 9,
                "avg_duration_ms": 2500,
                "p95_duration_ms": 4100,
            },
            configured_max_active_jobs=3,
            configured_max_upload_bytes=50 * 1024 * 1024,
            plan_name="team",
        )

        self.assertEqual(payload["plan"], "team")
        self.assertEqual(payload["organization"], "acme")
        self.assertEqual(payload["workspace"], "finance")
        self.assertEqual(payload["quota"]["remaining_jobs"], 488)
        self.assertIn("dashboard_saved_views", payload["features"])
        self.assertGreater(payload["usage"]["estimated_cost_usd"], 0)

    def test_metrics_exporter_includes_cost_and_quota_gauges(self) -> None:
        metrics = {
            "total_jobs": 5,
            "active_jobs": 0,
            "completed_jobs": 5,
            "failed_jobs": 0,
            "generated_reports": 5,
            "avg_duration_ms": 100,
            "p95_duration_ms": 120,
            "by_status": {"completed": 5},
        }
        metrics.update(usage_summary_for_metrics(metrics, "business"))

        prometheus = metrics_to_prometheus(metrics)

        self.assertIn("data_analyst_agent_estimated_cost_usd", prometheus)
        self.assertIn("data_analyst_agent_quota_used_ratio", prometheus)

    def test_account_permission_and_new_report_templates_are_registered(self) -> None:
        self.assertTrue(has_permission(Principal(actor="viewer", role="viewer"), "account.read"))
        self.assertEqual(parse_analysis_options({"delivery_format": "client_brief"}).delivery_format, "client_brief")
        self.assertEqual(parse_analysis_options({"delivery_format": "department_brief"}).delivery_format, "department_brief")
        self.assertEqual(parse_analysis_options({"delivery_format": "ppt_brief"}).delivery_format, "ppt_brief")

    def test_release_gate_and_saas_doc_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]

        self.assertTrue((root / ".github" / "workflows" / "release.yml").exists())
        self.assertIn("GET /api/account", (root / "docs" / "SAAS_READINESS.zh-CN.md").read_text(encoding="utf-8"))

    def test_fastapi_account_endpoint_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        client = TestClient(fastapi_app.create_app())
        response = client.get(
            "/api/account",
            headers={
                "X-Actor": "saas-smoke",
                "X-Org": "acme",
                "X-Workspace": "finance",
                "X-Role": "analyst",
                "X-Plan": "team",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["plan"], "team")
        self.assertEqual(payload["organization"], "acme")
        self.assertEqual(payload["workspace"], "finance")


if __name__ == "__main__":
    unittest.main()
