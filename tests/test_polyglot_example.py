from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is not installed")
def test_dependency_free_node_client_drives_python_sidecar() -> None:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + existing if existing else "")
    result = subprocess.run(
        [
            NODE,
            str(ROOT / "examples" / "node" / "sidecar-client.mjs"),
            sys.executable,
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout.strip().splitlines()[-1])
    assert output["wire_api"] == "polyhorizon.wire/v0.1"
    assert set(output["commands"]) == {
        "abort",
        "advance",
        "capabilities",
        "inspect",
        "open",
    }
    assert output["open_status"] == "awaiting_effects"
    assert output["effect_count"] == 20
    assert output["inspect_digest"].startswith("sha256:")
    assert output["abort_status"] == "aborted"
