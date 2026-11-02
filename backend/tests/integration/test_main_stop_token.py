"""Composition root (`avisabus.main`) and the dev stop-token secret warning (stop_tokens_qr v1.2).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database and working directory: the tests never touch `data/` nor a developer `.env`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.support.sae import E01

EVENT = "security.dev_stop_token_secret"


def _import_main(tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    workdir = tmp_path / "root" / "backend"  # no .env here nor in its parent
    workdir.mkdir(parents=True)
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    clean.update(
        {
            "AVISABUS_ENV": "test",
            "AVISABUS_DATABASE_URL": f"sqlite:///{tmp_path / 'avisabus.sqlite'}",
            "AVISABUS_SAE_REPLAY_DIR": str(E01),
            **env,
        }
    )
    return subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", "import avisabus.main"],
        cwd=workdir,
        env=clean,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _records_with_event(output: str) -> list[dict[str, Any]]:
    lines = [line for line in output.splitlines() if EVENT in line]
    return [json.loads(line) for line in lines]  # every such line must be a JSON log line


@pytest.mark.spec("stop_tokens_qr.AC-05")
def test_api_logs_the_dev_secret_warning_as_json_after_configuring_logging(
    tmp_path: Path,
) -> None:
    result = _import_main(tmp_path)
    assert result.returncode == 0, result.stderr
    (record,) = _records_with_event(result.stdout + result.stderr)
    assert record["level"] == "warning"
    assert record["env"] == "test"
    assert {"timestamp", "logger"} <= record.keys()


@pytest.mark.spec("stop_tokens_qr.AC-05")
def test_api_does_not_warn_with_a_configured_secret(tmp_path: Path) -> None:
    result = _import_main(tmp_path, AVISABUS_STOP_TOKEN_SECRET="x" * 32)
    assert result.returncode == 0, result.stderr
    assert _records_with_event(result.stdout + result.stderr) == []
