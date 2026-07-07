from __future__ import annotations

import time
import unittest
from pathlib import Path


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

        for export_format in ("md", "html", "csv"):
            export_response = client.get(
                f"/api/reports/{job_id}?format={export_format}",
                headers={"X-Actor": "smoke", "X-Org": "default", "X-Workspace": "default", "X-Role": "analyst"},
            )
            self.assertEqual(export_response.status_code, 200, export_response.text[:200])
            self.assertGreater(len(export_response.content), 100)


if __name__ == "__main__":
    unittest.main()
