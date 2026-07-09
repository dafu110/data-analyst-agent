from __future__ import annotations

from dataclasses import replace
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

from backend.config import AppConfig
from backend.job_store import JobRecord, utc_now
from backend.authz import Principal, can_access_job_scope, has_permission, token_is_valid
from backend.rate_limiter import InMemoryRateLimiter
from backend.server import CONFIG, DataAnalystRequestHandler, markdown_to_html, parse_data_dictionary, result_to_csv_summary
from backend.exporters import markdown_to_pdf
import backend.pdf_exporter as pdf_exporter
from backend.pdf_exporter import normalize_markdown_line
from backend.production_check import check_python_dependency_versions, version_in_range
from data_analyst_agent.llm_provider import extract_response_text


class SecurityControlTests(unittest.TestCase):
    def test_markdown_html_export_escapes_script(self) -> None:
        rendered = markdown_to_html("# Report\n<script>alert(1)</script>")

        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>alert", rendered)

    def test_pdf_export_embeds_chinese_font(self) -> None:
        pdf = markdown_to_pdf("# 数据分析报告\n\n- 中文内容不会乱码")

        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"ToUnicode", pdf)
        self.assertTrue(
            any(marker in pdf.lower() for marker in (b"simhei", b"noto", b"wqy", b"wenquanyi", b"dataanalyst")),
            "PDF should embed a configured Chinese-capable font.",
        )
        self.assertEqual(normalize_markdown_line("- **收入** `revenue`"), "- 收入 revenue")

    def test_pdf_font_registration_skips_unsupported_candidates(self) -> None:
        registered: list[str] = []

        class FakeMetrics:
            @staticmethod
            def getRegisteredFontNames() -> list[str]:
                return []

            @staticmethod
            def registerFont(font) -> None:
                registered.append(font.path)

        class FakeTTFont:
            def __init__(self, name: str, path: str) -> None:
                self.name = name
                self.path = path
                if path.endswith("bad.ttc"):
                    raise RuntimeError("unsupported font")

        def exists_only_for_candidates(self) -> bool:
            return self.name in {"bad.ttc", "good.ttf"}

        with patch.object(pdf_exporter, "CHINESE_FONT_CANDIDATES", ["bad.ttc", "good.ttf"]):
            with patch.object(pdf_exporter.Path, "exists", exists_only_for_candidates):
                font_path = pdf_exporter.register_chinese_font(FakeMetrics, FakeTTFont)

        self.assertEqual(str(font_path), "good.ttf")
        self.assertEqual(registered, ["good.ttf"])

    def test_openai_response_text_extraction(self) -> None:
        text = extract_response_text({"output": [{"content": [{"type": "output_text", "text": "{\"steps\": []}"}]}]})

        self.assertEqual(text, "{\"steps\": []}")

    def test_production_dependency_version_helper(self) -> None:
        self.assertTrue(version_in_range("5.26.1", "5.26.1", "6.0.0"))
        self.assertTrue(version_in_range("5.29.4", "5.26.1", "6.0.0"))
        self.assertFalse(version_in_range("3.20.3", "5.26.1", "6.0.0"))
        self.assertIn(check_python_dependency_versions().status, {"ok", "failed", "skipped"})

    def test_config_type_available(self) -> None:
        self.assertTrue(AppConfig.__annotations__)

    def test_job_access_is_owner_or_admin_scoped(self) -> None:
        now = utc_now()
        job = JobRecord(
            id="job-1",
            filename="sales.csv",
            goal="Find patterns",
            status="completed",
            created_at=now,
            updated_at=now,
            owner="alice",
        )

        class FakeHandler:
            def __init__(self, actor: str, organization: str = "default") -> None:
                self._actor = actor
                self._organization = organization

            def actor(self) -> str:
                return self._actor

            def organization(self) -> str:
                return self._organization

            def workspace(self) -> str:
                return "default"

            def is_admin_actor(self) -> bool:
                return self._actor in CONFIG.admin_actors

        alice_handler = FakeHandler("alice")
        bob_handler = FakeHandler("bob")
        admin_handler = FakeHandler(next(iter(CONFIG.admin_actors)))

        self.assertTrue(DataAnalystRequestHandler.can_access_job(alice_handler, job))
        self.assertFalse(DataAnalystRequestHandler.can_access_job(bob_handler, job))
        self.assertFalse(DataAnalystRequestHandler.can_access_job(FakeHandler("alice", "other-org"), job))
        self.assertTrue(DataAnalystRequestHandler.can_access_job(admin_handler, job))

    def test_rbac_permissions(self) -> None:
        self.assertTrue(has_permission(Principal("alice", "analyst"), "job.create"))
        self.assertFalse(has_permission(Principal("alice", "viewer"), "job.create"))
        self.assertFalse(has_permission(Principal("alice", "admin"), "audit.read"))
        self.assertTrue(has_permission(Principal("root", "viewer", is_admin_actor=True), "audit.read"))

    def test_api_token_and_rate_limiter_controls(self) -> None:
        self.assertTrue(token_is_valid(None, None))
        self.assertTrue(token_is_valid("secret", None, "Bearer secret"))
        self.assertFalse(token_is_valid("secret", "wrong"))

        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60)
        self.assertTrue(limiter.allow("alice"))
        self.assertTrue(limiter.allow("alice"))
        self.assertFalse(limiter.allow("alice"))

    def test_workspace_is_part_of_job_access_scope(self) -> None:
        now = utc_now()
        job = JobRecord(
            id="job-1",
            filename="sales.csv",
            goal="Find patterns",
            status="completed",
            created_at=now,
            updated_at=now,
            owner="alice",
            organization="acme",
            workspace="finance",
        )

        self.assertTrue(can_access_job_scope(Principal("alice", "analyst", organization="acme", workspace="finance"), job))
        self.assertFalse(can_access_job_scope(Principal("alice", "analyst", organization="acme", workspace="ops"), job))
        self.assertTrue(can_access_job_scope(Principal("admin", "viewer", is_admin_actor=True), job))

    def test_data_dictionary_parser_and_csv_summary(self) -> None:
        self.assertEqual(parse_data_dictionary('{"收入":"revenue"}'), {"收入": "revenue"})
        csv_text = result_to_csv_summary(
            {
                "insights": [
                    {
                        "title": "收入增长",
                        "insight_type": "finding",
                        "severity": "success",
                        "confidence": 0.9,
                        "metric_value": "10%",
                        "detail": "收入增长。",
                        "recommendation": "继续跟踪。",
                        "needs_review": False,
                    }
                ]
            }
        )
        self.assertIn("收入增长", csv_text)
        self.assertIn("confidence", csv_text)

    def test_fastapi_security_helpers_when_available(self) -> None:
        try:
            import backend.fastapi_app as fastapi_app
        except RuntimeError:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        with patch.object(fastapi_app, "CONFIG", replace(fastapi_app.CONFIG, api_token="secret")):
            with self.assertRaises(fastapi_app.HTTPException):
                fastapi_app.current_principal(x_actor="alice", x_api_token="wrong")
            with self.assertRaises(fastapi_app.HTTPException):
                fastapi_app.current_principal(x_actor="../alice", x_api_token="secret")
            principal = fastapi_app.current_principal(x_actor="alice", x_org="acme", x_workspace="finance", x_api_token="secret")

        self.assertEqual(principal.workspace, "finance")
        self.assertEqual(fastapi_app.resolve_workspace(principal, None), "finance")
        with self.assertRaises(fastapi_app.HTTPException):
            fastapi_app.resolve_workspace(principal, "ops")
        with self.assertRaises(fastapi_app.HTTPException):
            fastapi_app.parse_data_dictionary("{bad json")

    def test_fastapi_openapi_has_typed_job_schema_when_available(self) -> None:
        try:
            import backend.fastapi_app as fastapi_app
            from fastapi.testclient import TestClient
        except RuntimeError:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        schema = fastapi_app.create_app().openapi()
        schemas = schema.get("components", {}).get("schemas", {})
        self.assertIn("JobResponse", schemas)
        self.assertIn("MetricsResponse", schemas)

        response = TestClient(fastapi_app.create_app()).get("/api/health")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

        metrics_response = TestClient(fastapi_app.create_app()).get(
            "/api/metrics.prometheus",
            headers={"X-Actor": "metrics", "X-Role": "analyst"},
        )
        self.assertEqual(metrics_response.status_code, 200)
        self.assertIn("data_analyst_agent_jobs_total", metrics_response.text)

    def test_fastapi_report_paths_must_stay_inside_report_dir_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except RuntimeError:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        now = utc_now()
        outside_report = Path(fastapi_app.CONFIG.report_dir).resolve().parent / f"{Path(fastapi_app.CONFIG.report_dir).name}-outside.md"
        job = JobRecord(
            id="report-path-test",
            filename="sales.csv",
            goal="test",
            status="completed",
            created_at=now,
            updated_at=now,
            owner="alice",
            report_path=str(outside_report),
            result={},
        )

        outside_report.write_text("# outside", encoding="utf-8")
        try:
            with patch.object(fastapi_app.JOB_STORE, "get", return_value=job):
                response = TestClient(fastapi_app.create_app()).get(
                    "/api/reports/report-path-test",
                    headers={"X-Actor": "alice", "X-Role": "analyst"},
                )
        finally:
            outside_report.unlink(missing_ok=True)

        self.assertEqual(response.status_code, 404)

    def test_fastapi_report_format_is_an_explicit_contract_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except RuntimeError:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        response = TestClient(fastapi_app.create_app()).get(
            "/api/reports/missing-job?format=zip",
            headers={"X-Actor": "alice", "X-Role": "analyst"},
        )

        self.assertEqual(response.status_code, 422)

    def test_stdlib_server_adds_security_headers(self) -> None:
        handler = object.__new__(DataAnalystRequestHandler)
        handler._headers_buffer = []
        handler.request_version = "HTTP/1.1"
        handler.flush_headers = Mock()

        DataAnalystRequestHandler.end_headers(handler)

        rendered_headers = b"".join(handler._headers_buffer).decode("latin-1")
        self.assertIn("X-Content-Type-Options: nosniff", rendered_headers)
        self.assertIn("X-Frame-Options: DENY", rendered_headers)
        self.assertIn("frame-ancestors 'none'", rendered_headers)

    def test_unknown_post_api_returns_json_error(self) -> None:
        handler = object.__new__(DataAnalystRequestHandler)
        handler.path = "/api/unknown"
        handler.send_json = Mock()

        DataAnalystRequestHandler.do_POST(handler)

        handler.send_json.assert_called_once()
        payload = handler.send_json.call_args.args[0]
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
