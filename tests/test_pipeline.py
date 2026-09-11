from pathlib import Path

from evidence_repair.pipeline import run_repair_loop, validate_manifest


def test_heuristic_pipeline_promotes_without_activation(tmp_path: Path) -> None:
    result = run_repair_loop(out=tmp_path / "run")
    summary = result.summary

    assert summary["baseline_public_passed"] is False
    assert summary["baseline_hidden_score"] == 0.5
    assert summary["final_public_passed"] is True
    assert summary["candidate_hidden_score"] == 1.0
    assert summary["promotion_decision"]["decision"] == "PROMOTE"
    assert summary["activation_performed"] is False
    assert summary["all_invariants_passed"] is True
    assert (result.out / "summary.json").exists()
    assert (result.out / "analysis.md").exists()


def test_run_loop_refuses_to_overwrite_existing_output(tmp_path: Path) -> None:
    out = tmp_path / "run"
    out.mkdir()

    try:
        run_repair_loop(out=out)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")


def test_manifest_guard_rejects_missing_and_forbidden_fields() -> None:
    guard = validate_manifest({"hidden_cases": []})

    assert guard["passed"] is False
    assert "program_version" in guard["missing_fields"]
    assert "hidden_cases" in guard["forbidden_fields"]
