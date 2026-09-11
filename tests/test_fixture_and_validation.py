from pathlib import Path

from evidence_repair.fixtures import write_invoice_fixture
from evidence_repair.validation import (
    apply_control_patch,
    run_hidden_validation,
    run_public_validation,
)


def test_invoice_fixture_baseline_fails_but_control_patch_passes(tmp_path: Path) -> None:
    fixture = write_invoice_fixture(tmp_path / "fixture")

    public = run_public_validation(fixture)
    hidden = run_hidden_validation(fixture)
    control = apply_control_patch(
        source_fixture=fixture,
        workspace=tmp_path / "control",
    )

    assert public["passed"] is False
    assert hidden["aggregate_score"] == 0.5
    assert control["control_passed"] is True
