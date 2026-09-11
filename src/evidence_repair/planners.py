"""Repair planners.

The planner is the only part of the loop allowed to be probabilistic. It may
inspect a read-only repository surface and propose a replacement, but it does
not apply patches, run hidden evaluation, promote, or activate anything.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .fixtures import known_good_service
from .tools import RepositoryTools, ToolAudit


@dataclass(frozen=True)
class RepairProposal:
    """A candidate repair produced by a planner."""

    diagnosis: str
    suspected_files: tuple[str, ...]
    missing_evidence: str
    target_file: str
    replacement_content: str
    rationale: str
    expected_behavior_change: str
    generator: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairPlan:
    """A proposal plus the tool trajectory used to produce it."""

    proposal: RepairProposal
    tool_calls: list[dict[str, object]]

    def to_record(self) -> dict[str, Any]:
        return {
            "proposal": self.proposal.to_record(),
            "tool_calls": self.tool_calls,
        }


class RepairPlanner(Protocol):
    """Interface implemented by deterministic and DSPy planners."""

    name: str

    def propose(
        self,
        *,
        issue: str,
        constraints: str,
        repository: Path,
    ) -> RepairPlan:
        """Inspect allowed evidence and return a bounded repair proposal."""


class HeuristicRepairPlanner:
    """Known-good planner for local verification and CI.

    It deliberately uses the same read-only tools the DSPy planner receives.
    This keeps the evidence loop testable without requiring a live model.
    """

    name = "heuristic"

    def propose(
        self,
        *,
        issue: str,
        constraints: str,
        repository: Path,
    ) -> RepairPlan:
        audit = ToolAudit(RepositoryTools(repository))
        audit.search_repository("invoice_total")
        audit.read_file("service.py", 1, 80)
        audit.inspect_symbol("invoice_total")

        proposal = RepairProposal(
            diagnosis=(
                "invoice_total sums only item.price. It must multiply each "
                "line item's price by its quantity before summing."
            ),
            suspected_files=("service.py",),
            missing_evidence="None for this fixture.",
            target_file="service.py",
            replacement_content=known_good_service(),
            rationale=(
                "The public API already passes LineItem objects with price and "
                "quantity. The bug is isolated to the total calculation."
            ),
            expected_behavior_change=(
                "Totals now include quantity while empty invoices still return 0."
            ),
            generator="HeuristicRepairPlanner",
            usage={"history_entries": 0, "total_tokens": 0},
        )

        return RepairPlan(proposal=proposal, tool_calls=audit.calls)
