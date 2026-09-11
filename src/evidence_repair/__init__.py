"""Evidence-backed repository repair.

The package exposes a small runnable version of the DSPy book capstone:
models may propose repairs, but deterministic code owns validation,
independent evaluation, promotion, and activation boundaries.
"""

from .pipeline import RunResult, run_repair_loop
from .planners import HeuristicRepairPlanner, RepairPlan, RepairPlanner, RepairProposal
from .promotion import ComparisonDecision, ComparisonPolicy, PromotionRecord

__all__ = [
    "ComparisonDecision",
    "ComparisonPolicy",
    "HeuristicRepairPlanner",
    "PromotionRecord",
    "RepairPlan",
    "RepairPlanner",
    "RepairProposal",
    "RunResult",
    "run_repair_loop",
]
