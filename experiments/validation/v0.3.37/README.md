# v0.3.37 leave the distractor path after four steps

Fresh validation. It does not edit the v0.3.36 candidate and it does not change the product default.

`protocol.json` is committed with `executed: false` before the new applications are generated and before any policy run.

v0.3.36 found the navigation loop and then stayed on the help and settings pages. The order page never closed and reopened. This round still enters through the distractor link, allows four steps, then takes a return.
