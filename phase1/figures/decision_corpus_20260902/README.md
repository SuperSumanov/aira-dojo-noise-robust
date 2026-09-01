# Decision Corpus paper Figure 2

`figure2_run_to_pair_weighting.{png,svg}` is rendered only from the hash-locked,
outcome-blind structural trajectory at
`phase1/results/structural_weight_trajectory_7cda_20260826/trajectory.json`.

**Caption draft.** Run-level balance does not imply pair-level balance. Across the
chronological 120--339-run prefix, task concentration under physical-run weights
continues to decline, while sibling-pair weighting rises sharply after one
high-leverage drop. From first-240 to run 339, run HHI changes
`0.055972 -> 0.048877` and maximum run share changes `0.108333 -> 0.091445`, while
pair HHI changes `0.083038 -> 0.135747` and maximum pair share changes
`0.171499 -> 0.312334`. The run-to-pair task-distribution TV at run 339 is
`0.337083`. This is an outcome-blind benchmark-weight diagnostic, not observed
predictor bias, accuracy, effect, utility, or a causal producer-behavior estimate.
One drop accounts for high leverage, so the magnitude must not be called generally
robust even though the direction passes the recorded temporal/task-deletion gates.

Reproduce from the repository root:

```bash
python -m phase1.plot_paper_figure2_weighting
```

The renderer checks the input SHA before reading it and emits a machine-readable
receipt. Two consecutive renders were byte-identical for both PNG and SVG. Current
SHA-256 values:

- input trajectory: `bbdb802711bd2f300725be156c5fd228a79fa0792f8d7317674a6a0bbb419f30`
- receipt: `797f0d37b6c0850e8aa0405a20622b8b227e13aa637bcd4a5bd0537a7c04d558`
- PNG: `36d647b0fd4d44f39644f3af4fffe72496398cc244c9bff1afffb48b07ad701b`
- SVG: `326e2f7bcb684214a4d3f2e43fa8efea0933457d38b956fa7db0266b5081b459`

GPU/API/model fit/base update and outcome/label/prediction-value reads are all zero.
