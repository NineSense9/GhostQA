# v0.3.17 local action drain

Inspected failure repair after the frozen v0.3.16 reentry-frontier result. This round does not rewrite v0.3.14, v0.3.15, or v0.3.16 evidence and does not change the product default.

v0.3.16 Outcome B stands. Directory false handoffs went from 2 to 0 and early parent re-entry recovered BUG-L8. buggy-lab @120 still lost BUG-L1, BUG-L9, and BUG-L10. Billing kept every Guard bug and missed the strict full-transfer expansion gate.

`v0316-local-frontier-analysis.json` is recomputed from the committed v0.3.16 R trace and the committed Guard trace. At the run hub, the step-12 witness grants four frontier keys and step 13 selects `open_result_from_run` before `btn_cool`, `btn_staff_note`, and `open_sample_s2`. That child return-cycle escapes at step 20 and the suspended outer is abandoned. At the result hub, the step-25 witness grants `btn_close`, `btn_reopen`, `open_notebook`, and `open_run_again`; steps 26 and 30 select the two links; the child escapes at step 38 with `btn_close` and `btn_reopen` still untried.

Guard BUG-L10 is first confirmed at step 30 on `open_result_from_run` after `btn_staff_note`. Guard BUG-L9 is first confirmed at step 74 on `btn_reopen` after `btn_close`. BUG-L8 is already recovered by v0.3.16. BUG-L1 is a downstream `/samples.html` hit at step 99; this audit does not claim local button drain causes it.

`protocol.json` preregisters Local Action Drain before any v0.3.17 target cell. `executed` stays false.
