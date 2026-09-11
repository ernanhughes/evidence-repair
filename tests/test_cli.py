from pathlib import Path

from evidence_repair.cli import main


def test_cli_run_writes_summary(tmp_path: Path, capsys) -> None:
    out = tmp_path / "cli-run"

    main(["run", "--out", str(out)])
    captured = capsys.readouterr()

    assert '"promotion_decision": "PROMOTE"' in captured.out
    assert (out / "summary.json").exists()
