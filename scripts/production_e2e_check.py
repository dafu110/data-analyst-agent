from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "examples" / "sales.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an end-to-end production smoke check against a deployed API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL, for example http://127.0.0.1:8000")
    parser.add_argument("--token", default="", help="API token. If omitted, the check sends no token header.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="CSV/XLSX dataset to upload.")
    parser.add_argument("--timeout", type=int, default=90, help="Maximum seconds to wait for job completion.")
    args = parser.parse_args()

    client = ApiClient(args.base_url.rstrip("/"), args.token)
    health = client.get_json("/api/health")
    require(health.get("status") == "ok", f"health check failed: {health}")
    require(health.get("executor_mode") == "docker", f"expected docker executor, got {health.get('executor_mode')!r}")
    require(health.get("database") == "postgresql", f"expected PostgreSQL store, got {health.get('database')!r}")
    require(health.get("queue") == "redis-rq", f"expected Redis/RQ queue, got {health.get('queue')!r}")

    dataset_path = Path(args.dataset)
    require(dataset_path.exists(), f"dataset not found: {dataset_path}")
    job = client.upload_dataset(dataset_path, goal="生产端到端冒烟：生成经营分析报告并验证导出。")
    job_id = str(job["id"])

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        job = client.get_json(f"/api/jobs/{job_id}")
        if job.get("status") in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1)

    require(job.get("status") == "completed", f"job did not complete successfully: {job.get('status')} {job.get('error')}")
    result = job.get("result") or {}
    require(result.get("report_markdown"), "completed job has no report_markdown")
    require(len(result.get("chart_specs") or []) >= 1, "completed job has no chart specs")

    for export_format in ("md", "html", "csv"):
        content = client.get_bytes(f"/api/reports/{job_id}?format={export_format}")
        require(len(content) > 100, f"{export_format} export is unexpectedly small")
    prometheus = client.get_bytes("/api/metrics.prometheus")
    require(b"data_analyst_agent_jobs_total" in prometheus, "Prometheus metrics are missing job totals")

    print(json.dumps({"status": "ok", "job_id": job_id, "health": health, "prometheus_bytes": len(prometheus)}, ensure_ascii=False, indent=2))


class ApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    def headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "X-Actor": "production-smoke",
            "X-Org": "default",
            "X-Workspace": "default",
            "X-Role": "analyst",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def get_json(self, path: str) -> dict[str, object]:
        return json.loads(self.get_bytes(path).decode("utf-8"))

    def get_bytes(self, path: str) -> bytes:
        http_request = request.Request(f"{self.base_url}{path}", headers=self.headers())
        return open_request(http_request)

    def upload_dataset(self, path: Path, goal: str) -> dict[str, object]:
        boundary = "----data-analyst-agent-smoke"
        payload = build_multipart_payload(boundary, path, goal)
        http_request = request.Request(
            f"{self.base_url}/api/analyze",
            data=payload,
            method="POST",
            headers=self.headers(f"multipart/form-data; boundary={boundary}"),
        )
        return json.loads(open_request(http_request).decode("utf-8"))


def build_multipart_payload(boundary: str, path: Path, goal: str) -> bytes:
    lines: list[bytes] = []
    add_field(lines, boundary, "goal", goal)
    add_field(lines, boundary, "workspace", "default")
    add_field(lines, boundary, "business_scenario", "sales")
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(
        f'Content-Disposition: form-data; name="dataset"; filename="{path.name}"\r\n'
        "Content-Type: text/csv\r\n\r\n".encode()
    )
    lines.append(path.read_bytes())
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    return b"".join(lines)


def add_field(lines: list[bytes], boundary: str, name: str, value: str) -> None:
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))


def open_request(http_request: request.Request) -> bytes:
    try:
        with request.urlopen(http_request, timeout=20) as response:
            return response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("interrupted")
