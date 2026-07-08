from __future__ import annotations

import argparse
import importlib.metadata
import shutil
import socket
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from backend.config import load_config, validate_runtime_config


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def run_checks(require_external: bool = False) -> list[CheckResult]:
    config = load_config()
    results = [
        check_git_repository(),
        check_optional_import("fastapi", "FastAPI"),
        check_optional_import("psycopg", "PostgreSQL driver"),
        check_optional_import("redis", "Redis client"),
        check_optional_import("rq", "RQ worker"),
        check_optional_import("reportlab", "PDF exporter"),
        check_optional_import("pptx", "PPTX exporter"),
        check_python_dependency_versions(),
        check_runtime_config(config),
        check_postgres_config(config.database_url, require_external),
        check_redis_config(config.redis_url, require_external),
        check_docker(config.executor_mode, require_external),
    ]
    return results


def check_runtime_config(config) -> CheckResult:
    errors = validate_runtime_config(config)
    if errors:
        return CheckResult("Runtime configuration", "failed", " ".join(errors))
    if config.env.lower() in {"prod", "production"}:
        return CheckResult("Runtime configuration", "ok", "生产环境关键配置已设置。")
    return CheckResult("Runtime configuration", "ok", f"当前环境为 {config.env}，按本地/测试配置运行。")

def check_git_repository() -> CheckResult:
    root = Path(__file__).resolve().parents[1]
    git = shutil.which("git")
    if not git:
        return CheckResult("Git repository", "warning", "git command is not available; repository status was not checked.")
    try:
        completed = subprocess.run([git, "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True, timeout=5)
    except Exception as exc:
        return CheckResult("Git repository", "warning", f"git status check failed: {exc}")
    if completed.returncode != 0:
        return CheckResult("Git repository", "warning", "This directory is not a Git work tree. Initialize Git or open the repository root before release.")
    branch = subprocess.run([git, "-C", str(root), "branch", "--show-current"], capture_output=True, text=True, timeout=5)
    current_branch = branch.stdout.strip() or "detached HEAD"
    return CheckResult("Git repository", "ok", f"Git work tree detected on {current_branch}.")


def check_optional_import(module_name: str, label: str) -> CheckResult:
    try:
        __import__(module_name)
    except ImportError:
        return CheckResult(label, "missing", f"缺少 {module_name}，请安装生产依赖：pip install -e .[prod]")
    return CheckResult(label, "ok", f"{module_name} 可导入")

def check_python_dependency_versions() -> CheckResult:
    try:
        protobuf_version = importlib.metadata.version("protobuf")
    except importlib.metadata.PackageNotFoundError:
        return CheckResult("Python dependency versions", "skipped", "protobuf is not installed in this environment.")
    if not version_in_range(protobuf_version, "5.26.1", "6.0.0"):
        return CheckResult(
            "Python dependency versions",
            "failed",
            f"protobuf {protobuf_version} conflicts with production dependencies; run `python -m pip install -e .[prod]`.",
        )
    return CheckResult("Python dependency versions", "ok", f"protobuf {protobuf_version} satisfies production dependency constraints.")


def version_in_range(version: str, minimum: str, maximum: str) -> bool:
    return version_key(version) >= version_key(minimum) and version_key(version) < version_key(maximum)


def version_key(version: str) -> tuple[int, ...]:
    parts = []
    for chunk in version.replace("-", ".").split("."):
        digits = "".join(char for char in chunk if char.isdigit())
        parts.append(int(digits or 0))
    return tuple(parts)


def check_postgres_config(database_url: str | None, require_external: bool) -> CheckResult:
    if not database_url:
        status = "failed" if require_external else "skipped"
        return CheckResult("PostgreSQL", status, "未设置 DATA_ANALYST_AGENT_DATABASE_URL")
    parsed = urlparse(database_url)
    reachable = host_port_open(parsed.hostname, parsed.port or 5432)
    if reachable:
        return CheckResult("PostgreSQL", "ok", f"{parsed.hostname}:{parsed.port or 5432} 可连接")
    return CheckResult("PostgreSQL", "failed" if require_external else "warning", f"{parsed.hostname}:{parsed.port or 5432} 暂不可连接")


def check_redis_config(redis_url: str | None, require_external: bool) -> CheckResult:
    if not redis_url:
        status = "failed" if require_external else "skipped"
        return CheckResult("Redis/RQ", status, "未设置 DATA_ANALYST_AGENT_REDIS_URL")
    parsed = urlparse(redis_url)
    reachable = host_port_open(parsed.hostname, parsed.port or 6379)
    if reachable:
        return CheckResult("Redis/RQ", "ok", f"{parsed.hostname}:{parsed.port or 6379} 可连接")
    return CheckResult("Redis/RQ", "failed" if require_external else "warning", f"{parsed.hostname}:{parsed.port or 6379} 暂不可连接")


def check_docker(executor_mode: str, require_external: bool) -> CheckResult:
    docker = shutil.which("docker")
    if not docker:
        status = "failed" if require_external or executor_mode == "docker" else "skipped"
        return CheckResult("Docker sandbox", status, "未找到 docker 命令")
    try:
        completed = subprocess.run([docker, "version", "--format", "{{.Server.Version}}"], capture_output=True, text=True, timeout=5)
    except Exception as exc:
        status = "failed" if require_external or executor_mode == "docker" else "warning"
        return CheckResult("Docker sandbox", status, f"Docker 不可用：{exc}")
    if completed.returncode == 0:
        image_check = subprocess.run(
            [docker, "image", "inspect", "data-analyst-agent-sandbox:latest"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if image_check.returncode == 0:
            if require_external or executor_mode == "docker":
                smoke = run_docker_sandbox_smoke(docker)
                if smoke.status != "ok":
                    return smoke
            return CheckResult("Docker sandbox", "ok", f"Docker server {completed.stdout.strip()}，沙箱镜像可用")
        status = "failed" if require_external or executor_mode == "docker" else "warning"
        return CheckResult(
            "Docker sandbox",
            status,
            "Docker 可用，但未找到 data-analyst-agent-sandbox:latest；请运行 docker build -f docker/sandbox.Dockerfile -t data-analyst-agent-sandbox:latest .",
        )
    status = "failed" if require_external or executor_mode == "docker" else "warning"
    return CheckResult("Docker sandbox", status, completed.stderr.strip() or "Docker server 暂不可用")


def run_docker_sandbox_smoke(docker: str) -> CheckResult:
    try:
        completed = subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "data-analyst-agent-sandbox:latest",
                "python",
                "-c",
                "print('sandbox-ok')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return CheckResult("Docker sandbox smoke", "failed", f"沙箱容器 smoke 运行失败：{exc}")
    if completed.returncode == 0 and "sandbox-ok" in completed.stdout:
        return CheckResult("Docker sandbox smoke", "ok", "沙箱容器可启动，且使用 no-network/read-only/cap-drop 基线。")
    return CheckResult(
        "Docker sandbox smoke",
        "failed",
        completed.stderr.strip() or completed.stdout.strip() or "沙箱容器 smoke 未返回预期输出。",
    )


def host_port_open(host: str | None, port: int) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run production readiness checks for Data Analyst Agent.")
    parser.add_argument("--require-external", action="store_true", help="Treat missing PostgreSQL/Redis/Docker as failures.")
    args = parser.parse_args()
    results = run_checks(require_external=args.require_external)
    for result in results:
        print(f"[{result.status.upper()}] {result.name}: {result.detail}")
    if any(result.status == "failed" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
