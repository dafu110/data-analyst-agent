from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd


SANDBOX_IMAGE = "data-analyst-agent-sandbox:latest"


def run_python_in_docker(df: pd.DataFrame, code: str, timeout_seconds: int = 30) -> Any:
    """Execute analysis code inside a locked-down Docker container.

    This is an optional production boundary. It requires Docker and a sandbox
    image built from docker/sandbox.Dockerfile. The normal AST guardrails still
    run before this function is called.
    """
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        input_path = workdir / "input.json"
        code_path = workdir / "analysis.py"
        output_path = workdir / "output.json"
        input_path.write_text(df.to_json(orient="records", force_ascii=False), encoding="utf-8")
        code_path.write_text(code, encoding="utf-8")
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "512m",
            "--pids-limit",
            "128",
            "--read-only",
            "--security-opt",
            "no-new-privileges",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "-v",
            f"{workdir}:/work:rw",
            SANDBOX_IMAGE,
            "python",
            "/sandbox_runner.py",
            "/work/input.json",
            "/work/analysis.py",
            "/work/output.json",
        ]
        subprocess.run(command, check=True, timeout=timeout_seconds)
        return json.loads(output_path.read_text(encoding="utf-8"))
