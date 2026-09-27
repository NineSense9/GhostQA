# v0.3.34 remember button ids on the branch

Fresh validation. It does not edit the v0.3.33 candidate and it does not change the product default.

`protocol.json` is committed with `executed: false` before the new applications are generated and before any policy run.

v0.3.33 clicked the same wiki preview button 104 times because each click landed on a new signature. This round remembers button ids on the branch. A repeat is skipped. The next unseen button can still be taken. When none remain, the chain stops and the return proceeds.
