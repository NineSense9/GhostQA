# GhostQA v0.3.14 — Outcome A

Horizon Handoff repairs the inspected nested-boundary mechanism and passes the specified historical regression suite

Inspected mechanism development on buggy-crm and buggy-ops. Not a fresh-generalization claim. Product default unchanged. v0.3.11 remains Outcome D. v0.3.12 remains Outcome C. v0.3.13 remains Outcome C.

## Mechanism

| target | G states/URLs | F states/URLs | S states/URLs | H states/URLs | continuations | handoffs | witnesses | resumes | unwinds | max depth | horizon | return | confirmed |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| buggy-crm@40 | — | — | — | 13/10 | 5 | 2 | 2 | 2 | 0 | 1 | 8 | 8 | BUG-C2,BUG-C5 |
| buggy-crm@80 | — | — | — | 20/13 | 5 | 2 | 2 | 2 | 0 | 1 | 10 | 8 | BUG-C1,BUG-C2,BUG-C4,BUG-C5,BUG-C8 |
| buggy-crm | 5/5 | 20/13 | 5/5 | 20/13 | 5 | 2 | 2 | 2 | 0 | 1 | 10 | 8 | BUG-C1,BUG-C2,BUG-C4,BUG-C5,BUG-C8 |
| buggy-ops@40 | — | — | — | 15/15 | 4 | 3 | 2 | 2 | 1 | 2 | 8 | 5 | — |
| buggy-ops@80 | — | — | — | 27/24 | 8 | 4 | 2 | 2 | 2 | 2 | 12 | 9 | BUG-O2,BUG-O5 |
| buggy-ops | 5/5 | 28/24 | 5/5 | 28/25 | 13 | 7 | 4 | 4 | 3 | 2 | 19 | 12 | BUG-O2,BUG-O5 |
| buggy-desk | 35/19 | 23/16 | 23/13 | 33/20 | 4 | 2 | 1 | 1 | 1 | 1 | 11 | 5 | BUG-K1,BUG-K10,BUG-K2,BUG-K3,BUG-K4,BUG-K5,BUG-K6,BUG-K9 |
| deepbench | 28/— | 26/8 | 68/6 | 23/8 | 8 | 2 | 2 | 2 | 0 | 2 | 14 | 14 | BUG-D11,BUG-D12,BUG-D13,BUG-D14,BUG-D6,BUG-D7 |
| wiki | 23/16 | 23/16 | 33/14 | 24/16 | 4 | 1 | 1 | 1 | 0 | 1 | 23 | 21 | BUG-W2 |
| buggy-shop | 22/8 | 17/9 | 22/8 | 22/8 | 0 | 4 | 0 | 0 | 4 | 1 | 0 | 0 | BUG-W10,BUG-W5,BUG-W6,BUG-W9 |

## Regression

| target | guard confirmed | v0.3.12 | v0.3.13 | v0.3.14 | lost vs guard |
|---|---|---|---|---|---|
| buggy-desk | BUG-K1,BUG-K10,BUG-K2,BUG-K3,BUG-K5,BUG-K6,BUG-K9 | BUG-K1,BUG-K2,BUG-K4,BUG-K5 | BUG-K10,BUG-K3,BUG-K5,BUG-K6,BUG-K9 | BUG-K1,BUG-K10,BUG-K2,BUG-K3,BUG-K4,BUG-K5,BUG-K6,BUG-K9 | — |
| deepbench | BUG-D11,BUG-D12,BUG-D13,BUG-D14,BUG-D6,BUG-D7 | BUG-D11,BUG-D13,BUG-D14,BUG-D6,BUG-D7 | BUG-D12,BUG-D6 | BUG-D11,BUG-D12,BUG-D13,BUG-D14,BUG-D6,BUG-D7 | — |
| wiki | BUG-W2 | BUG-W2 | — | BUG-W2 | — |
| buggy-shop | BUG-W10,BUG-W5,BUG-W6,BUG-W9 | BUG-W10,BUG-W2,BUG-W5,BUG-W6,BUG-W9 | BUG-W10,BUG-W5,BUG-W6,BUG-W9 | BUG-W10,BUG-W5,BUG-W6,BUG-W9 | — |

## v0.3.13 restore re-audit

The corrected join does not change the published v0.3.13 Outcome C.

| target | resumes | old bad restore | same-step terminal witness | corrected residual |
|---|---:|---:|---:|---:|
| buggy-crm | 0 | 0 | 0 | 0 |
| buggy-desk | 28 | 1 | 1 | 0 |
| buggy-ops | 0 | 0 | 0 | 0 |
| buggy-shop | 0 | 0 | 0 | 0 |
| deepbench | 44 | 33 | 33 | 0 |
| wiki | 16 | 0 | 16 | 0 |

## Safety

| suite | cases/traces | failures |
|---|---:|---:|
| H1–H20 | 20 | 0 |
| handoff model raw traces | 19607 | 0 |
| S1–S7 | 7 | 0 |
| historical return model | 5800 | 0 |
| N1–N12 historical | 12 | 0 |
| P1–P15 historical | 15 | 0 |

witness violations: 0
terminal accounting violations: 0

Product default changed: no

```text
python -m benchmark.horizon_handoff_reproduce --root experiments/published/horizon-handoff-v0.3.14 --verify
```
