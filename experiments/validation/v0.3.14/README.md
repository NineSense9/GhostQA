# GhostQA v0.3.14 — v0.3.13 restore re-audit

This directory records a measurement correction for the published v0.3.13 metric `restore_without_child_return`. It does not rewrite `experiments/published/nested-stack-v0.3.13`. That round remains Outcome C.

Date: 2026-09-23
Starting HEAD: `202abe12310f30e552fbff5317e593682f60a726`

Regenerate the artifact with:

```text
python -m benchmark.v0313_restore_reaudit --write experiments/validation/v0.3.14/v0313-restore-reaudit.json
```

## Old detector

`benchmark.nested_stack_analysis.stack_audit` accepts a `parent_frame_resumed` event when the same child has either:

- a same-step `sequence_terminal` with outcome `returned`, or
- a prior-step `sequence_terminal` with outcome `finding` or `crash`.

It does not accept a same-step finding or crash, even when that same call also matches the recorded child parent and historical return completion clears the child.

## Corrected join

For each resume, repository code reads the committed sequence trace and the browser step with the same index.

A resume has evidence when all of the following hold:

- the child id and branch match that child's `branch_start`
- the browser destination equals the recorded child parent exact signature, or the destination cluster equals the recorded child parent cluster
- no same-step `return_cycle_escape` invalidates the resolution
- historical return completion is visible as a same-step `returned` terminal, a same-step finding, a same-step crash, or a prior finding/crash together with the physical parent match

A change in a global return counter is not evidence.

## Budget 120 stack traces

| target | resumes | old bad restore | same-step finding | same-step crash | same-step returned | corrected residual |
|---|---:|---:|---:|---:|---:|---:|
| buggy-crm | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-desk | 28 | 1 | 1 | 0 | 0 | 0 |
| buggy-ops | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-shop | 0 | 0 | 0 | 0 | 0 | 0 |
| deepbench | 44 | 33 | 33 | 0 | 0 | 0 |
| wiki | 16 | 0 | 0 | 0 | 16 | 0 |

BuggyDesk's one old failure is step 65, child `seq-0021`: a same-step finding whose destination is the recorded parent exact signature. DeepBench's 33 old failures are same-step findings whose destination cluster matches the recorded parent and whose exact signature is a same-page variant. Wiki's 16 resumes already had same-step `returned` terminals, so the old detector accepted them. Corrected residual bad restores are 0 on every published stack trace, including CRM and Ops at 40, 80, and 120.

## v0.3.13 stays Outcome C

Recomputing `derive_v0313_outcome` with `restore_without_child_return=false` and the other published gate inputs is still Outcome C.

The round is not promotable because:

- `crm_repair` is false
- `ops_repair` is false
- guard-confirmed losses remain: BuggyDesk `BUG-K1` `BUG-K2`, DeepBench `BUG-D11` `BUG-D13` `BUG-D14` `BUG-D7`, Wiki `BUG-W2`

Those losses are additional to the v0.3.12 loss set, so the v0.3.13 harmful gate stays true. The measurement erratum does not make the suspended-parent candidate safe or successful.
