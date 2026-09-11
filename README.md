# evidence-repair

Evidence Repair is a small DSPy-oriented repository-repair loop.

It starts from the capstone experiment in **DSPy From First Principles** and turns it into a reusable implementation surface: a language-model program can diagnose and propose a repair, while deterministic software controls tools, patch application, validation, independent evaluation, promotion, and activation boundaries.

The project is intentionally modest on day one. It includes a runnable deterministic planner so the evidence machinery can be tested anywhere, plus a DSPy planner path for running the same contract with a configured model.

## Public reference map

- Book: [DSPy From First Principles](https://programmer.ie/books/dspy-from-first-principles/)
- Capstone chapter: [Build a Self-Improving Engineering Program](https://programmer.ie/books/dspy-from-first-principles/20-chapter/)
- Solution page: [Self-Improving Engineering Program](https://programmer.ie/solutions/self-improving-engineering-program/)
- Original experiment source: [next-books/experiments/dspy-from-first-principles](https://github.com/ernanhughes/next-books/tree/main/experiments/dspy-from-first-principles)
- This implementation: [ernanhughes/evidence-repair](https://github.com/ernanhughes/evidence-repair)
- Reference map: [docs/reference-map.md](docs/reference-map.md)

There is not yet a separate DSPy blog post for this project. When one exists, add it to the reference map rather than scattering links through the code.

## What it does

Evidence Repair runs a repository-repair experiment with explicit evidence boundaries:

```text
issue
  -> bounded repository inspection
  -> diagnosis
  -> candidate replacement
  -> isolated patch application
  -> syntax and scope gates
  -> public development validation
  -> independent hidden evaluation when eligible
  -> comparison with active baseline
  -> promotion recommendation
  -> no automatic activation
```

The default fixture is deliberately tiny. `invoice_total` ignores quantity, public tests expose the problem, and hidden cases check whether a candidate generalizes beyond the visible test.

The important part is not that this example is hard. The important part is that the system records what the repair program saw, what it changed, which gates it passed, which evidence stayed independent, and why a candidate did or did not earn promotion.

## Install

```powershell
python -m pip install -e ".[dev]"
```

To run the DSPy planner path, install the optional DSPy extra:

```powershell
python -m pip install -e ".[dev,dspy]"
```

Local verification used Python 3.13 for the deterministic path and Python 3.11 for the live DSPy/Ollama path. If a Python 3.13 environment has a broken NumPy wheel, use a Python 3.11 or 3.12 virtual environment for DSPy runs.

## Run the deterministic path

```powershell
evidence-repair run --out .artifacts\evidence-repair\demo --overwrite
```

This path uses a deterministic planner that performs the same bounded repository inspection and proposes the known quantity repair. It is the fastest way to inspect the evidence loop.

Expected summary:

```text
baseline public validation: failed
baseline hidden score: 0.5
candidate public validation: passed
candidate hidden score: 1.0
promotion decision: PROMOTE
activation performed: false
```

## Run the DSPy path

Start a model provider, then run:

```powershell
evidence-repair run `
  --planner dspy `
  --model ollama_chat/qwen3:latest `
  --api-base http://127.0.0.1:11434 `
  --out .artifacts\evidence-repair\dspy `
  --overwrite
```

The DSPy planner defines two signatures:

- `DiagnoseRepositoryRepair`: use read-only repository tools to diagnose the issue.
- `GenerateRepair`: produce one complete replacement for the allowed file.

The LM-visible tool surface is deliberately read-only:

- `search_repository(query)`
- `read_file(path, start_line, end_line)`
- `inspect_symbol(name)`

The model never receives a mutation tool, shell access, network access, or the hidden evaluator.

## Artifact files

Each run writes:

```text
analysis.md
baseline_validation.json
candidate_artifact.json
capstone_manifest.json
control_validation.json
independent_evaluation.json
invariants.json
manifest_guard.json
promotion.json
repair_attempts.json
run.json
summary.json
tool_surface.json
tool_trajectory.json
```

Generated artifacts live under `.artifacts/`, which is ignored by git.

## Development

```powershell
python -m pytest
python -m evidence_repair run --out .artifacts\evidence-repair\demo --overwrite
```

The tests avoid live LM calls. They check the fixture, path boundaries, deterministic validation, artifact writing, and promotion behavior.

## Design rule

Evidence Repair keeps four operations separate:

```text
proposal != validation != promotion != activation
```

That is the core idea from the book. DSPy is useful because it gives the probabilistic repair behavior a contract. The surrounding software is what makes the improvement claim inspectable.
