# v0.3.16 early parent re-entry and local frontier lease

Inspected failure repair after the frozen v0.3.15 fresh validation. This round does not rewrite v0.3.14 or v0.3.15 evidence and does not change the product default.

v0.3.15 Outcome C stands. The frozen Horizon Handoff candidate transferred on buggy-forum and buggy-billing, lost four Guard-confirmed buggy-lab bugs, and emitted two same-parent handoffs on the shallow buggy-directory negative control.

`v0315-failure-analysis.json` is recomputed from the committed v0.3.15 traces. Directory has 2/2 same-parent handoffs. The same-parent census is forum 11/1, billing 6/1, lab 11/3, directory 2/2. The first lab action divergence is step 13: Guard `open_result_from_run`, Horizon `nav_up_exp`.

`protocol.json` preregisters the repair before any v0.3.16 target cell. `executed` stays false.

Published result: Outcome B. Directory false handoffs went from 2 to 0. The lab branch lease recovered BUG-L8 and still lost BUG-L1, BUG-L9, and BUG-L10. Billing kept every Guard bug and missed the v0.3.15 expansion gate. No historical Guard bug was lost. The product default is unchanged. This is not a fresh validation and not a promotion.
