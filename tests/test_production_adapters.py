from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import re

import pandas as pd

from backend.config import AppConfig, validate_runtime_config
from data_analyst_agent.database_connector import validate_database_url, validate_readonly_query
from data_analyst_agent.datasets import load_dataset_bundle
from data_analyst_agent.agent import DataAnalystAgent
from data_analyst_agent.relationships import infer_table_relationships


ROOT = Path(__file__).resolve().parents[1]


class ProductionAdapterTests(unittest.TestCase):
    def test_production_runtime_config_requires_secure_defaults(self) -> None:
        config = AppConfig(
            env="prod",
            host="127.0.0.1",
            port=8000,
            max_upload_bytes=1024,
            max_concurrent_jobs=1,
            job_timeout_seconds=60,
            api_token=None,
            admin_actors={"admin", "local"},
            storage_dir=Path("storage"),
            upload_dir=Path("uploads"),
            report_dir=Path("reports"),
            database_path=Path("agent.sqlite3"),
            frontend_dir=Path("frontend"),
            llm_provider="rules",
            llm_model="none",
            openai_api_key=None,
            database_url=None,
            redis_url=None,
            queue_name="analysis",
            executor_mode="in_process",
            allowed_database_hosts={"localhost"},
            rate_limit_per_minute=60,
            max_active_jobs_per_actor=3,
        )

        errors = validate_runtime_config(config)

        self.assertGreaterEqual(len(errors), 4)
        self.assertTrue(any("API_TOKEN" in error for error in errors))
        self.assertTrue(any("EXECUTOR_MODE=docker" in error for error in errors))
        self.assertTrue(any("ADMIN_ACTORS" in error for error in errors))

    def test_local_runtime_config_allows_developer_defaults(self) -> None:
        config = AppConfig(
            env="local",
            host="127.0.0.1",
            port=8000,
            max_upload_bytes=1024,
            max_concurrent_jobs=1,
            job_timeout_seconds=60,
            api_token=None,
            admin_actors={"admin"},
            storage_dir=Path("storage"),
            upload_dir=Path("uploads"),
            report_dir=Path("reports"),
            database_path=Path("agent.sqlite3"),
            frontend_dir=Path("frontend"),
            llm_provider="rules",
            llm_model="none",
            openai_api_key=None,
            database_url=None,
            redis_url=None,
            queue_name="analysis",
            executor_mode="in_process",
            allowed_database_hosts={"localhost"},
            rate_limit_per_minute=60,
            max_active_jobs_per_actor=3,
        )

        self.assertEqual(validate_runtime_config(config), [])

    def test_production_compose_uses_docker_sandbox_defaults(self) -> None:
        compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
        env_example = (ROOT / ".env.prod.example").read_text(encoding="utf-8")
        api_service = re.search(r"(?ms)^  api:\n(?P<body>.*?)(?=^  worker:)", compose).group("body")
        worker_service = re.search(r"(?ms)^  worker:\n(?P<body>.*?)(?=^volumes:)", compose).group("body")

        self.assertIn("DATA_ANALYST_AGENT_ENV: prod", compose)
        self.assertIn("DATA_ANALYST_AGENT_EXECUTOR_MODE: docker", compose)
        self.assertNotIn("/var/run/docker.sock:/var/run/docker.sock", api_service)
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", worker_service)
        self.assertIn("DATA_ANALYST_AGENT_ADMIN_ACTORS", compose)
        self.assertIn("condition: service_completed_successfully", compose)
        self.assertIn("DATA_ANALYST_AGENT_EXECUTOR_MODE=docker", env_example)
        self.assertIn("DATA_ANALYST_AGENT_ADMIN_ACTORS=admin", env_example)

    def test_sandbox_runner_drops_linux_capabilities(self) -> None:
        sandbox_source = (ROOT / "data_analyst_agent" / "sandbox.py").read_text(encoding="utf-8")

        self.assertIn('"--cap-drop"', sandbox_source)
        self.assertIn('"ALL"', sandbox_source)
        self.assertIn('"no-new-privileges"', sandbox_source)

    def test_production_e2e_script_is_available(self) -> None:
        script = ROOT / "scripts" / "production_e2e_check.py"

        self.assertTrue(script.exists())
        self.assertIn("/api/metrics.prometheus", script.read_text(encoding="utf-8"))

    def test_database_connector_rejects_unsafe_queries_and_hosts(self) -> None:
        validate_readonly_query("select * from orders")
        with self.assertRaises(ValueError):
            validate_readonly_query("delete from orders")
        with self.assertRaises(ValueError):
            validate_database_url("postgresql://user:pass@evil.example/db", {"localhost"})

    def test_excel_multi_sheet_loader_selects_largest_sheet(self) -> None:
        fake_sheets = {
            "small": pd.DataFrame({"a": [1]}),
            "large": pd.DataFrame({"a": [1, 2, 3]}),
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.xlsx"
            path.write_bytes(b"placeholder")
            with patch("pandas.read_excel", return_value=fake_sheets):
                bundle = load_dataset_bundle(path)

        self.assertEqual(bundle.source_type, "excel")
        self.assertEqual(len(bundle.primary), 3)
        self.assertEqual(set(bundle.tables), {"small", "large"})

    def test_relationship_inference_finds_matching_ids(self) -> None:
        tables = {
            "orders": pd.DataFrame({"customer_id": [1, 2, 3], "revenue": [10, 20, 30]}),
            "customers": pd.DataFrame({"customer_id": [1, 2, 3], "segment": ["A", "B", "C"]}),
        }
        relationships = infer_table_relationships(tables)

        self.assertTrue(relationships)
        self.assertEqual(relationships[0].left_column, "customer_id")

    def test_chart_specs_include_range_and_line_types(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = DataAnalystAgent().analyze_csv(root / "examples" / "monthly_sales.csv", "分析销售趋势")
        chart_types = {chart.id: chart.chart_type for chart in result.chart_specs}

        self.assertEqual(chart_types.get("numeric-ranges"), "range")
        self.assertEqual(chart_types.get("time-trend"), "line")


if __name__ == "__main__":
    unittest.main()
