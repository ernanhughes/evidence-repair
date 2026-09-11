"""DSPy planner implementation.

This module is imported only when the user asks for `--planner dspy`, so the
default package remains usable without installing DSPy or configuring an LM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .planners import RepairPlan, RepairProposal
from .tools import RepositoryTools, ToolAudit


def _require_dspy() -> Any:
    try:
        import dspy  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "DSPy is not installed. Install with: python -m pip install -e \".[dspy]\""
        ) from exc
    return dspy


def _signature_classes(dspy: Any) -> tuple[type, type]:
    class DiagnoseRepositoryRepair(dspy.Signature):
        """Diagnose the issue using only supplied read-only repository tools."""

        issue: str = dspy.InputField()
        constraints: str = dspy.InputField()

        diagnosis: str = dspy.OutputField()
        suspected_files: list[str] = dspy.OutputField()
        missing_evidence: str = dspy.OutputField()

    class GenerateRepair(dspy.Signature):
        """Propose one bounded file replacement.

        Return complete replacement contents for exactly one allowed file.
        Do not use markdown fences. Do not modify tests or models.
        """

        issue: str = dspy.InputField()
        diagnosis: str = dspy.InputField()
        repository_evidence: str = dspy.InputField()
        constraints: str = dspy.InputField()

        target_file: str = dspy.OutputField(
            desc="Repository-relative file to replace; must be service.py."
        )
        replacement_content: str = dspy.OutputField(
            desc="Complete Python contents for target_file, without markdown fences."
        )
        rationale: str = dspy.OutputField()
        expected_behavior_change: str = dspy.OutputField()

    return DiagnoseRepositoryRepair, GenerateRepair


def _history_len(lm: Any) -> int:
    history = getattr(lm, "history", None)
    return len(history) if isinstance(history, list) else 0


def _usage_from_history_slice(lm: Any, start: int) -> dict[str, Any]:
    history = getattr(lm, "history", None)
    if not isinstance(history, list):
        return {
            "history_entries": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

    rows = history[start:]
    result = {
        "history_entries": len(rows),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    saw_usage = False

    for row in rows:
        if not isinstance(row, Mapping):
            continue

        usage = row.get("usage")
        if not isinstance(usage, Mapping):
            response = row.get("response")
            if isinstance(response, Mapping):
                usage = response.get("usage")

        if not isinstance(usage, Mapping):
            continue

        saw_usage = True
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                result[key] += int(value)

    if not saw_usage:
        result["prompt_tokens"] = None
        result["completion_tokens"] = None
        result["total_tokens"] = None

    return result


def _strip_code_fences(text: str) -> str:
    value = text.strip()
    if not value.startswith("```"):
        return value

    lines = value.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)
    return (str(value),)


class DspyRepairPlanner:
    """DSPy-backed repair planner for the Evidence Repair contract."""

    name = "dspy"

    def __init__(
        self,
        *,
        model: str = "ollama_chat/qwen3:latest",
        api_base: str = "http://127.0.0.1:11434",
        api_key: str = "",
        temperature: float = 0.0,
        max_tokens: int = 512,
        cache: bool = False,
        react_max_iters: int = 6,
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = cache
        self.react_max_iters = react_max_iters

    def _configure_lm(self, dspy: Any) -> Any:
        lm = dspy.LM(
            model=self.model,
            api_base=self.api_base,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            cache=self.cache,
            think=False,
        )
        dspy.configure(lm=lm)
        return lm

    def propose(
        self,
        *,
        issue: str,
        constraints: str,
        repository: Path,
    ) -> RepairPlan:
        dspy = _require_dspy()
        DiagnoseRepositoryRepair, GenerateRepair = _signature_classes(dspy)
        lm = self._configure_lm(dspy)

        audit = ToolAudit(RepositoryTools(repository))
        diagnosis_program = dspy.ReAct(
            DiagnoseRepositoryRepair,
            tools=[
                audit.search_repository,
                audit.read_file,
                audit.inspect_symbol,
            ],
            max_iters=self.react_max_iters,
        )

        start_history = _history_len(lm)
        diagnosis_prediction = diagnosis_program(issue=issue, constraints=constraints)
        diagnosis_usage = _usage_from_history_slice(lm, start_history)

        evidence = {
            "tool_calls": audit.calls,
            "note": (
                "This evidence packet contains only planner-visible read-only "
                "tool observations. Hidden validation is not included."
            ),
        }

        start_history = _history_len(lm)
        repair_prediction = dspy.Predict(GenerateRepair)(
            issue=issue,
            diagnosis=str(getattr(diagnosis_prediction, "diagnosis", "")),
            repository_evidence=str(evidence),
            constraints=constraints,
        )
        repair_usage = _usage_from_history_slice(lm, start_history)

        usage = {
            "diagnosis": diagnosis_usage,
            "repair": repair_usage,
            "history_entries": (
                (diagnosis_usage.get("history_entries") or 0)
                + (repair_usage.get("history_entries") or 0)
            ),
            "total_tokens": (
                (diagnosis_usage.get("total_tokens") or 0)
                + (repair_usage.get("total_tokens") or 0)
            ),
        }

        proposal = RepairProposal(
            diagnosis=str(getattr(diagnosis_prediction, "diagnosis", "")).strip(),
            suspected_files=_as_tuple(
                getattr(diagnosis_prediction, "suspected_files", ())
            ),
            missing_evidence=str(
                getattr(diagnosis_prediction, "missing_evidence", "")
            ).strip(),
            target_file=str(getattr(repair_prediction, "target_file", "")).strip(),
            replacement_content=_strip_code_fences(
                str(getattr(repair_prediction, "replacement_content", ""))
            ),
            rationale=str(getattr(repair_prediction, "rationale", "")).strip(),
            expected_behavior_change=str(
                getattr(repair_prediction, "expected_behavior_change", "")
            ).strip(),
            generator="DspyRepairPlanner",
            usage=usage,
            raw={
                "model": self.model,
                "api_base": self.api_base,
                "react_max_iters": self.react_max_iters,
            },
        )

        return RepairPlan(proposal=proposal, tool_calls=audit.calls)
