"""Repository fixtures for Evidence Repair.

The initial project ships one tiny invoice repository. It is intentionally
simple: the purpose is to exercise the evidence loop, not to hide a puzzle.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


ISSUE = (
    "Invoice totals ignore item quantity. Repair the repository so "
    "invoice_total multiplies each line item's price by its quantity "
    "while preserving the existing public API."
)

CONSTRAINTS = (
    "Read-only diagnosis before patch generation. The repair may modify only "
    "service.py. Do not change models.py or tests. Do not use shell, network, "
    "or files outside the bound repository. Preserve invoice_total(items)."
)

ALLOWED_PATCH_FILES = frozenset({"service.py"})


@dataclass(frozen=True)
class HiddenCase:
    """A holdout case unavailable to repair generation."""

    case_id: str
    raw_items: tuple[tuple[float, int], ...]
    expected: float

    def to_record(self) -> dict[str, object]:
        return asdict(self)


HIDDEN_CASES = (
    HiddenCase("hidden-basic-quantity", ((10.0, 2), (3.0, 4)), 32.0),
    HiddenCase("hidden-single", ((7.5, 3),), 22.5),
    HiddenCase("hidden-zero-quantity", ((8.0, 0), (2.0, 5)), 10.0),
    HiddenCase("hidden-empty", (), 0.0),
)


def broken_service() -> str:
    """Return the intentionally broken implementation."""

    return (
        "from models import LineItem\n\n\n"
        "def invoice_total(items: list[LineItem]) -> float:\n"
        "    return sum(item.price for item in items)\n"
    )


def known_good_service() -> str:
    """Return the minimal repair for the invoice fixture."""

    return (
        "from models import LineItem\n\n\n"
        "def invoice_total(items: list[LineItem]) -> float:\n"
        "    \"\"\"Return the total value of all invoice line items.\"\"\"\n"
        "    return sum(item.price * item.quantity for item in items)\n"
    )


def write_invoice_fixture(root: Path, *, overwrite: bool = False) -> Path:
    """Create the invoice fixture repository and return its root."""

    if root.exists():
        if not overwrite:
            raise FileExistsError(f"fixture already exists: {root}")
        shutil.rmtree(root)

    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)

    (root / "models.py").write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class LineItem:\n"
        "    price: float\n"
        "    quantity: int\n",
        encoding="utf-8",
    )

    (root / "service.py").write_text(broken_service(), encoding="utf-8")

    (tests / "test_service.py").write_text(
        "import unittest\n\n"
        "from models import LineItem\n"
        "from service import invoice_total\n\n\n"
        "class ServiceTests(unittest.TestCase):\n"
        "    def test_invoice_total_uses_quantity(self):\n"
        "        items = [LineItem(10, 2), LineItem(3, 4)]\n"
        "        self.assertEqual(invoice_total(items), 32)\n\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# Invoice fixture\n\n"
        "Tests define the required observable behavior. The initial "
        "`service.py` implementation is intentionally broken.\n",
        encoding="utf-8",
    )

    return root
