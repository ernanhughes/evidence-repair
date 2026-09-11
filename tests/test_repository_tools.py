from pathlib import Path

from evidence_repair.fixtures import write_invoice_fixture
from evidence_repair.tools import RepositoryTools, ToolAudit


def test_repository_tools_find_and_read_invoice_function(tmp_path: Path) -> None:
    fixture = write_invoice_fixture(tmp_path / "fixture")
    tools = RepositoryTools(fixture)

    search = tools.search_repository("invoice_total")
    read = tools.read_file("service.py", 1, 20)
    symbol = tools.inspect_symbol("invoice_total")

    assert search.ok is True
    assert {"path": "service.py"} in search.data
    assert read.ok is True
    assert symbol.ok is True
    assert symbol.data == [{"path": "service.py", "kind": "FunctionDef", "line": 4}]


def test_repository_tools_reject_path_escape(tmp_path: Path) -> None:
    fixture = write_invoice_fixture(tmp_path / "fixture")
    tools = RepositoryTools(fixture)

    result = tools.read_file("../outside.py", 1, 1)

    assert result.ok is False
    assert result.error == "path escapes repository root"


def test_tool_audit_records_observation_fingerprints(tmp_path: Path) -> None:
    fixture = write_invoice_fixture(tmp_path / "fixture")
    audit = ToolAudit(RepositoryTools(fixture))

    observation = audit.search_repository("invoice_total")

    assert "service.py" in observation
    assert len(audit.calls) == 1
    assert audit.calls[0]["tool_name"] == "search_repository"
    assert "observation_fingerprint" in audit.calls[0]
