# v0.3.18 return-phase entry drain

Inspected repair after the frozen v0.3.17 local-action result. This round does not rewrite v0.3.17 or earlier evidence and does not change the product default.

v0.3.17 Outcome B stands. Its final SHA is `4ee5d6527c8f3405f7dd6f9a961b8b2ab555c5f3`. Lab kept L1, L2, L5, L6, L8, and L10. The only Guard loss is L9. Forum and Billing have zero Guard loss and strict full transfer. Directory handoffs stayed 0.

`v0317-return-entry-analysis.json` is recomputed from the committed v0.3.17 Lab trace and the committed Guard trace. Step 15 goes from the run page through `open_result_from_run` onto `result.html`, emits `sequence_terminal` outcome `finding` and `horizon_handoff_started`, and step 16 is `return_attempt`. No local drain starts on that result hub. Step 21 goes from experiment `e2` through `open_result_q1` onto `result.html`, emits `sequence_terminal` outcome `finding` and `nested_continuation`, and step 22 is `return_attempt`. Again no result drain.

Guard L9 is first confirmed at step 74 on `btn_reopen` with `lab_reopen_clears`, after `btn_close` in the same window.

`protocol.json` preregisters Return-Phase Entry Drain before any v0.3.18 target cell. `executed` stays false. The candidate, once frozen, may drain eligible local buttons only on a false-to-true return transition. It shares the v0.3.17 drained-key store and does not promote a cross-hub probe into a child.
