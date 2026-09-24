# v0.3.23 residual frontier debt escape

Inspected repair round. It is not fresh validation and it does not change the product default.

The audit file `v0322-residual-debt-audit.json` is computed by:

```
.\.venv\Scripts\python.exe -m benchmark.residual_frontier_debt_audit
```

It reads the committed v0.3.21 and v0.3.22 publications, hydrates each runtime `StateGraph`, and applies `pending_opportunity_counts`. It does not read frozen target topology and it does not import the v0.3.23 candidate.

Computed b480 sink, using stored-action edges and ignoring `CRASHED`:

| target | SCC size | closed | outgoing | pending interactions | template 5/8/9 through b480 |
|---|---:|---:|---:|---:|---|
| buggy-campus | 2 | true | 0 | 0 | missing |
| buggy-studio | 3 | true | 0 | 0 | missing |
| buggy-warehouse | 40 | true | 0 | 77 | retained, later organic residual use |
| buggy-booking | 40 | true | 0 | 77 | retained, later organic residual use |

Campus and Studio sinks are closed and interaction-exhausted. Warehouse and Booking sinks stay interaction-open in the pending-opportunity sense: the observed component has no outgoing edge, and it still has pending interactions. The first v0.3.21 waypoint escape on each positive target is the only debt source this round is allowed to restore.

`protocol.json` is preregistered with `executed: false` before any v0.3.23 candidate cell.
