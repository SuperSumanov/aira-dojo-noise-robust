# ForeTS exact-upstream hotfix preparation — 2026-09-08

Upstream: `8b621851a87d20382feefe8c8458a7db2a1fabea`.
Design and limitations: `phase1/PARALLEL_EXECUTION_AND_FORETS_20260908.md`.
Patch: `phase1/upstream_patches/0002-ForeTS-startup-and-step-boundary-20260908.patch`.

No upstream branch, active checkout, producer or experiment protocol was modified.
This is a proposed partial integration fix, NOT a ready end-to-end experiment.

## Actual checks

1. Original-source and proposed-source method tests: 28 passed, 0 failed/skipped.
2. Git patch applied in an independent temporary index based on the exact upstream;
   4 source files, 42 insertions and 11 deletions. Applied tree:
   `c180d1358bc03a9893b1a3a5c5678d3b006be08b`.
3. Same 28 checks reloaded patched functions from that actual Git tree, not the
   in-memory replacement helper: 28 passed, 0 failed/skipped.

These are the SAME 28 scenarios, not 56 independent experiments. They execute actual
method bodies, but use mock parent initialization, HTTP, debug and synthetic nodes.
No GPU/model/real program/paid API or held-out data was accessed. Actual environment:
Windows, Python 3.13.4, pytest 8.4.0. No Linux/Slurm/Hydra integration pass is claimed.

The suite includes an explicit reproduction of the still-unfixed unexecuted-node
memory crash. Passing that test means the limitation was reproduced, not eliminated.
The other original-source tests assert the old defects, alongside patched expectations.

Commands from repository root:

```text
python -m pytest phase1/tests/test_forets_upstream_hotfix_20260908.py -q --tb=short -p no:cacheprovider --junitxml=phase1/results/forets_hotfix_20260908/builder_final_tests.xml
python -m phase1.forets_upstream_hotfix_20260908
```

To check the patch, use a separate temporary Git index, `git read-tree` the exact
upstream, then `git apply --cached --check` and `git apply --cached` the patch.
`git write-tree` must produce the tree above. Do not apply it to the senior's live branch.
For the second test pass, set `FORETS_PATCHED_TREE` to that tree, run the same test
command with `applied_tree_tests.xml`, then restore the previous environment value.

`validation.json` binds the seven deliverable payloads, exact upstream source hashes,
both final XML logs and remaining blockers. The applied Git tree is locally derived;
it is not itself a pushed commit. Reconstruct it from the patch and upstream.

Two SSH attempts in this turn both ended with `Connection closed by 137.189.88.148 port 22`.
The pending metadata budget join did NOT execute; no task/component selection or
training-source admission was made. Github fetch and patch publication are separate
from remote execution availability.
