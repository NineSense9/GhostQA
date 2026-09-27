# v0.3.32 one button after an alternate payload

Fresh validation. It does not edit the v0.3.31 candidate and it does not change the product default.

`protocol.json` is committed with `executed: false` before the new applications are generated and before any policy run.

v0.3.31 typed the empty title and then returned. The submit button was never clicked. Guard confirmed the empty-title bug by typing the empty title and then clicking submit. This round arms a one-shot on that payload and, on the next return from a non-hub page, takes one untried button. It does not take a link or a hub click.
