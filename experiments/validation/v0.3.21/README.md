# v0.3.21 return-waypoint frontier escape

Inspected failure repair after the frozen v0.3.20 fresh composite result. This round does not rewrite v0.3.20 or earlier evidence and does not change the product default.

v0.3.20 Outcome C stands. Its final SHA is `fc550eeccd153f201062dc612b2a791a3ed35b99`. All four fresh positive targets were composite-evaluable. Nested transfer was 4/4 and finding-gated drain was 4/4. Horizon-only drain was 0. Catalog stayed inactive. Kiosk produced finding-gated drains and no nested handoff. Every positive still lost the same bug-template classes relative to Guard: template 5, template 8, and template 9.

`v0320-waypoint-loss-analysis.json` is recomputed from the committed v0.3.20 publication. On each positive @120 the first Guard-versus-F divergence is action index 11: Guard takes `nav_up_child` back to the mid hub, and F takes `btn_mark` with label `return_entry_drain`. That divergence shows the composite policy changes the trajectory. It is not, by itself, the claim that templates 5/8/9 were lost.

The shared later pattern is the resumed outer return:

- action index 20: the deep child returns to the mid hub, `child_parent_witness` and `parent_frame_resume_to_return` fire, and the handoff stack depth is 0
- action index 21: mid hub to entity hub, decision `return_hub`, active branch still the original list-to-entity branch
- action index 22: entity hub to the list parent, decision `return_hub`

The entity hub is an intermediate return waypoint. It is not the outer sequence's final parent. At that node the final graph observes `btn_pin`, `btn_cool`, `nav_prefs`, `open_side`, `open_mid`, `nav_up_list`, and `back`. `btn_pin` and `btn_cool` never occur. `open_side` never occurs on Campus or Studio and first occurs at index 57 on Warehouse and Booking. Those three are residual at the first waypoint. `nav_up_list` is the return action taken at index 22.

This is consistent with intermediate-waypoint residual-frontier starvation: after handoff resolution, the outer list-to-entity sequence stays alive as a return obligation and walks through the known entity hub without trying the residual frontier already observed there. The audit shows that the entity local actions were observable and skipped, and that `open_side` was residual at the first waypoint and either absent or delayed. It does not prove that the mechanism will recover every bug. The experiment decides that.

`protocol.json` preregisters Return-Waypoint Frontier Escape before any v0.3.21 target cell. `executed` stays false in that commit. The candidate, once frozen, may abandon a handoff-resumed outer return only at a known intermediate waypoint that still has residual frontier, with stack depth 0, without counting a successful return, and without choosing the next action.

Published result: Outcome C. The mechanism engaged on all four inspected positives at action index 21, and the next action was the frozen policy's `open_side` branch. Warehouse and Booking recovered Guard templates 5/8/9. Campus and Studio did not. The frozen gate also records that all four lost the blank-page bug v0.3.20 F had confirmed outside the Guard set. Historical regression, catalog, and kiosk stayed inside their gates. Product default unchanged. This is not fresh validation.
