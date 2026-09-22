# GhostQA v0.3.13 — regression mechanism analysis

This document records why v0.3.12 Outcome C lost child-local discoveries. It is derived by `benchmark.nested_stack_regression` from committed traces. The suspended-parent candidate is not in this commit. v0.3.12 remains Outcome C. The product default is unchanged.

Date: 2026-09-23
Starting HEAD: `23a5e3688433bfc532abc578ec919083368db604`

Regenerate the artifact with:

```text
python -m benchmark.nested_stack_regression
```

The committed file is `experiments/validation/v0.3.13/regression-analysis.json`.

## BuggyDesk anchor

Policies at budget 120, seed 1:

- reference: `ghost-structural-return-guard` from `experiments/published/fresh-transfer-v0.3.10`
- candidate: `ghost-structural-nested-return-guard` from `experiments/published/nested-hub-parent-v0.3.12`

Alignment uses the normalized URL and the action, because state signatures differ across runs.

The traces share a prefix of 3 actions:

```text
index -> tickets -> ticket?id=1001 -> customer?id=c1
```

The first divergence is step 3, still on `customer.html?id=c1`:

| trace | action | pre-action commitment | returning |
|---|---|---:|---|
| v0.3.9 guard | `nav_activity` | 2 | false |
| v0.3.12 flatten | `nav_back_customers` | 0 | true |

The nested branch click is the previous step, `ticket.html?id=1001` `nav_customer_c1`, with outer commitment 1.

The guard emits `lost_parent` and `branch_start`. After that click the active branch is the new child and commitment is `BRANCH_HORIZON - 1` (2). That is a child commitment reset.

The v0.3.12 candidate emits `nested_branch_followup` and does not emit `branch_start`. The outer branch is unchanged, commitment falls from 1 to 0, and the sequence enters returning. That is outer commitment consumption. The next choice is an outer return, so the child-local `nav_activity` follow-up never runs.

Reference-only URLs include `/activity.html?id=c2`, `/customer.html?id=c2`, `/ticket.html?id=1002`, `/ticket.html?id=1003`, `/article.html?id=a2`, and `/article.html?id=a3`. Candidate-only URLs are `/settings.html`, `/help.html`, and `/handbook.html`.

Lost reference findings, first matching step in the guard trace, absent from the candidate trace:

| bug | guard step | action |
|---|---:|---|
| BUG-K3 | 36 | `btn_watch` on `ticket.html?id=1003` |
| BUG-K6 | 37 | `btn_pause_sla` on `ticket.html?id=1003` |
| BUG-K9 | 39 | `btn_reopen` on `ticket.html?id=1003` |
| BUG-K10 | 57 | `nav_activity` on `customer.html?id=c1` |

## DeepBench

BUG-D12 is "移除成员后计数未更新", assert `member_count_consistent`, prerequisites `login`, `project`, `add-member`, `remove`, trigger depth 9. The v0.3.9 guard metrics confirm it. The v0.3.12 candidate metrics do not.

The published v0.3.9 deepbench directory has metrics and no event trace, so this is not a step-aligned proof. In the candidate sequence trace, `btn_add_alice` is recorded eight times as `nested_branch_followup` on an open `btn_members` instance. `commitment_left_before` alternates 2 then 1. `btn_add_alice` never emits `branch_start`. That is the same flattening pattern as BuggyDesk: a child-local action spends the outer commitment. It is consistent with losing the add/remove workflow. It is not proof that flattening is the only reason D12 is missing.

## What v0.3.13 asks

Nested branch starts should keep ordinary child-sequence semantics. The outer frame is suspended and restored only after the child returns to its own parent. Flattening the child into the outer commitment, and discarding the outer frame, are the two behaviors this round is trying to replace.

## Protocol

`experiments/validation/v0.3.13/protocol.json` is preregistered with `executed: false`. The candidate identity is `ghost-structural-nested-stack-guard`. It does not replace the v0.3.12 flattening identity. The mechanism matrix is CRM and Ops, policies G/F/S, budgets 40/80/120, seed 1, 18 cells. Regression cells are BuggyDesk, DeepBench, Wiki, and BuggyShop at 120 for the stack candidate only. No target evaluation happens before the protocol commit and the later candidate-freeze commit. Product default stays NoFrontier with `sequence_mode=off`.
