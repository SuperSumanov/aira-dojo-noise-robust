# Clean critic scaling independent confirmation contract v2

Status: `CONTRACT_READY_ASSETS_PENDING / COMPUTE_NOT_AUTHORIZED`.

This contract implements the current 20-day direction. For any newly produced
confirmation run, it supersedes v1's four-size/eight-checkpoint matrix. It does not
alter or delete v1 artifacts and does not authorize GPU jobs, API calls, model fitting,
base-model updates, or frozen-truth access.

## 1. Frozen question and matrix

Under one exact generator/config stratum with outcome-before config-v2 provenance,
does an independent Qwen3 Base critic improve from 0.6B to 8B on real sibling decisions?

```text
Qwen3 Base {0.6B, 4B, 8B} x seeds {6, 7} = 6 training runs
context length = 16,384
```

Only model size may vary. Prompt, context, optimizer, token/step budget, scheduler,
warmup, task/budget conditioning, split, scorer, checkpoint rule, and reporting code
must be fixed. This trains a separate critic; the agent base LLM is never fine-tuned
or RL-updated.

## 2. Source gate before any training

Every admitted run must have a canonical `producer.config_v2.jsonl` sidecar written
before outcomes, a stable public generator release ID, and exact generator/config
stratum membership. Sidecar coverage must be 100%. The first real sidecar stops at
metadata redaction/schema review; a filename alone does not pass the gate.

The pre-test lock must carry the sidecar coverage, the canonical sidecar-manifest
SHA-256, the stable public generator release ID, the exact generator/config stratum
ID, an affirmative outcome-before-sidecar attestation, and a negative historical-
backfill attestation. The producer and independent verifier both reject a missing or
nonconforming field before any result is computed.

Historical archives cannot be backfilled into this confirmation. The existing
16,012/16,012 historical configured-model-ID reconstruction improves release metadata
but cannot replace outcome-before config-v2 provenance.

## 3. Split, selection, and one-shot access

- train/dev/frozen endpoints, physical runs, parents, and unordered pairs must have
  zero overlap;
- checkpoint selection uses train-run dev only;
- the frozen/test path is not mounted during training and is never used for periodic
  evaluation;
- all six exact model revisions, checkpoint manifests, steps, dev metrics, output
  paths, and exclusive ledgers are locked before the first frozen access;
- each checkpoint receives exactly one frozen scoring attempt; failures remain failures
  and cannot be overwritten into success;
- char TF-IDF is fitted on train only and evaluated on the identical pair IDs.

The existing materialization contract remains the delivery schema: canonical truth,
six one-shot prediction files/ledgers, baseline predictions, and a relative-path bundle.
An extra or missing size/seed fails closed.

## 4. Pre-result support and positive gates

Support requires at least 20 tasks and 300 comparison components, maximum task pair
share at most 0.20, and 100% canonical sidecar coverage.

The capacity claim requires all of the following:

1. two-seed task-macro means are nondecreasing over 0.6B, 4B, and 8B;
2. mean 8B-minus-0.6B is at least 0.02;
3. the delta is strictly positive for seed 6 and seed 7 separately;
4. the task-bootstrap 95% CI lower bound is positive;
5. every leave-one-task-out delta is positive; and
6. the delta remains positive after deleting the predeclared dominant task.

The dominant task is selected without outcome values: it is the task with the largest
number of primary pairs, with lexicographically smallest task ID as the deterministic
tie-break. This rule is frozen before result access.

“8B beats TF-IDF” is a separate stronger claim: each 8B seed must exceed the same-pool
baseline, the paired task-bootstrap lower bound must be positive, and every LOTO delta
must remain positive. Component gain capture is a third, separately named utility
conversion claim. Failure of a stronger gate does not erase a passed weaker gate, and
no secondary estimand may rescue a failed primary.

## 5. Reporting

Report every seed and the full curve, not only the mean. Required views are pair-micro,
task-macro, run/parent/component aggregation, task- and run-clustered intervals, LOTO,
dominant-task deletion, coverage/tie/missingness, and initialization/query/execution
cost. Pair-i.i.d. significance is not headline evidence.

This is capacity evidence on a benchmark, not proof of improved online search. Equal-
budget deployment requires a separate preregistered experiment and resource approval.

## 6. Resource approval sequence

No GPU work is authorized by this document. The next permissible request is a timing-
only calibration with an explicit model, GPU count, wall cap, and total GPU-hour cap.
Only after that receipt may the six-run matrix receive an exact wall/GPU-hour budget
and user approval. QOS remains at most four jobs/eight GPUs; excluded nodes and the
required Slurm configuration remain unchanged.

## 7. Machine contract and compatibility

- machine contract: `phase1/critic_scaling_confirmation_contract_v2.json`;
- v1 remains immutable for old synthetic/formal receipts;
- analyzer/verifier support for v2 must be additive and keep all v1 tests passing;
- no result may be produced until the v2 contract hash, source commit, six checkpoint
  manifests, cohort hashes, and one-shot paths are frozen.
