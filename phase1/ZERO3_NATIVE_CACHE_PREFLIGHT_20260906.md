# Native CPUAdam cache restoration: separately bounded GPU check

2026-09-06. Previous job12574 FAILED199seconds/398GPU-seconds at strict final-state comparison.
Only FP32 master shards differed, maximum3.725290298461914e-09; BF16, Adam state, RNG,
counters and consumed samples agreed. This is not an explanation for historical critic accuracy.
Its original six checkpoints and failure are retained, not retrospectively accepted.

## Actual diagnosis before this trial

Pinned native CPUAdam caches float beta powers outside state_dict. Continuous training multiplies
the powers, while a fresh restored native optimizer jumps using pow; rounding need not be identical.
Real CPUAdam experiment1b6b8372b83f68038bf964547bf4b6e8b7e2c661 fixed four cases before results.
Ordinary restore differed in two cases, not all four. Empty-tensor cache replay made all four equal.
Production helper30f179505af15ca81862d5448e820739b76a13c8 then passed A/B across the same four cases,
including unchanged parameters/moments/RNG and duplicate-restore rejection.
Result75cb6581e3016ab259c35df06a69eb19cbcecd0e9272025dc631b743064b75f9;
independentba7e811a397fbb246fc5ca85a624daa88c9e853af48545184750b87fe7041184;
helperb7b037bfcae04ea10e1185099bf5339f7724d4371f45d562b58ee72944041fc7.
CPU tests use torch.equal (signed zeros are not distinguished); strict GPU fingerprint/payload byte
comparison remains mandatory. CPU vector equality is not complete GPU or production qualification.

## Narrow change

Fresh native optimizer only, exact CPUAdam Python/C++ source, fixed identical group options except
planned LR. Replay steps1..cut on zero-element tensors to reproduce only the hidden bias-power cache.
No real parameter/gradient/moment passed, no Python optimizer.step, no data access, no extra learning.
Verify all restored serialized-state/RNG fingerprints before AND after priming. Fail on changed
static optimizer options, bad step, repeated restore or native failure. Save returned cache receipt
in each actual trajectory; no tolerance, loss, model, seed, input or budget-matching change.

## Matrix and cap

One job, twoRTX3090,12min wall, driver600s+kill60s. Same4433parameter seed6, five original trajectories.
Upper2160GPU-seconds including300s exit and60s margin. Previous actual817, aggregate2977<=3120.
No automatic retries. Original12535 remains reversibly held because its pinned old guard is obsolete;
its source/configuration is not rewritten. Formal four-fit training remains unadmitted.

## Thirteen preflight requirements

1. Actual cache receipt and Socket/toolchain in artifacts. 2. CPU helper/negative tests before GPU.
3. Synthetic only. 4. Both ranks and both cuts. 5. Same training math and consumption.
6. Every checkpoint/optimizer/RNG saved. 7. All trace/security gates. 8. Original RNG perturbation.
9. Secret scan and exact SHA before publish. 10. Aggregate actuals plus bounded new wall.
11. No power/model-benefit claim. 12. Independent Slurm/worker/driver/payload statuses.
13. Frozen protocols and original confirmation membership unchanged; ADMITTED_RELEASES={}.

Pass requires full live state plus independently decoded model/master/AdamW/RNG payloads to match
at the original bit-level tolerance. Also check actual native receipts. Failure stays failure.
