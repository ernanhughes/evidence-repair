"""Command line interface for Evidence Repair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_repair_loop
from .planners import HeuristicRepairPlanner, RepairPlanner


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence-repair",
        description="Run a repository-repair loop with explicit evidence boundaries.",
    )

    subparsers = parser.add_subparsers(dest="command")
    run = subparsers.add_parser("run", help="run the invoice repair evidence loop")
    run.add_argument(
        "--out",
        type=Path,
        default=Path(".artifacts/evidence-repair/demo"),
        help="directory for generated evidence artifacts",
    )
    run.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the output directory if it already exists",
    )
    run.add_argument(
        "--planner",
        choices=("heuristic", "dspy"),
        default="heuristic",
        help="repair planner to use",
    )
    run.add_argument(
        "--model",
        default="ollama_chat/qwen3:latest",
        help="DSPy model string used with --planner dspy",
    )
    run.add_argument(
        "--api-base",
        default="http://127.0.0.1:11434",
        help="DSPy provider base URL used with --planner dspy",
    )
    run.add_argument(
        "--api-key",
        default="",
        help="DSPy provider API key used with --planner dspy",
    )
    run.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="DSPy model temperature used with --planner dspy",
    )
    run.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="DSPy maximum tokens used with --planner dspy",
    )
    return parser


def _planner_from_args(args: argparse.Namespace) -> RepairPlanner:
    if args.planner == "heuristic":
        return HeuristicRepairPlanner()

    from .dspy_programs import DspyRepairPlanner

    return DspyRepairPlanner(
        model=args.model,
        api_base=args.api_base,
        api_key=args.api_key,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        args = parser.parse_args(["run", *(argv or [])])

    result = run_repair_loop(
        out=args.out,
        planner=_planner_from_args(args),
        overwrite=args.overwrite,
    )

    print(
        json.dumps(
            {
                "out": str(result.out),
                "planner": result.summary["planner"],
                "final_public_passed": result.summary["final_public_passed"],
                "candidate_hidden_score": result.summary["candidate_hidden_score"],
                "promotion_decision": result.summary["promotion_decision"]["decision"],
                "activation_performed": result.summary["activation_performed"],
            },
            indent=2,
        )
    )
