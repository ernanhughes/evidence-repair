# Evidence artifacts

Generated run artifacts are written under `.artifacts/evidence-repair/` and ignored by git.

The default command is:

```powershell
evidence-repair run --out .artifacts\evidence-repair\demo --overwrite
```

## Artifact contract

| artifact | meaning |
| --- | --- |
| `provider.json` | Planner type, DSPy version if installed, and planner metadata. |
| `tool_surface.json` | The tool boundary visible to the planner. |
| `tool_trajectory.json` | Tool calls and proposal data used during repair generation. |
| `baseline_validation.json` | Public and hidden behavior of the broken baseline. |
| `control_validation.json` | Known-good repair proving the harness can recognize success. |
| `repair_attempts.json` | Candidate proposal, application result, and public validation. |
| `candidate_artifact.json` | Fingerprinted candidate record. |
| `independent_evaluation.json` | Hidden evaluation summaries used for comparison. |
| `promotion.json` | Promotion policy, decision, and activation status. |
| `capstone_manifest.json` | Run identity and evidence-boundary manifest. |
| `manifest_guard.json` | Manifest completeness and forbidden-field check. |
| `summary.json` | Small top-level outcome summary. |
| `invariants.json` | Boolean checks that make the run interpretable. |
| `analysis.md` | Human-readable summary of the run. |
| `run.json` | Machine-readable run index. |

## Interpretation

A candidate may fail and the run can still be useful. Evidence Repair treats repair quality as an outcome, not a structural invariant.

The run becomes invalid when the evidence boundary fails: hidden evidence leaks into repair generation, mutation tools are exposed to the planner, the candidate artifact is conflated with the promotion decision, or activation happens automatically.
