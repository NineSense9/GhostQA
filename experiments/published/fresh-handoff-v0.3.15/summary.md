# GhostQA v0.3.15 — Outcome C

validation failed or protocol invalid

Static qualification, actual evaluability, and full transfer are different claims. A qualified graph only says the declared structure is relevant. It does not mean a policy reached that structure, and it does not mean full transfer. This round is not universal generalization and it does not change the product default.

Promotion readiness: `not_ready`.

Product default changed: no

## Static qualification

| target | qualified | chain count | max nested chain | roles |
|---|---:|---:|---:|---|
| buggy-forum | True | 2 | 8 | moderation_resolution, report_triage |
| buggy-billing | True | 2 | 7 | payment_capture, refund_escape |
| buggy-lab | True | 2 | 8 | comparison_notebook, sample_observation |
| buggy-directory | False | 0 | 2 | — |

## Budget 120

| target | policy | states | URLs | confirmed | lost_parent | horizon | return attempts | returned | escapes | continuations | handoffs | witnesses | unwinds | max depth |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| buggy-forum | C1 | 14 | 11 | BUG-F2 | 11 | 0 | 88 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-forum | G | 17 | 14 | BUG-F2 | 43 | 0 | 22 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| buggy-forum | H | 20 | 15 | BUG-F1,BUG-F2,BUG-F4 | 0 | 11 | 49 | 8 | 6 | 14 | 11 | 10 | 1 | 1 |
| buggy-billing | C1 | 12 | 8 | BUG-B2 | 2 | 0 | 107 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-billing | G | 19 | 13 | BUG-B2,BUG-B9 | 11 | 0 | 28 | 0 | 11 | 0 | 0 | 0 | 0 | 0 |
| buggy-billing | H | 25 | 15 | BUG-B1,BUG-B2,BUG-B4,BUG-B9 | 0 | 5 | 30 | 4 | 6 | 6 | 6 | 4 | 2 | 1 |
| buggy-lab | C1 | 18 | 12 | BUG-L10,BUG-L2,BUG-L8 | 4 | 0 | 94 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-lab | G | 24 | 16 | BUG-L1,BUG-L10,BUG-L2,BUG-L8,BUG-L9 | 14 | 0 | 51 | 0 | 7 | 0 | 0 | 0 | 0 | 0 |
| buggy-lab | H | 18 | 11 | BUG-L2,BUG-L4,BUG-L5,BUG-L6 | 0 | 11 | 46 | 5 | 7 | 5 | 11 | 10 | 1 | 2 |
| buggy-directory | C1 | 11 | 8 | BUG-DIR1,BUG-DIR8 | 2 | 1 | 101 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| buggy-directory | G | 20 | 10 | BUG-DIR1,BUG-DIR4,BUG-DIR5,BUG-DIR6,BUG-DIR7,BUG-DIR8 | 4 | 2 | 24 | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| buggy-directory | H | 20 | 10 | BUG-DIR1,BUG-DIR4,BUG-DIR5,BUG-DIR6,BUG-DIR7,BUG-DIR8 | 0 | 4 | 26 | 4 | 2 | 0 | 2 | 2 | 0 | 1 |

## Transfer

| target | static qualified | actual evaluable | full transfer | lost vs guard |
|---|---:|---:|---:|---|
| buggy-forum | True | True | True | — |
| buggy-billing | True | True | True | — |
| buggy-lab | True | True | False | BUG-L1, BUG-L10, BUG-L8, BUG-L9 |

## Negative control

H handoffs: 2
H witnesses: 2
H resumes: 2
max depth: 1
lost vs guard: —

## Aggregate

- static positive targets = 3
- actually evaluable targets = 3
- full transfer targets = 2
- guard bug losses = buggy-lab
- negative-control handoffs = 2
- witness violations = 0
- terminal violations = 0
- Outcome = C
- promotion_readiness = not_ready
- Product default changed: no

```text
python -m benchmark.fresh_handoff_reproduce --root experiments/published/fresh-handoff-v0.3.15 --verify
```
