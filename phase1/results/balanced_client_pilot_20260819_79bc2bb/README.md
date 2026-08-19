# Balanced three-client production pilot — frozen support decision

## Decision

`INSUFFICIENT_BALANCED_PILOT_SUPPORT`

The engineering contract passed, but the frozen scientific support gate failed. This result does **not** authorize a
larger acquisition with the same three-client matrix. No score values were reported and no winner labels were computed.

## Frozen design

- Source/control commit: `79bc2bb6e5bb86b7cc60c61bed5cdcf6cdd7c692`
- Matrix: 3 clients × 2 tasks × 2 seeds = 12 physical runs
- Clients: `deepseek-v4-flash`, `qwen3-coder-flash`, `glm-5`
- Tasks: `spooky-author-identification`, `spaceship-titanic`
- Seeds: 1402, 1403
- Per-run contract: four journal rows, `step_limit=4`, `execution_timeout=300`, `time_limit_secs=1800`
- Four plain Slurm shard jobs, one GPU each; no native Slurm array

## Integrity result

- Slurm jobs `11198`, `11199`, `11200`, `11201`: all `COMPLETED 0:0`
- Physical runs: 12/12
- Journal rows: 48/48
- Worker receipts: 12/12 with `rc=0`
- Exact resolved/final client, task, seed, operator, timeout, state, and search/journal checks: passed
- Environment dumps: 0
- Failed-row markers: 0
- Sum of top-level one-GPU job elapsed time: 9,373 seconds = 2.6036111111111113 GPU-hours

## Frozen support gate

| Quantity | DeepSeek | Qwen | GLM | Total / decision |
|---|---:|---:|---:|---:|
| Runs with at least one valid non-root node | 4 | 0 | 3 | gate failed: each client needed at least 2 |
| Valid non-root nodes | 7 | 0 | 4 | 11; gate required at least 18 |
| Finite same-parent sibling pairs | 3 | 0 | 0 | 3; gate required at least 6 |

The remaining gates also failed: Qwen and GLM had no finite sibling pair, and DeepSeek supplied all three pairs, so the
maximum client pair share was 1.0 rather than at most 0.60. In total, 0/5 frozen support predicates passed.

This is a production-support failure, not a client quality comparison. In particular, job completion is not equivalent to
a valid submission: all four Qwen runs completed structurally but produced zero valid non-root nodes under the frozen
definition. The outcome closes direct scale-up of this exact three-client matrix; it does not establish an ordering of
client scores.

## Independent verification

The committed independent verifier was run twice against the same sealed artifacts. Both outputs were byte-identical:

`7527ef2dec44aff2c4bebeca8a9f4749f11532f3c9b40f20314f3b33809dbd04`

The archived directory contains only the manifest, source/control receipts, Slurm accounting, resolved configurations,
worker receipts, and the two support-only verification outputs. Raw journals, generated code, logs, score values, and
credentials are not included.
