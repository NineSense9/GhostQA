# v0.3.19 finding-gated return-entry drain

Inspected trigger-narrowing repair after the frozen v0.3.18 return-entry result. This round does not rewrite v0.3.18 or earlier evidence and does not change the product default.

v0.3.18 Outcome C stands. Its final SHA is `0acb51103cfe466db1d3b2227e587535f39d8958`. Lab @120 confirmed L1, L2, L4, L5, L6, L7, L8, L9, and L10, so the Guard set L1, L2, L8, L9, L10 was retained. The result-hub drain started from a same-step `sequence_terminal` outcome `finding`, then probed `btn_close` and `btn_reopen`. BUG-L9 was confirmed on `btn_reopen`.

DeepBench @120 regressed to 8 states, 6 URLs, `return_success` 0, and confirmed only BUG-D8. The Guard set D6, D7, D11, D12, D13, and D14 was lost. The only return-entry epoch on that trace is step 7, and that step has `sequence_horizon_reached` with no `sequence_terminal` outcome `finding`. Step 8 probes `btn_login` and records a `dead_action` finding. Step 9 probes `btn_demo_login` and leaves the login hub.

`v0318-trigger-context-analysis.json` is recomputed from the committed v0.3.18 traces. The census is Billing 7 finding / 1 horizon, CRM 0 / 4, Desk 1 / 5, Directory 1 / 0, Forum 3 / 1, Lab 3 / 1, Ops 0 / 0, Shop 1 / 0, Deep 0 / 1, and Wiki 0 / 6. No return-entry trigger in that census is a crash terminal.

A rule that stops a drain at the first local finding is rejected from the same traces. In the Lab result epoch, step 17 `btn_close` already has `lab_note_visibility`, and step 18 `btn_reopen` carries `lab_reopen_clears`. Billing, Desk, and Wiki also show a probe finding followed by another probe in the same epoch. Those later probes are part of the recorded drain, so finding-stop is not the candidate.

v0.3.17 had no Return-Entry Drain and already kept the Deep Guard set, Wiki W2, Directory handoff at 0, and Forum and Billing strict full transfer. That is historical support for sending horizon-only transitions back to v0.3.17 behavior. It is not a guarantee.

`protocol.json` preregisters Finding-Gated Return-Entry Drain before any v0.3.19 target cell. `executed` stays false. The candidate, once frozen, may start the inherited v0.3.18 drain only from a new same-step finding terminal that puts the live branch into returning. An ordinary horizon transition must not start that drain.

Published result: Outcome A. Lab @120 still drains the result hub from a finding terminal, probes `btn_close` then `btn_reopen`, and confirms BUG-L9 at step 18. The Guard set L1, L2, L8, L9, L10 is retained. DeepBench @120 has no horizon-triggered Return-Entry Drain, 26 states, 8 URLs, return_success 37, and retains D6, D7, D11, D12, D13, and D14. Directory handoffs stay 0. Forum and billing strict full transfer stay true. Desk, Wiki, and BuggyShop lose no Guard bugs. The product default is unchanged. This is not a fresh validation and not a promotion. The next round must be a new fresh-validation suite.
