# GhostQA v0.3.12 — Nested-Hub Parent Preservation

**Outcome C — harmful/regression** (computed from the preregistered gates).

Product default unchanged: NoFrontier, `sequence_mode=off`.
Generalization claim: no.

CRM and Ops are inspected mechanism-development cases from the frozen v0.3.11 suite. A repair here is not a fresh-generalization result.

## Historical preemption

The v0.3.11 guard never reached return on CRM or Ops because an open sequence was terminated `lost_parent` at the next hub branch click, before horizon. Wiki reached horizon and return.

| target | G branch starts | G lost_parent | G horizon | G return attempts | G states | G URLs |
|---|---:|---:|---:|---:|---:|---:|
| buggy-crm | 81 | 80 | 0 | 0 | 5 | 5 |
| buggy-ops | 80 | 79 | 0 | 0 | 5 | 5 |

## Mechanism @120

| target | policy | states | URLs | lost_parent | nested-followup | horizon | return attempts | returned | escapes | confirmed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| buggy-crm | ghost-structural-memory | 5 | 5 | 80 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-return-guard | 5 | 5 | 80 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-nested-return-guard | 20 | 13 | 0 | 5 | 8 | 14 | 6 | 2 | BUG-C1, BUG-C2, BUG-C4, BUG-C5, BUG-C8 |
| buggy-ops | ghost-structural-memory | 5 | 5 | 79 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-return-guard | 5 | 5 | 79 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-nested-return-guard | 28 | 24 | 0 | 18 | 21 | 30 | 14 | 7 | BUG-O2, BUG-O5 |

## Candidate timeline @120

| target | first follow-up | first horizon after | first return | first escape | first novel state | first novel URL |
|---|---:|---:|---:|---:|---:|---|
| buggy-crm | 1 | 2 | 3 | 41 | 1 | /account.html?id=a1 |
| buggy-ops | 2 | 2 | 3 | 43 | 2 | /incidents.html?service=svc1 |

## Regression @120

| target | guard confirmed | candidate confirmed | lost |
|---|---|---|---|
| wiki | BUG-W2 | BUG-W2 | — |
| buggy-desk | BUG-K1, BUG-K10, BUG-K2, BUG-K3, BUG-K5, BUG-K6, BUG-K9 | BUG-K1, BUG-K2, BUG-K4, BUG-K5 | BUG-K10, BUG-K3, BUG-K6, BUG-K9 |
| buggy-shop | BUG-W10, BUG-W5, BUG-W6, BUG-W9 | BUG-W10, BUG-W2, BUG-W5, BUG-W6, BUG-W9 | — |
| deepbench | BUG-D11, BUG-D12, BUG-D13, BUG-D14, BUG-D6, BUG-D7 | BUG-D11, BUG-D13, BUG-D14, BUG-D6, BUG-D7 | BUG-D12 |

| target | states | URLs | BDR | return attempts | returned | escapes | nested follow-up | lost_parent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| wiki | 23 | 16 | 0.111 | 52 | 20 | 2 | 5 | 0 |
| buggy-desk | 23 | 16 | 0.4 | 16 | 6 | 2 | 4 | 0 |
| buggy-shop | 17 | 9 | 0.5 | 7 | 2 | 1 | 3 | 0 |
| deepbench | 26 | 8 | 0.357 | 38 | 16 | 0 | 13 | 0 |

## Safety

| suite | cases/traces | failures |
|---|---:|---:|
| N1-N12 | 12 | 0 |
| S1-S7 | 7 | 0 |
| bounded return model | 5800 | 0 |

Guard exhaustive traces 5800, failures 0.
Differential failures: 0.

## Gate

CRM mechanism repair: True. Ops mechanism repair: True. Historical preemption reproduced: True.
Confirmed-bug loss: buggy-desk, deepbench.
N1–N12, S1–S7, and the bounded return model are in the safety table. Outcome C means this candidate is not advanced.

## Scope

CRM and Ops were already inspected. The lifecycle change is visible there, and it is not a fresh-generalization result. Confirmed bugs were lost on the historical regression cases listed above. Do not ship this candidate as the default, and do not treat it as transfer-ready.
