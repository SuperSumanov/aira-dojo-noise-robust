# SPT pilot v1 reproducibility bundle

This directory contains the small, shareable artifacts for frozen Slurm job `10648`:

- `prereg/pilot_manifest.jsonl` and `prereg/pilot_audit.json`;
- 18 entry status records and 18 raw `result.json` records;
- primary per-execution/card/group tables and `summary.json`;
- the independently recomputed raw report and cross-check;
- the frozen-test overlap audit and label-blind v11 capacity census.

Large checkpoint snapshots, repeated CSV artifacts, and the container image are not duplicated in Git. Their content hashes and
provenance remain in the raw result/manifest records. The candidate never received private labels or grader output.

Verified headline:

```text
verdict=INCONCLUSIVE
baseline=2/6
probe120=2/6
semantics=2/2
latency_pairs=2
median_relative_feedback_gain=0.04135151374612629
```

Recompute the independent verdict from this directory alone:

```bash
python phase1/verify_spt_pilot_raw.py \
  --manifest phase1/spt_pilot_v1/prereg/pilot_manifest.jsonl \
  --manifest-sha256 5b74f725822b0290393de976020c02bfb456ac3164cc094a848637b53ef55a06 \
  --results phase1/spt_pilot_v1/raw_results \
  --status-dir phase1/spt_pilot_v1/status \
  --output /tmp/spt_raw_verification.json
```

The recomputed file must have SHA-256
`8ef4723fa059e7f91a48d95e6187d9d02d729ba4626eccfc56f9e883abe01c7f`, matching
`independent_raw_verification.json`. The scientific interpretation and frozen gate ordering are in
`../实验记录/2026-08-13/SPT_标签盲机制pilot裁决.md`.
