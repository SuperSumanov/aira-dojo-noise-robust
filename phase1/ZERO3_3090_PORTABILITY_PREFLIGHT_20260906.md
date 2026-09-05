# Bounded actual-GPU portability check — 2026-09-06

Goal: establish whether the unchanged tiny BF16 ZeRO3 CPUAdam five-trajectory
resume test runs on public gpu28 (two RTX3090), then independently verify actual
checkpoint bytes and CPU final readout. Not a model-effect experiment, 1.7B/16K
qualification, a throughput comparison or replacement for pending PRO6000 12535.

Context: shared R5 Torch2.11.0+cu128, transformers5.12.1, accelerate1.14.0,
DeepSpeed0.19.3; CUDA12.8 toolchain required, no installs or upgrades. gpu28 Ubuntu24
advertises available3090; actual admission and device names must verify. Read-only
senior forward source fixed at5f3bc362db922c8edee2ef134656dfdb9a2b74fb.
Source code exact-commit, clean sparse worktree; keys never exported to job.

Matrix: seed6; random4433 parameters, eager short-context, same fixture/optimizer,
2ranks ×2microbatch ×2accumulation. Full4; prefix2/resume2; prefix3/resume3.
Five fresh distributed lifecycles within ONE allocation. Only hardware profile
changes. No real Cards/G/L, protected outcomes, pretrained weights or network.
No inference from cross-platform hash differences: only same-platform resume
versus uninterrupted must be bitwise identical, with unchanged tolerances.

Resources: gpu_24h/qosgpu, gpu28,2RTX3090,12CPU,mem0,no-requeue,20minutes.
Separate cap2×(1200+300+60)=3120GPU-seconds=.8666666666666667GPUh.
Existing12535 untouched; combined2jobs/4GPUs remains within4jobs/8GPUs.
No retry. Initial compiler/runtime failure terminates before model work. Held
submission and independent scheduler-field inspection required before release.

Preflight checklist:
1. Save actual GPU names, runtime, Slurm fields, config/source hashes in receipts.
2. CPU tests for profile routing, allocation refusal, session and payload verifier.
3. No real test data; only fixed synthetic fixture. No oversampling change.
4. Five trajectories and both rank states, not a scalar mean.
5. No accuracy claim or imbalance-sensitive evaluation.
6. Retain all nine complete model/master/optimizer/RNG checkpoint bundles.
7. No real train/test paths; file trace reviewed independently.
8. RNG restored and directly compared, no changed input ordering or sampling.
9. Credential-shape scan before publication; no raw env export.
10. Fixed20min including compilation; hard timeout, terminal accounting, no retry.
    This is a fail-fast feasibility allocation, NOT a measured completion ETA.
11. Synthetic engineering only; no power/model-capacity conclusion.
12. Trap records actual exit including early compiler failure; timeout and no-requeue.
13. No corpus mutation or assignment; concurrent intake follows unchanged protocol.

After success, independent CPU verifier hashes every member before loading our own
artifacts; compares actual12 model/optimizer/RNG payload pairs and consumption.
Then real engine final shards exercise the pinned CPU reconstruction interface.
Both require trace/security acceptance; success is engineering progress only.
