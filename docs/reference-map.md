# Evidence Repair reference map

This repository is the standalone implementation surface for the `DSPy From First Principles` capstone.

## Public references

| reference | URL |
| --- | --- |
| Book | https://programmer.ie/books/dspy-from-first-principles/ |
| Capstone chapter | https://programmer.ie/books/dspy-from-first-principles/20-chapter/ |
| Solution page | https://programmer.ie/solutions/self-improving-engineering-program/ |
| Original book experiments | https://github.com/ernanhughes/next-books/tree/main/experiments/dspy-from-first-principles |
| Evidence Repair implementation | https://github.com/ernanhughes/evidence-repair |

## Repository map

| path | purpose |
| --- | --- |
| `src/evidence_repair/fixtures.py` | Builds the invoice fixture and defines public issue/constraints. |
| `src/evidence_repair/tools.py` | Read-only repository tools and the tool-call audit wrapper. |
| `src/evidence_repair/dspy_programs.py` | DSPy signatures and `DspyRepairPlanner`. |
| `src/evidence_repair/planners.py` | Planner protocol, proposal records, and deterministic planner. |
| `src/evidence_repair/validation.py` | Patch application, public tests, hidden evaluation, and control patch. |
| `src/evidence_repair/promotion.py` | Independent comparison policy and promotion records. |
| `src/evidence_repair/pipeline.py` | End-to-end run orchestration and artifact writing. |
| `docs/architecture.md` | System architecture and evidence boundary. |
| `evidence/README.md` | Explanation of generated evidence artifacts. |
| `tests/` | Local verification that avoids live LM calls. |

## Publishing loop

```text
book argument
  -> chapter 20 capstone experiment
  -> tracked solution page
  -> standalone implementation repo
  -> generated evidence artifacts
  -> future examples and evaluations
```

The implementation should remain narrower than the name sounds. Its job is not to claim general autonomous repair. Its job is to make repair proposals inspectable under explicit evidence and promotion boundaries.
