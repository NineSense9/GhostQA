# v0.3.24 episode-scoped local drain revalidation

Inspected repair round. It is not fresh validation and it does not change the product default.

The audit file `v0323-episode-drain-audit.json` is computed by:

```
.\.venv\Scripts\python.exe -m benchmark.episode_drain_epoch_audit
```

It reads the committed v0.3.23 publication at budget 120, seed 1. It does not import a v0.3.24 candidate and it does not rerun exploration.

Computed from that publication:

| target | debt relocations | executor reset | pre-reset same-hub probes | later same-hub witness starts a new drain | template 9 |
|---|---:|---|---|---|---|
| buggy-campus | 1 | step 68 | btn_variant 30, btn_staff_note 31 | no, witness step 89 | missing |
| buggy-studio | 1 | step 71 | btn_variant 30, btn_staff_note 31 | no, witness step 92 | missing |
| buggy-warehouse | 0 | none | btn_variant 30, btn_staff_note 31 | no, witness step 100 | retained |
| buggy-booking | 0 | none | btn_variant 30, btn_staff_note 31 | no, witness step 100 | retained |

Campus and Studio replay windows contain no local or return-entry probe. `policy.reset` is not called on the relocation path, so `_drained_by_cluster` survives `executor.reset()`. Warehouse and Booking keep template 9 with zero relocations. DeepBench has a `parent_frame_resume_to_return` on a hub that just drained its visible local buttons, and zero debt relocations, so a broad resume drain is rejected before candidate design.

`protocol.json` is preregistered with `executed: false` before any v0.3.24 candidate cell.
