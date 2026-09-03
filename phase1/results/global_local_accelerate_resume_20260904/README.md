# Exact Accelerate CPU checkpoint recovery — 2026-09-04

Status: **engineering verification passed; no research effect/scaling result**.

This extends the earlier variable-update adapter using the real Accelerate
`save_state`/`load_state` interfaces, not the previous manual Gloo checkpoint path.
The model has two float64 parameters and synthetic integer inputs; dropout,
Python RNG and NumPy RNG are active. No real model, training data, dev/test,
prospective vault, GPU or paid API is opened. It does not authorize a model fit.

## Fixed test and observed result

- world 2/4 × G-to-L/Ghash-to-L; seed 6, per-rank seed 600+rank.
- G/L source sizes 176/209, update pair counts 128/48/128/81; actual token-plan
  synchronization, mean-loss normalization, clipping and LR are used.
- Full four updates; prefix two and fresh-process suffix; prefix three and
  fresh-process suffix. Full trajectories perform the same intermediate save
  calls, avoiding a save-call/RNG confound.
- Resumed processes deliberately initialize with 9600+rank. All three RNGs must
  differ before load and match the saved state immediately after load.
- 20 distributed trajectories, 48 global updates, 612 all-rank forwards.
- 8 resume comparisons / 24 rank states: model, optimizer, Python/NumPy/Torch RNG
  and complete consumption events match uninterrupted execution bit for bit.
- Independent verifier decodes all 36 framework checkpoints directly using
  safetensors and `weights_only=True` with narrowly scoped NumPy safe globals.
  It imports neither the harness nor the update/checkpoint adapter.
- Runner rc=0, timeout=false, elapsed 347.506484746933 seconds. This single runtime
  is not a throughput claim. Source bytes are unchanged during execution.

The known Accelerate RNG loader catches exceptions rather than necessarily
raising. Thus a successful return alone is insufficient: the gate independently
compares every restored component. All ranks and files are hash-checked before
any deserialization; hashes establish integrity against our own receipts, not
the trustworthiness of an arbitrary third-party pickle. Completion markers are
written only after all ranks save. This is not a power-failure durability proof.

## Evidence and reproducibility

- Base commit: `dca429b85507cfcd96b256f65e2df2ac15be7b9a`.
- Summary SHA-256:
  `99601e0ca6440952f789690b5e118a0887cfec54ff2355f376fc849ea2c7bc7b`.
- Actual binary root: `/tmp/gl-accelerate-20260904-XmQYTa/resume-r1`.
- Original export: 171 files, 3,317,919 bytes before this README/context were
  added; archive SHA `1d625c21985ee12ec4b8301f1e51f8125f626af2a105afb8fdfdfb9eb9b1fa1b`.
- `preflight.json` pins source/runtime/matrix and scopes; `execution_exit.json`
  records the exact command, environment overrides, limits and actual return code.
- `run_ledger.csv` has one row per synthetic execution trajectory, including
  commit, source SHA, seed, world, arm, shared budget and fixed model/LR knobs.
  The original raw `runs.csv` is retained; both bind the same trajectory receipts.
- Binary checkpoints stay remote. Git contains framework-file manifests,
  rank observations, trajectory receipts and independent verification receipts.
  The receipt-only checker is explicitly not a new independent binary decode.
- Related regression: 243 passed, 2 existing skips (local Torch absent for one
  module; old explicit opt-in autograd test). Actual CPU evidence is separate.

Local verification without Torch:

```text
python -m phase1.verify_global_local_accelerate_resume --root phase1/results/global_local_accelerate_resume_20260904 --summary-sha 99601e0ca6440952f789690b5e118a0887cfec54ff2355f376fc849ea2c7bc7b --receipt-only
python -m pytest -q phase1/tests/test_global_local_accelerate_checkpoint_gate.py phase1/tests/test_global_local_accelerate_resume_result.py
```

## Failure history (not omitted)

1. The independent decoder's first early check failed before RNG deserialization:
   NumPy 1.26.4 exposed a compatibility `numpy._core` namespace without its
   `multiarray` attribute imported. A first diagnostic also assumed `_core`
   was always present; it failed without touching any model state.
2. After the execution matrix finished, only two decoder lines were corrected
   to explicitly import `numpy.core.multiarray._reconstruct`. No trajectory,
   checkpoint, observation, comparison criterion or source used by the workers
   changed. The corrected decoder and export checker both returned zero.
3. The as-run source map includes the original decoder SHA
   `6791f220e744b51ac7bb3b26bfc69c6eec01d398880cad2576c4c62dffeab4ff`.
   The corrected verifier SHA is
   `6b8cc683e5ff4f3e3ed4a800fa8aeb4fa7388a9dc2676116974c1951ab47e5ca`.
   A test reconstructs the original two lines and checks the original file SHA.
4. During a parallel status check, an assumed `/tmp` status-script path did not
   exist. After copying the reviewed script to an explicit path the check passed.
   This did not launch or alter any experiment.

Missing rank files, changed bytes, missing components, and semantic sync/target-
access/model-state changes after rehashing are rejected in regression tests.

## Limits and next scientific step

This does not verify real reward-model training, GPU ZeRO-3/bf16, data-loader
state, heterogeneous world-size resumption, or power loss. Explicit names and
plan cursor receipts are used; Accelerate's internal `step=0` is not confused with
the completed optimizer updates. LR is derived from the plan, not restored from
an unregistered scheduler. No checkpoint is selected by an effect metric.

The scientific next step still requires G0 cost evidence, producer/experiment
isolation and explicit GPU-hour approval. G0 12288 remained pending at 18:53 UTC;
senior b8d0951, 589/960 intake, zero config-v2 sidecars and absent closure were
unchanged at 18:54 UTC. Neither these engineering results nor single-pivot
Global-to-Local training establish capacity scaling.
