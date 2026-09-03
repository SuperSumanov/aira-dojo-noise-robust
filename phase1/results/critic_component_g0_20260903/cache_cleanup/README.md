# Approved single-cache cleanup and G0 recovery

User approval: “清理一下吧”, in response to the named historical download-cache cleanup request.

Only `/research/d7/spc/yzyang4/balanced-e2a-hf-cache-e2d587d-a1` was removed. Before deletion,
545 inventory entries and the original cache manifest were preserved locally and their SHA-256 values
independently checked. The 214 regular files had no additional hardlinks; all 96 symlinks resolved
inside the exact cache. No active Slurm job or inspected workload/current G0 dependency referenced it.
OpenSSH, user systemd and PAM session-service environments/maps are protected by the host and were
not read: only their identity and command lines were checked. The initial two preparation attempts
stopped on those permissions without deleting or changing the target. They were not experiment failures.

The cache's predeletion allocated size was **14697836544 bytes**. This is not an observed quota balance.
Deletion receipt: `2026-09-03T09:46:42.900964+00:00`. No other directories, raw corpus, trained critic
checkpoints, sealed results or effective runtime overlay were deleted. There is no trash/payload backup;
the preserved manifest and snapshot inventory support redownloading public upstream model artifacts,
subject to upstream availability.

At `2026-09-03T09:47:04.661125+00:00`, a fresh unique diagnostic file on the same filesystem passed
fallocate and fsync with length and allocated size both **4294967296 bytes**. That diagnostic file
alone was then removed. The original failed zero-byte reservation remains as evidence. This verifies
restored write capacity at test time, not a permanently reserved balance or a GPU training result.

## G0 recovery preflight checklist

The approved workload is still Qwen3-1.7B Base, seed 6, context 16384, two PRO6000 GPUs,
10 optimizer steps and exactly one full historical dev evaluation. Source is
`5f3bc362db922c8edee2ef134656dfdb9a2b74fb`; control is
`94ad7dafff1866c6d50eb54927a4bf56547facc2`. The sole scientific CLI change from the failed G0
is its approved final-only reload flag. No five-arm fit or clean-scaling matrix is authorized.

| Gate | Application to this bounded engineering run |
|---|---|
| 1. Resolved knobs | Rebind full captured CLI and source/framework hashes; allocated worker also checks the recovery receipt. |
| 2. Changed paths | Original CPU checkpoint roundtrip/overwrite regression retained; current control tests rerun. |
| 3. Pair duplication | Reuse exact immutable historical train/dev inputs; no oversampling or fresh pair selection. |
| 4. Distribution | No method-effect claim from G0; its ten steps estimate cost only. |
| 5. Evaluation balance | Exactly one complete fixed dev evaluation; no newly selected eval subset. |
| 6. Checkpoint | Approved model-only checkpoint-10; actual distributed save still must pass. |
| 7. Leakage | Existing component train/dev contract remains; no test or sealed cohort input is accepted. |
| 8. RNG | Same seed 6 and sampler settings; no corpus expansion or reshuffling change. |
| 9. Secrets | Only explicit safe receipts/helpers published after filename and content scans. |
| 10. Wall clock | New allocation capped at 7020 seconds; prior 2 GPUs x 156 seconds included. Combined maximum 14352 GPU-seconds, below 14400. No requeue. |
| 11. Power | This is an engineering cost calibration, not a powered cross-seed comparison. |
| 12. Exit status | Chain saves return codes and fails closed; uncertain submission is reconciled, not repeated. |
| 13. Immutable inputs | Source/control/data/model/runtime binding checked before launch; original failed artifacts retained. |

The first sparse-control preflight omitted two scheduler-related test fixtures: 11 tests passed and
one failed on a missing file. Both existing fixtures were included without changing their commit;
the second run passed all 12 tests in 0.07 seconds. Original preflight logs remain on the server.
