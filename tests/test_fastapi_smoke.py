from __future__ import annotations

import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


class FastApiSmokeTests(unittest.TestCase):
    def test_fastapi_upload_job_and_report_exports_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        client = TestClient(fastapi_app.create_app())
        dataset_path = Path(__file__).resolve().parents[1] / "examples" / "sales.csv"
        with dataset_path.open("rb") as handle:
            response = client.post(
                "/api/analyze",
                files={"dataset": ("sales.csv", handle, "text/csv")},
                data={"goal": "生成经营分析报告"},
                headers={"X-Actor": "smoke", "X-Org": "default", "X-Workspace": "default", "X-Role": "analyst"},
            )

        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["id"]

        job_payload = {}
        for _ in range(80):
            job_response = client.get(
                f"/api/jobs/{job_id}",
                headers={"X-Actor": "smoke", "X-Org": "default", "X-Workspace": "default", "X-Role": "analyst"},
            )
            self.assertEqual(job_response.status_code, 200, job_response.text)
            job_payload = job_response.json()
            if job_payload["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.1)

        self.assertEqual(job_payload.get("status"), "completed", job_payload.get("error"))
        self.assertGreaterEqual(len(job_payload["result"].get("chart_specs", [])), 4)
        self.assertIn("report_markdown", job_payload["result"])

        expected_exports = {
            "md": ("text/markdown", b"#"),
            "html": ("text/html", b"<!doctype html>"),
            "csv": ("text/csv", b"title,type"),
            "pdf": ("application/pdf", b"%PDF"),
            "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", b"PK"),
        }
        for export_format, (expected_content_type, expected_prefix) in expected_exports.items():
            export_response = client.get(
                f"/api/reports/{job_id}?format={export_format}",
                headers={"X-Actor": "smoke", "X-Org": "default", "X-Workspace": "default", "X-Role": "analyst"},
            )
            self.assertEqual(export_response.status_code, 200, export_response.text[:200])
            self.assertIn(expected_content_type, export_response.headers["content-type"])
            self.assertTrue(export_response.content.startswith(expected_prefix))
            self.assertGreater(len(export_response.content), 100)

    def test_fastapi_rejects_oversized_upload_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        with patch.object(fastapi_app, "CONFIG", replace(fastapi_app.CONFIG, max_upload_bytes=8)):
            client = TestClient(fastapi_app.create_app())
            response = client.post(
                "/api/analyze",
                files={"dataset": ("large.csv", b"col\n" + b"1\n" * 10, "text/csv")},
                data={"goal": "测试大文件限制"},
                headers={"X-Actor": "large-file", "X-Role": "analyst"},
            )

        self.assertEqual(response.status_code, 413, response.text)

    def test_fastapi_preflight_plan_and_execution_contract_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        client = TestClient(fastapi_app.create_app())
        headers = {"X-Actor": "preflight", "X-Org": "default", "X-Workspace": "default", "X-Role": "analyst"}
        source = Path(__file__).resolve().parents[1] / "examples" / "sales.csv"
        content = source.read_bytes()
        preflight_response = client.post("/api/preflights", files={"dataset": ("sales.csv", content, "text/csv")}, headers=headers)
        self.assertEqual(preflight_response.status_code, 201, preflight_response.text)
        preflight = preflight_response.json()
        self.assertEqual(preflight["profile"]["rows"], 10)

        plan_response = client.post(
            f"/api/preflights/{preflight['id']}/plans",
            json={
                "goal": "分析销售趋势",
                "data_dictionary": {"revenue": "revenue"},
                "business_scenario": "sales",
                "report_audience": "manager",
                "analysis_depth": "quick",
                "delivery_format": "business_report",
            },
            headers=headers,
        )
        self.assertEqual(plan_response.status_code, 201, plan_response.text)
        plan = plan_response.json()
        self.assertTrue(plan["plan"]["steps"])
        self.assertTrue(plan["execution_contract"])

        mismatch = client.post(
            "/api/analyze",
            files={"dataset": ("sales.csv", b"region,revenue\nNorth,999\n", "text/csv")},
            data={
                "goal": "分析销售趋势",
                "preflight_id": preflight["id"],
                "plan_id": plan["id"],
                "preflight_fingerprint": preflight["fingerprint"],
                "preflight_contract": plan["execution_contract"],
                "data_dictionary": '{"revenue":"revenue"}',
            },
            headers=headers,
        )
        self.assertEqual(mismatch.status_code, 409, mismatch.text)

        accepted = client.post(
            "/api/analyze",
            files={"dataset": ("sales.csv", content, "text/csv")},
            data={
                "goal": plan["plan"]["user_goal"],
                "preflight_id": preflight["id"],
                "plan_id": plan["id"],
                "preflight_fingerprint": preflight["fingerprint"],
                "preflight_contract": plan["execution_contract"],
                "data_dictionary": '{"revenue":"revenue"}',
            },
            headers=headers,
        )
        self.assertEqual(accepted.status_code, 202, accepted.text)

        changed_options = client.post(
            "/api/analyze",
            files={"dataset": ("sales.csv", content, "text/csv")},
            data={
                "goal": plan["plan"]["user_goal"],
                "preflight_id": preflight["id"],
                "plan_id": plan["id"],
                "preflight_fingerprint": preflight["fingerprint"],
                "preflight_contract": plan["execution_contract"],
                "data_dictionary": '{"revenue":"profit"}',
                "analysis_depth": "deep",
            },
            headers=headers,
        )
        self.assertEqual(changed_options.status_code, 409, changed_options.text)

        changed_depth = client.post(
            "/api/analyze",
            files={"dataset": ("sales.csv", content, "text/csv")},
            data={
                "goal": plan["plan"]["user_goal"],
                "preflight_id": preflight["id"],
                "plan_id": plan["id"],
                "preflight_fingerprint": preflight["fingerprint"],
                "preflight_contract": plan["execution_contract"],
                "data_dictionary": '{"revenue":"revenue"}',
                "analysis_depth": "deep",
            },
            headers=headers,
        )
        self.assertEqual(changed_depth.status_code, 409, changed_depth.text)

    def test_fastapi_rejects_unsupported_file_without_creating_job_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        client = TestClient(fastapi_app.create_app())
        response = client.post(
            "/api/analyze",
            files={"dataset": ("notes.txt", b"not a dataset", "text/plain")},
            data={"goal": "测试错误文件"},
            headers={"X-Actor": "bad-file", "X-Role": "analyst"},
        )

        self.assertEqual(response.status_code, 400, response.text)

    def test_fastapi_rejects_actor_active_job_quota_when_available(self) -> None:
        try:
            from fastapi.testclient import TestClient
            import backend.fastapi_app as fastapi_app
        except Exception:
            self.skipTest("FastAPI production dependencies are not installed.")

        if fastapi_app.FastAPI is None:
            self.skipTest("FastAPI production dependencies are not installed.")

        client = TestClient(fastapi_app.create_app())
        with patch.object(
            fastapi_app.JOB_STORE,
            "active_count_for_actor",
            return_value=fastapi_app.CONFIG.max_active_jobs_per_actor,
        ):
            response = client.post(
                "/api/analyze",
                files={"dataset": ("sales.csv", b"region,revenue\nNorth,10\n", "text/csv")},
                data={"goal": "测试并发配额"},
                headers={"X-Actor": "quota", "X-Role": "analyst"},
            )

        self.assertEqual(response.status_code, 429, response.text)


if __name__ == "__main__":
    unittest.main()
