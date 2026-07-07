from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from urllib import request
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]


def build_multipart(dataset_path: Path, goal: str) -> tuple[bytes, str]:
    boundary = f"----daa-{uuid.uuid4().hex}"
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="goal"\r\n\r\n'
            f"{goal}\r\n"
        ).encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="dataset"; filename="{dataset_path.name}"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode("utf-8"),
        dataset_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def api_request(base_url: str, path: str, *, token: str, method: str = "GET", body: bytes | None = None, content_type: str | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Actor": "prod-check",
        "X-Org": "release",
        "X-Workspace": "verification",
        "X-Role": "analyst",
    }
    if content_type:
        headers["Content-Type"] = content_type
    req = request.Request(base_url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=10) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def read_json(status: int, body: bytes, context: str) -> dict:
    if status >= 400:
        raise RuntimeError(f"{context} failed with HTTP {status}: {body[:500].decode('utf-8', errors='replace')}")
    return json.loads(body.decode("utf-8"))


def run_check(base_url: str, token: str, dataset_path: Path, timeout_seconds: int) -> None:
    health_status, _, health_body = api_request(base_url, "/api/health", token=token)
    health = read_json(health_status, health_body, "health")
    print(f"health: {health.get('status')} database={health.get('database')} queue={health.get('queue')}")

    body, content_type = build_multipart(dataset_path, "生产端到端验证：生成经营分析报告并检查导出。")
    status, _, payload = api_request(base_url, "/api/analyze", token=token, method="POST", body=body, content_type=content_type)
    job = read_json(status, payload, "create job")
    job_id = job["id"]
    print(f"job created: {job_id}")

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status, _, payload = api_request(base_url, f"/api/jobs/{job_id}", token=token)
        job = read_json(status, payload, "poll job")
        if job["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1)

    if job.get("status") != "completed":
        raise RuntimeError(f"job did not complete: {job.get('status')} {job.get('error')}")
    print(f"job completed: charts={len(job.get('result', {}).get('chart_specs', []))}")

    for export_format in ("md", "html", "csv"):
        status, _, payload = api_request(base_url, f"/api/reports/{job_id}?format={export_format}", token=token)
        if status != 200 or len(payload) < 100:
            raise RuntimeError(f"{export_format} export failed with HTTP {status}")
        print(f"export ok: {export_format} bytes={len(payload)}")

    status, _, payload = api_request(base_url, "/api/metrics.prometheus", token=token)
    text = payload.decode("utf-8", errors="replace")
    if status != 200 or "data_analyst_agent_jobs_total" not in text:
        raise RuntimeError("Prometheus metrics endpoint did not return expected metrics.")
    print("metrics ok: prometheus")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an end-to-end production verification against a running Data Analyst Agent API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "examples" / "sales.csv")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    run_check(args.base_url, args.token, args.dataset, args.timeout_seconds)


if __name__ == "__main__":
    main()
