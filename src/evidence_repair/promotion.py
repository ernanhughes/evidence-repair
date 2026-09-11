"""Promotion records and comparison policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum

from .artifacts import fingerprint


class ComparisonDecision(str, Enum):
    """Possible outcomes of comparing a candidate with an active baseline."""

    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class EvaluationSummary:
    """Minimal comparable evaluation record."""

    program_id: str
    case_count: int
    aggregate_score: float
    hard_failures: int
    validation_failures: int
    baseline_fingerprint: str
    evaluation_protocol_fingerprint: str

    def to_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ComparisonPolicy:
    """Policy thresholds for promotion."""

    min_cases: int = 2
    min_improvement: float = 0.05
    expected_baseline_fingerprint: str = ""


@dataclass(frozen=True)
class PromotionRecord:
    """Evidence-backed recommendation. This is not activation."""

    decision: ComparisonDecision
    reason: str
    active_program_id: str
    candidate_program_id: str

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record["decision"] = self.decision.value
        record["fingerprint"] = fingerprint(record)
        return record


def evaluation_protocol_fingerprint(
    *,
    dataset_fingerprint: str,
    split_fingerprint: str,
    evaluation_case_ids: tuple[str, ...],
    metric_fingerprint: str,
    validation_contract: str,
    model_runtime_policy: str,
) -> str:
    """Fingerprint the independent evaluation protocol."""

    return fingerprint(
        {
            "dataset_fingerprint": dataset_fingerprint,
            "split_fingerprint": split_fingerprint,
            "evaluation_case_ids": evaluation_case_ids,
            "metric_fingerprint": metric_fingerprint,
            "validation_contract": validation_contract,
            "model_runtime_policy": model_runtime_policy,
        }
    )


def compare(
    active: EvaluationSummary,
    candidate: EvaluationSummary,
    policy: ComparisonPolicy,
) -> PromotionRecord:
    """Compare candidate evidence against the active baseline."""

    if active.baseline_fingerprint != policy.expected_baseline_fingerprint:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "active stale baseline fingerprint",
            active.program_id,
            candidate.program_id,
        )
    if candidate.baseline_fingerprint != policy.expected_baseline_fingerprint:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "candidate stale baseline fingerprint",
            active.program_id,
            candidate.program_id,
        )
    if active.evaluation_protocol_fingerprint != candidate.evaluation_protocol_fingerprint:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "evaluation protocol mismatch",
            active.program_id,
            candidate.program_id,
        )
    if candidate.case_count < policy.min_cases:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "too few candidate cases",
            active.program_id,
            candidate.program_id,
        )
    if candidate.hard_failures > active.hard_failures:
        return PromotionRecord(
            ComparisonDecision.REJECT,
            "hard regression",
            active.program_id,
            candidate.program_id,
        )
    if candidate.validation_failures > active.validation_failures:
        return PromotionRecord(
            ComparisonDecision.REJECT,
            "validation regression",
            active.program_id,
            candidate.program_id,
        )
    if candidate.aggregate_score >= active.aggregate_score + policy.min_improvement:
        return PromotionRecord(
            ComparisonDecision.PROMOTE,
            "meaningful improvement without hard regression",
            active.program_id,
            candidate.program_id,
        )
    return PromotionRecord(
        ComparisonDecision.INSUFFICIENT,
        "improvement below threshold",
        active.program_id,
        candidate.program_id,
    )


def decide_promotion(
    *,
    active: EvaluationSummary,
    candidate: EvaluationSummary | None,
    public_validation_passed: bool,
    policy: ComparisonPolicy,
) -> PromotionRecord:
    """Apply preconditions before comparing independent evaluation summaries."""

    if not public_validation_passed:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "candidate did not pass public development validation",
            active.program_id,
            "candidate-unavailable",
        )
    if candidate is None:
        return PromotionRecord(
            ComparisonDecision.INSUFFICIENT,
            "independent candidate evaluation unavailable",
            active.program_id,
            "candidate-unavailable",
        )
    return compare(active, candidate, policy)
