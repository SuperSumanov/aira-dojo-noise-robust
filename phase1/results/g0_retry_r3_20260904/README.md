# G0 r3 — approved and submitted; no training result

User approved exactly one additional two-GPU job, capped at 117 minutes, after the source repair.
Job **12377**, submitted Hong Kong `2026-09-04T13:16:31`, is `PENDING / Resources` at
`2026-09-04T05:18:44.604969+00:00`. Runtime remains zero. There is no new cost measurement or effect result.

Scheduler estimate: Hong Kong `2026-09-05T12:38:50` start / `2026-09-05T14:35:50` maximum end.
The observed wait estimate is 84005.395031 seconds (23.334831953055552 hours), **not guaranteed**.
The fixed node's two schedulable PRO6000 GPUs are occupied by a prior allocation. No hardware, queue, card-count,
priority or scientific-config change was made to bypass the queue.

## Authorized scope and admission

- Single new job; partition/QOS gpu_24h/gpu, projgpu39, 2 PRO6000 GPUs, 12 CPUs, mem=0, walltime01:57:00.
- Requeue=0, Restarts=0, exactly one requested node (Slurm pending represents this as `1-1`).
- Unique submission directory `/research/d7/spc/yzyang4/critic-component-g0/submissions/20260904-g0-r3`.
  It is a non-reusable admission latch. Do not invoke any older submit helper or retry an uncertain submission.
- Source/control/runtime/train/dev/model settings remain unchanged from repaired G0.
  Executed submit-helper commit `9ce09008812b41c82deda04c9aa720883eccdeb6`; script SHA
  `8d48facdac46ed497b187d7c67349e87903afee141a9c17f369f0b9d3508d53a`.
- A fresh 4294967296-byte allocation/fsync test passed at05:16:08 UTC; only its own diagnostic file was removed.
  This is an admission check, not a guarantee that quota cannot change while queued.
- Runtime rebound65 versions/5 critical hashes, repaired source remains clean/nonwritable at root.
  Prior failures used320 GPU seconds; this job's cap is7020seconds×2GPUs. Cumulative worst case14360GPU seconds,
  3.988888888888889 GPU-hours. Five-arm15fits remain unapproved/unsubmitted.

The 13-item project checklist is mapped in `PREFLIGHT.md`;17 related existing tests passed before submission.
All structural submission receipts were independently reread from their exact paths, credential-scanned and hashed.
The initial read-only check failed on pending `NumNodes=1-1` rather than `1`; this was a checker-format limitation,
not an allocation failure. We retained that fact and accepted only the equivalent exact-one-node forms.
The corrected independent check passed. No scheduler/job edit or resource-contract relaxation occurred.

`submission_verified.json` contains the timestamped scheduler projection and exact artifact digests.
Private raw logs, source/model data and checkpoint artifacts are not published here. Neither this observer nor
the submission helper reads the protected prospective cohort. G0 remains dev-only engineering calibration,
not a method-effect trial or clean scaling confirmation. The new job must pass the existing full worker verifier
after actual execution before its cost receipt is usable.
