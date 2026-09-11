# Architecture

Evidence Repair has two halves:

- a probabilistic planner that can inspect allowed evidence and propose a candidate repair;
- deterministic governance code that applies, validates, evaluates, compares, and records the candidate.

The boundary is the design.

## Components

```text
fixture repository
  -> RepositoryTools
  -> planner
  -> RepairProposal
  -> isolated candidate workspace
  -> syntax gate
  -> scope gate
  -> public validation
  -> independent hidden validation
  -> EvaluationSummary
  -> PromotionRecord
  -> artifacts
```

## Planner boundary

The planner receives:

- the issue;
- constraints;
- read-only repository search;
- bounded file reads;
- symbol inspection.

The planner does not receive:

- mutation access;
- shell access;
- network access;
- hidden validation cases;
- promotion metadata;
- activation authority.

`src/evidence_repair/dspy_programs.py` contains the DSPy signatures and planner. `src/evidence_repair/planners.py` contains the deterministic planner used for local verification.

## Candidate boundary

The first implementation uses full-file replacement for one allowed file:

```text
allowed patch files = {"service.py"}
```

That keeps the initial patch model small enough to audit. A future version can add unified diffs, multi-file changes, or real repository adapters after the artifact format is stable.

## Evaluation boundary

Public development validation can decide whether a candidate is eligible for independent evaluation.

Independent hidden evaluation is comparison evidence only. It must not become repair feedback.

## Promotion boundary

Promotion is a record with a decision and reason:

```text
PROMOTE / REJECT / INSUFFICIENT
```

Activation is not performed by this project. A downstream operator or deployment system can use the promotion record as evidence, but the record is not itself a deployment.
