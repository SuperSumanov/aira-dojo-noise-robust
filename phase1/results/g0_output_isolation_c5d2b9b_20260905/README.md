# G0 12377 failure and output-isolation recovery receipt

Date: 2026-09-05 Hong Kong. This is an engineering receipt, not a model-effect result.

## Failed allocation

Slurm accounting records job 12377 as `FAILED`, exit `1:0`, elapsed 131 seconds,
with two allocated GPUs. It ran from 02:26:33 to 02:28:44 Hong Kong time, consuming
262 GPU-seconds. Together with the previously recorded 320 GPU-seconds, cumulative
allocated time is 582 GPU-seconds (0.16166666666666665 GPU-hours).

The launcher command itself exited after 0.02 seconds because its sourced shared
environment attempted to create `outputs` inside the deliberately read-only source
checkout. No model output, checkpoint, verification, manifest, or COMPLETE marker exists.
This is not evidence about model loading, memory, DeepSpeed, NCCL, or ten-step runtime.

Downloaded archive SHA-256 values:

- run: `ab4059d8c892f649222079bf256f7664086cd8701c0d3c53c65b43a3354bc1d5`;
- submission: `1a2f524597f13460c3b5431ad18678751b6d91287aef6ca2d04d75c5aefffc9b`.

Both credential-shape scans were clean.

## Narrow correction

Control commit `1487bab052335dc787084b6b51b2b39ff5b59705` redirects only the shared
environment's default output/log paths to fresh directories beneath `G0_RUN_ROOT`.
The actual confirmatory output, senior launcher/source, model, data, SHA bindings,
seed, batch shape, context, steps, optimizer settings, and final-only behavior are unchanged.

Two source-initialization smokes passed against the actual read-only source commit
`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`. Worker SHA-256 was
`38244d3cc3cc16d86baa8dffdabdf4148243382623d8ae231cb16d4f055700d2`.
Only an external shared setup directory was created; source Git remained clean.

## Exact launcher dry-run

The original senior launcher and real train/dev/cards hashes were then run through
argument construction with a fake `accelerate` executable. This does not import the
model or training code. The first two passes had different raw argv hashes solely due
to different scratch output paths; no byte-identity claim is made for them.

Commit `c5d2b9ba5d9469df60819408a4f2272399da3612` added a hash that normalizes only
the scratch prefix. Two new passes both returned zero with empty stderr and produced:

- normalized argv SHA-256: `4fea5ab1fc547c794e15def2c10ca63caa947cd8ee7701540b4bdc6d1731fa03`;
- launcher stdout SHA-256: `9f101800d81c88cdea09ff7bcb6aa23fb9c79bc2f67f7e61b3d7f10b80f151ef`;
- processes/context/steps: 2 / 16384 / 10;
- effective pair batch: 128;
- test-path arguments, model imports, GPU jobs, model fits, API calls: all zero.

This reaches the real `accelerate launch` boundary and resolves the observed first
failure. It does not prove actual distributed execution. The prior one-job authorization
has been consumed; no successor was submitted.
