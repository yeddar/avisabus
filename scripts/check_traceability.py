#!/usr/bin/env python3
"""Harness checks for AvisaBus.

--schema-only : validate feature_list.json (statuses, dependencies, spec folders).
(default)     : for every feature whose status is implementing or later, check that each
                acceptance criterion `<feature>.AC-n` in its requirements.md is cited by at
                least one test in backend/tests or frontend/ (src, tests, e2e).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKED = {"implementing", "in_review", "changes_requested", "done"}
NEEDS_SPEC = {"spec_draft", "spec_approved", "spec_blocked", "exploring"} | TRACKED
TEST_DIRS = [
    ROOT / "backend" / "tests",
    ROOT / "frontend" / "src",
    ROOT / "frontend" / "tests",
    ROOT / "frontend" / "e2e",
]
TEST_SUFFIXES = {".py", ".ts", ".tsx"}


def load_features() -> tuple[list[dict], set[str]]:
    data = json.loads((ROOT / "feature_list.json").read_text(encoding="utf-8"))
    return data["features"], set(data["statuses"])


def check_schema() -> list[str]:
    errors: list[str] = []
    features, statuses = load_features()
    ids = [f["id"] for f in features]
    if len(ids) != len(set(ids)):
        errors.append("feature_list.json: ids duplicados")
    known = set(ids)
    order = {f["id"]: f["order"] for f in features}
    for f in features:
        if f["status"] not in statuses:
            errors.append(f"{f['id']}: estado desconocido '{f['status']}'")
        for dep in f["depends_on"]:
            if dep not in known:
                errors.append(f"{f['id']}: dependencia desconocida '{dep}'")
            elif order[dep] >= f["order"]:
                errors.append(f"{f['id']}: depende de '{dep}', que va después")
        if f["status"] in NEEDS_SPEC:
            spec = ROOT / f["spec"]
            for name in ("requirements.md", "design.md", "tasks.md"):
                if not (spec / name).is_file():
                    errors.append(f"{f['id']}: falta {f['spec']}{name}")
        if f["status"] in TRACKED:
            for name in ("requirements.md", "design.md", "tasks.md"):
                path = ROOT / f["spec"] / name
                if path.is_file() and "Estado: APPROVED" not in path.read_text(encoding="utf-8"):
                    errors.append(f"{f['id']}: {name} no está APPROVED y la feature ya se implementa")
    return errors


def corpus() -> str:
    chunks: list[str] = []
    for base in TEST_DIRS:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.suffix in TEST_SUFFIXES and "node_modules" not in path.parts:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


AUTOMATED = re.compile(r"\b(unit|integration|e2e)\b", re.IGNORECASE)


def automated_acs(feature_id: str, requirements: str) -> list[str]:
    """ACs whose '*Verificación:*' line declares an automated test type (see docs/specs.md §3)."""
    result: list[str] = []
    pattern = re.compile(
        rf"\*\*({re.escape(feature_id)}\.AC-\d+)\*\*(.*?)\*Verificación:\*([^\n]*)", re.DOTALL
    )
    for match in pattern.finditer(requirements):
        ac = match.group(1)
        verification = re.sub(r"`[^`]*`|\([^)]*\)", "", match.group(3))  # ignore code and details
        if AUTOMATED.search(verification):
            result.append(ac)
    return result


def check_traceability() -> list[str]:
    errors: list[str] = []
    features, _ = load_features()
    tracked = [f for f in features if f["status"] in TRACKED]
    if not tracked:
        return errors
    text = corpus()
    for f in tracked:
        req = (ROOT / f["spec"] / "requirements.md").read_text(encoding="utf-8")
        for ac in automated_acs(f["id"], req):
            if not re.search(rf"\b{re.escape(ac)}\b", text):
                errors.append(f"{ac}: ningún test lo cita")
    return errors


def main() -> int:
    errors = check_schema() if "--schema-only" in sys.argv else check_traceability()
    for e in errors:
        print(f"  - {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
