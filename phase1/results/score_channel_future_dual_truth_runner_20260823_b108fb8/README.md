# Future dual-truth runner exact-commit verification

This directory mirrors the aggregate-only verification receipt for control commit
`b108fb8d4d9c04d52ccae1d71d6e3d8d867820b6`.

- focused tests: 23/23 passed;
- complete `phase1/tests`: 880/880 passed with 33 warnings;
- real collecting-cohort negative control: rc=1 before truth open;
- `label_vault.jsonl` file-open count in that negative control: 0;
- changed-filename/high-confidence-content credential counts: 0/0;
- fresh no-smudge worktree clean before and after;
- production truth/GPU/API/model fit/base-LLM update: unopened/0/0/0/0;
- remote immutable `SHA256SUMS` file SHA-256:
  `5bf3b4dbd414e88d3696acb1a25ebb09924536a610ccbb1b236a05f2b0198b31`.

The runner remains manual-only and is not wired into the continuous intake watchdog. It does not authorize a replay
regardless of either truth-support status. The remote manifest references file-open traces retained on the experiment
host; this repository mirrors the compact human-auditable subset of that receipt.
