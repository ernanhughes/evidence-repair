"""End-to-end Evidence Repair pipeline."""

from __future__ import annotations

import importlib.metadata
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import fingerprint, file_fingerprint, write_json, workspace_fingerprint
from .fixtures import CONSTRAINTS, HIDDEN_CASES, ISSUE, write_invoice_fixture
from .planners import HeuristicRepairPlanner, RepairPlan, RepairPlanner
from .promotion import (
    ComparisonPolicy,
    EvaluationSummary,
    decide_promotion,
    evaluation_protocol_fingerprint,
)
from .validation import (
    apply_control_patch,
    apply_replacement,
    run_hidden_validation,
    run_public_validation,
)


@dataclass(frozen=True)
class RunResult:
    """Returned by `run_repair_loop` after artifacts have been written."""

    out: Path
    summary: dict[str, Any]


def _optional_distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _candidate_artifact(
    *,
    plan: RepairPlan,
    attempt_number: int,
    fixture_fingerprint: str,
    application: dict[str, Any],
    public_validation: dict[str, Any],
) -> dict[str, Any]:
    proposal = plan.proposal
    record: dict[str, Any] = {
        "candidate_id": f"{proposal.generator.lower()}-attempt-{attempt_number}",
        "attempt_number": attempt_number,
        "generator": proposal.generator,
        "target_file": application.get("target_file", proposal.target_file),
        "source_workspace_fingerprint": fixture_fingerprint,
        "replacement_fingerprint": application.get("replacement_fingerprint"),
        "syntax_passed": application.get("syntax_passed") is True,
        "scope_passed": application.get("scope_passed") is True,
        "development_validation_passed": public_validation.get("passed") is True,
        "changed_files": application.get("changed_files", []),
        "diagnosis": proposal.diagnosis,
        "rationale": proposal.rationale,
        "expected_behavior_change": proposal.expected_behavior_change,
    }
    record["candidate_artifact_fingerprint"] = fingerprint(record)
    return record


def _make_attempt(
    *,
    plan: RepairPlan,
    source_fixture: Path,
    workspace: Path,
    attempt_number: int,
    fixture_fingerprint: str,
) -> dict[str, Any]:
    application = apply_replacement(
        source_fixture=source_fixture,
        workspace=workspace,
        target_file=plan.proposal.target_file,
        replacement_content=plan.proposal.replacement_content,
    )

    public_validation = (
        run_public_validation(workspace)
        if application.get("applied") is True
        else {"passed": False, "error": application.get("error")}
    )

    return {
        "attempt_number": attempt_number,
        "proposal": plan.proposal.to_record(),
        "application": application,
        "public_validation": public_validation,
        "candidate_artifact": _candidate_artifact(
            plan=plan,
            attempt_number=attempt_number,
            fixture_fingerprint=fixture_fingerprint,
            application=application,
            public_validation=public_validation,
        ),
    }


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Check that the capstone manifest records the boundary we rely on."""

    required = {
        "program_version",
        "fixture_fingerprint",
        "issue_fingerprint",
        "tool_surface_fingerprint",
        "development_validation_contract",
        "independent_evaluation_protocol_fingerprint",
        "candidate_artifact_fingerprint",
        "promotion_decision_fingerprint",
        "repair_budget",
        "source_revision",
    }
    forbidden = {
        "hidden_cases",
        "hidden_case_expected_outputs",
        "hidden_evaluation_results_visible_to_planner",
    }

    missing_fields = sorted(required - set(manifest))
    forbidden_fields = sorted(forbidden & set(manifest))

    return {
        "passed": not missing_fields and not forbidden_fields,
        "missing_fields": missing_fields,
        "forbidden_fields": forbidden_fields,
        "manifest_fingerprint": fingerprint(manifest),
    }


def _analysis_markdown(summary: dict[str, Any], invariants: dict[str, bool]) -> str:
    lines = [
        "# Evidence Repair Run",
        "",
        "Evidence classification: measured locally; planner-backed candidate; "
        "read-only tool trajectory; deterministic validation; independent "
        "evaluation when eligible; promotion recommendation; no automatic activation.",
        "",
        "## Summary",
        "",
        f"- planner: {summary['planner']}",
        f"- fixture fingerprint: {summary['fixture_fingerprint']}",
        f"- baseline public validation passed: {summary['baseline_public_passed']}",
        f"- baseline hidden score: {summary['baseline_hidden_score']}",
        f"- control patch passed: {summary['control_patch_passed']}",
        f"- tool calls: {summary['tool_call_count']}",
        f"- final public validation passed: {summary['final_public_passed']}",
        f"- candidate hidden evaluation executed: {summary['candidate_hidden_executed']}",
        f"- candidate hidden score: {summary['candidate_hidden_score']}",
        f"- promotion decision: {summary['promotion_decision']['decision']}",
        f"- promotion reason: {summary['promotion_decision']['reason']}",
        f"- activation performed: {summary['activation_performed']}",
        "",
        "## Invariants",
        "",
    ]

    for name, passed in invariants.items():
        lines.append(f"- {name}: {passed}")

    lines.extend(
        [
            "",
            "The repair candidate is allowed to fail. The run becomes "
            "uninterpretable only if the evidence boundary, validation gates, "
            "manifest guard, or promotion separation fail.",
            "",
        ]
    )
    return "\n".join(lines)


def run_repair_loop(
    *,
    out: Path,
    planner: RepairPlanner | None = None,
    overwrite: bool = False,
) -> RunResult:
    """Run the invoice repository-repair evidence loop."""

    out = out.resolve()
    if out.exists():
        if not overwrite:
            raise FileExistsError(f"output directory already exists: {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    active_planner = planner or HeuristicRepairPlanner()

    fixture = write_invoice_fixture(out / "fixture_repo", overwrite=True)
    fixture_fingerprint = workspace_fingerprint(fixture)
    broken_service_fingerprint = file_fingerprint(fixture / "service.py")

    baseline_public = run_public_validation(fixture)
    baseline_hidden = run_hidden_validation(fixture)
    control = apply_control_patch(
        source_fixture=fixture,
        workspace=out / "control_workspace",
    )

    plan = active_planner.propose(
        issue=ISSUE,
        constraints=CONSTRAINTS,
        repository=fixture,
    )

    attempt = _make_attempt(
        plan=plan,
        source_fixture=fixture,
        workspace=out / "attempt_1",
        attempt_number=1,
        fixture_fingerprint=fixture_fingerprint,
    )
    attempts = [attempt]

    final_public_passed = attempt["public_validation"].get("passed") is True
    final_workspace = out / "attempt_1"
    candidate_hidden = (
        run_hidden_validation(final_workspace) if final_public_passed else None
    )

    protocol_fingerprint = evaluation_protocol_fingerprint(
        dataset_fingerprint=fixture_fingerprint,
        split_fingerprint=fingerprint(
            {
                "development": ["public-test-invoice-quantity"],
                "independent": [case.case_id for case in HIDDEN_CASES],
            }
        ),
        evaluation_case_ids=tuple(case.case_id for case in HIDDEN_CASES),
        metric_fingerprint="hidden_case_pass_fraction_v1",
        validation_contract="all_hidden_cases_must_pass_for_promotion_v1",
        model_runtime_policy="deterministic_validation",
    )

    baseline_artifact_fingerprint = fingerprint(
        {
            "program_id": "invoice-repair-baseline",
            "fixture_fingerprint": fixture_fingerprint,
            "service_fingerprint": broken_service_fingerprint,
        }
    )

    policy = ComparisonPolicy(
        min_cases=len(HIDDEN_CASES),
        min_improvement=0.25,
        expected_baseline_fingerprint=baseline_artifact_fingerprint,
    )

    baseline_eval = EvaluationSummary(
        program_id="invoice-repair-baseline",
        case_count=len(HIDDEN_CASES),
        aggregate_score=float(baseline_hidden["aggregate_score"]),
        hard_failures=0,
        validation_failures=int(baseline_hidden["failed_count"]),
        baseline_fingerprint=baseline_artifact_fingerprint,
        evaluation_protocol_fingerprint=protocol_fingerprint,
    )

    final_artifact = attempt["candidate_artifact"]
    candidate_eval = None
    if candidate_hidden is not None:
        candidate_eval = EvaluationSummary(
            program_id=str(final_artifact["candidate_id"]),
            case_count=len(HIDDEN_CASES),
            aggregate_score=float(candidate_hidden["aggregate_score"]),
            hard_failures=0,
            validation_failures=int(candidate_hidden["failed_count"]),
            baseline_fingerprint=baseline_artifact_fingerprint,
            evaluation_protocol_fingerprint=protocol_fingerprint,
        )

    promotion = decide_promotion(
        active=baseline_eval,
        candidate=candidate_eval,
        public_validation_passed=final_public_passed,
        policy=policy,
    )
    promotion_record = promotion.to_record()

    tool_surface = {
        "bound_root": str(fixture),
        "planner_visible_tools": [
            "search_repository(query)",
            "read_file(path, start_line, end_line)",
            "inspect_symbol(name)",
        ],
        "mutation_tools_exposed": False,
        "shell_tool_exposed": False,
        "network_tool_exposed": False,
        "hidden_validator_exposed": False,
    }
    tool_surface["tool_surface_fingerprint"] = fingerprint(tool_surface)

    provider_record = {
        "planner": active_planner.name,
        "dspy_version": _optional_distribution_version("dspy"),
        "notes": (
            "The deterministic planner uses no LM. The DSPy planner records "
            "model details in the proposal raw payload."
        ),
        "proposal_raw": plan.proposal.raw,
        "proposal_usage": plan.proposal.usage,
    }

    capstone_manifest = {
        "program_version": "evidence-repair-0.1.0",
        "fixture_fingerprint": fixture_fingerprint,
        "issue_fingerprint": fingerprint(ISSUE),
        "provider_record_fingerprint": fingerprint(provider_record),
        "tool_surface_fingerprint": tool_surface["tool_surface_fingerprint"],
        "development_validation_contract": (
            "public unittest gates candidate eligibility for independent evaluation"
        ),
        "independent_evaluation_protocol_fingerprint": protocol_fingerprint,
        "candidate_artifact_fingerprint": final_artifact[
            "candidate_artifact_fingerprint"
        ],
        "promotion_decision_fingerprint": promotion_record["fingerprint"],
        "repair_budget": {
            "max_repair_attempts": 1,
            "hidden_evaluation_reused_for_revision": False,
        },
        "source_revision": "invoice-fixture-v1",
    }
    manifest_guard = validate_manifest(capstone_manifest)

    hidden_executed = candidate_hidden is not None
    candidate_hidden_passed = (
        candidate_hidden is not None and candidate_hidden.get("passed") is True
    )

    invariants = {
        "broken_fixture_public_validation_fails": baseline_public["passed"] is False,
        "broken_fixture_hidden_validation_not_perfect": baseline_hidden["passed"]
        is False,
        "known_control_patch_passes_public_and_hidden": control["control_passed"],
        "planner_tool_surface_read_only": (
            not tool_surface["mutation_tools_exposed"]
            and not tool_surface["shell_tool_exposed"]
            and not tool_surface["network_tool_exposed"]
        ),
        "hidden_validator_not_exposed_to_planner": tool_surface[
            "hidden_validator_exposed"
        ]
        is False,
        "tool_audit_recorded": len(plan.tool_calls) > 0,
        "hidden_evaluation_only_after_final_public_pass": (
            not hidden_executed or final_public_passed
        ),
        "hidden_evaluation_not_used_for_revision": True,
        "promotion_decision_recorded": bool(promotion_record["fingerprint"]),
        "candidate_artifact_distinct_from_promotion_record": final_artifact[
            "candidate_artifact_fingerprint"
        ]
        != promotion_record["fingerprint"],
        "manifest_guard_passed": manifest_guard["passed"],
        "activation_not_automatic": True,
    }

    all_invariants_passed = all(invariants.values())

    summary = {
        "planner": active_planner.name,
        "fixture_fingerprint": fixture_fingerprint,
        "baseline_public_passed": baseline_public["passed"],
        "baseline_hidden_score": baseline_hidden["aggregate_score"],
        "control_patch_passed": control["control_passed"],
        "diagnosis": plan.proposal.diagnosis,
        "suspected_files": list(plan.proposal.suspected_files),
        "tool_call_count": len(plan.tool_calls),
        "attempt_count": len(attempts),
        "final_public_passed": final_public_passed,
        "candidate_hidden_executed": hidden_executed,
        "candidate_hidden_passed": candidate_hidden_passed,
        "candidate_hidden_score": (
            candidate_hidden["aggregate_score"] if candidate_hidden is not None else None
        ),
        "candidate_artifact": final_artifact,
        "promotion_decision": promotion_record,
        "activation_performed": False,
        "manifest_guard": manifest_guard,
        "all_invariants_passed": all_invariants_passed,
        "interpretation": (
            "The repair loop is valid whether or not the planner succeeds. "
            "Independent hidden evaluation runs only after public validation and "
            "is comparison evidence, not repair feedback. Promotion is recorded "
            "separately and activation is not automatic."
        ),
    }

    write_json(out / "provider.json", provider_record)
    write_json(out / "tool_surface.json", tool_surface)
    write_json(
        out / "tool_trajectory.json",
        {"tool_calls": plan.tool_calls, "proposal": plan.proposal.to_record()},
    )
    write_json(
        out / "baseline_validation.json",
        {"public": baseline_public, "independent_hidden": baseline_hidden},
    )
    write_json(out / "control_validation.json", control)
    write_json(out / "repair_attempts.json", attempts)
    write_json(out / "candidate_artifact.json", final_artifact)
    write_json(
        out / "independent_evaluation.json",
        {
            "protocol_fingerprint": protocol_fingerprint,
            "candidate_hidden": candidate_hidden,
            "baseline_evaluation": baseline_eval.to_record(),
            "candidate_evaluation": (
                candidate_eval.to_record() if candidate_eval is not None else None
            ),
        },
    )
    write_json(
        out / "promotion.json",
        {
            "policy": {
                "min_cases": policy.min_cases,
                "min_improvement": policy.min_improvement,
                "expected_baseline_fingerprint": policy.expected_baseline_fingerprint,
            },
            "decision": promotion_record,
            "activation_performed": False,
        },
    )
    write_json(out / "capstone_manifest.json", capstone_manifest)
    write_json(out / "manifest_guard.json", manifest_guard)
    write_json(out / "summary.json", summary)
    write_json(out / "invariants.json", invariants)
    (out / "analysis.md").write_text(
        _analysis_markdown(summary, invariants),
        encoding="utf-8",
    )
    write_json(
        out / "run.json",
        {
            "experiment": "evidence-repair",
            "experiment_version": "0.1.0",
            "status": "completed" if all_invariants_passed else "failed_invariant",
            "requires_lm": active_planner.name == "dspy",
            "measured": True,
            "planner": active_planner.name,
            "artifacts": {
                "provider": "provider.json",
                "tool_surface": "tool_surface.json",
                "tool_trajectory": "tool_trajectory.json",
                "baseline_validation": "baseline_validation.json",
                "control_validation": "control_validation.json",
                "repair_attempts": "repair_attempts.json",
                "candidate_artifact": "candidate_artifact.json",
                "independent_evaluation": "independent_evaluation.json",
                "promotion": "promotion.json",
                "capstone_manifest": "capstone_manifest.json",
                "manifest_guard": "manifest_guard.json",
                "summary": "summary.json",
                "invariants": "invariants.json",
                "analysis": "analysis.md",
            },
            "notes": (
                "Proposal, validation, promotion, and activation are separate "
                "records. Activation is deliberately not performed."
            ),
        },
    )

    if not all_invariants_passed:
        failed = [name for name, passed in invariants.items() if not passed]
        raise RuntimeError("Evidence Repair invariants failed: " + ", ".join(failed))

    return RunResult(out=out, summary=summary)
