# GhostQA v0.3.13 — Outcome C

harmful / unsafe

Inspected mechanism development on buggy-crm and buggy-ops. Not a fresh-generalization claim. Product default unchanged. v0.3.11 remains Outcome D. v0.3.12 remains Outcome C.

## Mechanism

| target | policy | budget | states | URLs | lost_parent | stack pushes | resumes | unwind | max depth | horizon | returns | escapes | confirmed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| buggy-crm | ghost-structural-nested-return-guard | 120 | 20 | 13 | 0 | 0 | 0 | 0 | 0 | 8 | 6 | 2 | BUG-C1,BUG-C2,BUG-C4,BUG-C5,BUG-C8 |
| buggy-crm | ghost-structural-nested-return-guard | 40 | 14 | 10 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | BUG-C2,BUG-C5 |
| buggy-crm | ghost-structural-nested-return-guard | 80 | 20 | 13 | 0 | 0 | 0 | 0 | 0 | 8 | 6 | 2 | BUG-C1,BUG-C2,BUG-C4,BUG-C5,BUG-C8 |
| buggy-crm | ghost-structural-nested-stack-guard | 120 | 5 | 5 | 0 | 80 | 0 | 0 | 80 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-nested-stack-guard | 40 | 5 | 5 | 0 | 27 | 0 | 0 | 27 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-nested-stack-guard | 80 | 5 | 5 | 0 | 53 | 0 | 0 | 53 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-return-guard | 120 | 5 | 5 | 80 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-return-guard | 40 | 5 | 5 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-crm | ghost-structural-return-guard | 80 | 5 | 5 | 53 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-nested-return-guard | 120 | 28 | 24 | 0 | 0 | 0 | 0 | 0 | 21 | 14 | 7 | BUG-O2,BUG-O5 |
| buggy-ops | ghost-structural-nested-return-guard | 40 | 15 | 12 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | BUG-O2,BUG-O5 |
| buggy-ops | ghost-structural-nested-return-guard | 80 | 23 | 19 | 0 | 0 | 0 | 0 | 0 | 14 | 10 | 4 | BUG-O2,BUG-O5 |
| buggy-ops | ghost-structural-nested-stack-guard | 120 | 5 | 5 | 0 | 79 | 0 | 0 | 79 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-nested-stack-guard | 40 | 5 | 5 | 0 | 25 | 0 | 0 | 25 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-nested-stack-guard | 80 | 5 | 5 | 0 | 52 | 0 | 0 | 52 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-return-guard | 120 | 5 | 5 | 79 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-return-guard | 40 | 5 | 5 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| buggy-ops | ghost-structural-return-guard | 80 | 5 | 5 | 52 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — |

## Regression

| target | v0.3.9 guard confirmed | v0.3.12 flatten confirmed | v0.3.13 stack confirmed | lost vs guard |
|---|---|---|---|---|
| buggy-desk | BUG-K1,BUG-K10,BUG-K2,BUG-K3,BUG-K5,BUG-K6,BUG-K9 | BUG-K1,BUG-K2,BUG-K4,BUG-K5 | BUG-K10,BUG-K3,BUG-K5,BUG-K6,BUG-K9 | BUG-K1,BUG-K2 |
| deepbench | BUG-D11,BUG-D12,BUG-D13,BUG-D14,BUG-D6,BUG-D7 | BUG-D11,BUG-D13,BUG-D14,BUG-D6,BUG-D7 | BUG-D12,BUG-D6 | BUG-D11,BUG-D13,BUG-D14,BUG-D7 |
| wiki | BUG-W2 | BUG-W2 | — | BUG-W2 |
| buggy-shop | BUG-W10,BUG-W5,BUG-W6,BUG-W9 | BUG-W10,BUG-W2,BUG-W5,BUG-W6,BUG-W9 | BUG-W10,BUG-W5,BUG-W6,BUG-W9 | — |

## Safety

| suite | cases/traces | failures |
|---|---:|---:|
| P1–P15 | 15 | 0 |
| S1–S7 | 7 | 0 |
| bounded return model | 5800 | 0 |

## Terminal accounting

violations: 0
return inflation: False
stack frame corruption: False
restore without child return: True

Product default changed: no

```text
python -m benchmark.nested_stack_reproduce --root experiments/published/nested-stack-v0.3.13 --verify
```
