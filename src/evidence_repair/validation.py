"""Patch application and validation gates."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .artifacts import fingerprint, repository_snapshot, workspace_fingerprint
from .fixtures import ALLOWED_PATCH_FILES, HIDDEN_CASES, known_good_service


def run_public_validation(workspace: Path, *, timeout: int = 30) -> dict[str, Any]:
    """Run the repository's visible development tests."""

    command = [sys.executable, "-m", "unittest", "discover", "tests"]
    started = time.perf_counter()

    proc = subprocess.run(
        command,
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )

    return {
        "passed": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "elapsed_seconds": time.perf_counter() - started,
        "command": command,
        "output_fingerprint": fingerprint(
            {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        ),
    }


def run_hidden_validation(workspace: Path, *, timeout: int = 30) -> dict[str, Any]:
    """Run independent hidden cases without exposing them to the planner."""

    cases = [case.to_record() for case in HIDDEN_CASES]
    hidden_script = f"""
import json
from models import LineItem
from service import invoice_total

cases = json.loads({json.dumps(json.dumps(cases))})
rows = []

for case in cases:
    items = [LineItem(price, quantity) for price, quantity in case["raw_items"]]
    try:
        actual = invoice_total(items)
        passed = abs(float(actual) - float(case["expected"])) < 1e-9
        error = None
    except Exception as exc:
        actual = None
        passed = False
        error = f"{{type(exc).__name__}}: {{exc}}"

    rows.append(
        {{
            "case_id": case["case_id"],
            "passed": passed,
            "actual": actual,
            "expected": case["expected"],
            "error": error,
        }}
    )

print(json.dumps(rows, sort_keys=True))
"""

    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", hidden_script],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )

    rows: list[dict[str, Any]] = []
    if proc.returncode == 0:
        try:
            decoded = json.loads(proc.stdout.strip())
            if isinstance(decoded, list):
                rows = [dict(row) for row in decoded]
        except json.JSONDecodeError:
            rows = []

    if not rows:
        rows = [
            {
                "case_id": case.case_id,
                "passed": False,
                "actual": None,
                "expected": case.expected,
                "error": "hidden validator did not return parseable results",
            }
            for case in HIDDEN_CASES
        ]

    passed_count = sum(1 for row in rows if row.get("passed") is True)

    return {
        "executed": True,
        "passed": proc.returncode == 0 and passed_count == len(HIDDEN_CASES),
        "returncode": proc.returncode,
        "cases": rows,
        "passed_count": passed_count,
        "failed_count": len(HIDDEN_CASES) - passed_count,
        "aggregate_score": passed_count / len(HIDDEN_CASES),
        "stderr": proc.stderr,
        "elapsed_seconds": time.perf_counter() - started,
        "protocol_case_ids": [case.case_id for case in HIDDEN_CASES],
        "output_fingerprint": fingerprint(rows),
    }


def syntax_check(content: str) -> dict[str, Any]:
    """Parse replacement Python before it can touch a candidate workspace."""

    try:
        ast.parse(content)
    except SyntaxError as exc:
        return {
            "passed": False,
            "error": f"SyntaxError line {exc.lineno}: {exc.msg}",
        }
    return {"passed": True, "error": None}


def normalize_target_file(path: str) -> str:
    """Normalize a planner-provided target file without resolving outside root."""

    return path.strip().replace("\\", "/").removeprefix("./")


def apply_replacement(
    *,
    source_fixture: Path,
    workspace: Path,
    target_file: str,
    replacement_content: str,
    allowed_files: frozenset[str] = ALLOWED_PATCH_FILES,
) -> dict[str, Any]:
    """Apply a full-file replacement in an isolated candidate workspace."""

    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(source_fixture, workspace)

    normalized = normalize_target_file(target_file)
    if normalized not in allowed_files:
        return {
            "applied": False,
            "target_file": normalized,
            "scope_passed": False,
            "syntax_passed": False,
            "changed_files": [],
            "error": "target file outside allowed patch surface",
        }

    syntax = syntax_check(replacement_content)
    if not syntax["passed"]:
        return {
            "applied": False,
            "target_file": normalized,
            "scope_passed": True,
            "syntax_passed": False,
            "changed_files": [],
            "error": syntax["error"],
        }

    before = repository_snapshot(workspace)
    (workspace / normalized).write_text(
        replacement_content.rstrip() + "\n",
        encoding="utf-8",
    )
    after = repository_snapshot(workspace)

    changed = sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )

    return {
        "applied": True,
        "target_file": normalized,
        "scope_passed": set(changed).issubset(allowed_files),
        "syntax_passed": True,
        "changed_files": changed,
        "error": None,
        "workspace_fingerprint": workspace_fingerprint(workspace),
        "replacement_fingerprint": fingerprint(replacement_content),
    }


def apply_control_patch(
    *,
    source_fixture: Path,
    workspace: Path,
) -> dict[str, Any]:
    """Apply the known-good repair to prove the validation harness works."""

    application = apply_replacement(
        source_fixture=source_fixture,
        workspace=workspace,
        target_file="service.py",
        replacement_content=known_good_service(),
    )

    public = (
        run_public_validation(workspace)
        if application["applied"]
        else {"passed": False, "error": application["error"]}
    )
    hidden = (
        run_hidden_validation(workspace)
        if public.get("passed") is True
        else {"executed": False, "passed": False, "reason": "public validation failed"}
    )

    return {
        "application": application,
        "public_validation": public,
        "hidden_validation": hidden,
        "control_passed": (
            application["applied"]
            and application["scope_passed"]
            and application["syntax_passed"]
            and public.get("passed") is True
            and hidden.get("passed") is True
        ),
    }
