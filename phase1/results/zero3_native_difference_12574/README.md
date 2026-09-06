# Failed real GPU restart comparison: job12574

This is **retained failure evidence**, not GPU acceptance or model benefit.
Training source: `09c322bf82cc62ce67babb7e2bfee51633e40710`.

Two RTX3090,199seconds/398GPU-seconds. Full, prefix2 and resume2 completed, with six
checkpoints. Strict final equality failed: only FP32 master shards differed;
maximum absolute difference was3.725290298461914e-09 and BF16 projections agreed.
Adam state, RNG, counters and consumed samples agreed. Prefix checkpoint2 agreed
with uninterrupted checkpoint2. Prefix3/resume3 were never run.

The later native CPUAdam cache diagnosis must not retrospectively turn this job
into a pass. Its original payloads remain on the research disk; this public bundle
contains safe logs, structural checkpoint manifests and fingerprints, not pickles.
All34 raw files were imported byte-for-byte; MANIFEST lists33 members.
Failure receipt SHA: `0c67e794bf08175755bbd4c77611bd61d27709833fe1e437b213a6234911ad80`.
Trace SHA: `bd860db3cb768f1f6530331280a8234aa7a593c47ebc4d77ba5ac2b0b523139c`.
Archive SHA: `fbe56416a2faff61b2b10cc3ebc737a23c6bed189c76e12775173a3be787a7b7`.

Also retained: the reversible hold of obsolete pending job12535. Its original
configuration was not changed; its old gradient guard is known to be incorrect.
Do not release that old job, rerun the exclusive audit, or execute its successor
12574 FINAL reader/payload acceptance on this failed job.
