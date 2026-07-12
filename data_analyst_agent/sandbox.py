from __future__ import annotations

import json
import os
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
    sandbox_volume = os.getenv("DATA_ANALYST_AGENT_SANDBOX_VOLUME", "").strip()
    sandbox_workdir = os.getenv("DATA_ANALYST_AGENT_SANDBOX_WORKDIR", "").strip()
    if bool(sandbox_volume) != bool(sandbox_workdir):
        raise RuntimeError("Sandbox volume and work directory must be configured together.")

    with tempfile.TemporaryDirectory(dir=sandbox_workdir or None) as tmp:
        workdir = Path(tmp)
        workdir.chmod(0o733)
        input_path = workdir / "input.json"
        code_path = workdir / "analysis.py"
        output_path = workdir / "output.json"
        input_path.write_text(df.to_json(orient="records", force_ascii=False), encoding="utf-8")
        code_path.write_text(code, encoding="utf-8")
        sandbox_path = f"/work/{workdir.name}" if sandbox_volume else "/work"
        mount_source = f"{sandbox_volume}:/work:rw" if sandbox_volume else f"{workdir}:/work:rw"
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
            mount_source,
            SANDBOX_IMAGE,
            "python",
            "/sandbox_runner.py",
            f"{sandbox_path}/input.json",
            f"{sandbox_path}/analysis.py",
            f"{sandbox_path}/output.json",
        ]
        subprocess.run(command, check=True, timeout=timeout_seconds)
        return json.loads(output_path.read_text(encoding="utf-8"))
