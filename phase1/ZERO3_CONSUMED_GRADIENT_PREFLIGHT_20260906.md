# CPU-offload consumed-gradient boundary correction

2026-09-06. Engineering only, not model/scaling benefit. Original12535 unchanged.

## Evidence and narrowly scoped correction

12573 source b84e8baea4de65a16038b4136cee094d29716964 FAILED at first checkpoint boundary,
133seconds/266GPU-seconds; no finished trajectory/checkpoint. Socket communication initialized.
Failure receipt a79b966c57a5fbd115712fb821c472b533bb34daf04f268873daef353af1403d;
trace108033194bytes SHA7a2b1f7ecce4962776738bb38a3392261b970e90e827be9149c3b3febbf232cb.
No SIGSEGV or protected-path/credential hit in that trace scan. Original artifacts retained.

Pinned Stage3 source84778a1aeeac1cdbadcc1cb8ae3644ef9a004a33e28b0247941f4ff95da8daf3:
initialize_optimizer_states allocates persistent CPU master.grad; _release_sub_group only sets
master.grad=None when offload is disabled. partition_grads copies the fresh accumulation into
master.grad on the next update boundary. _pre_step/zero_grad reset micro/epilogue flags, while
_post_step empties norm_for_param_grads. CPUAdam consumes but does not clear its input gradient.
CPUAdam file8a65f2a4b90df3e25cc0d21f81c53e10c3f5fffffa5178c2a7bd91c065641cac is now pinned too.

Replace only the incorrect zero-valued-master-gradient test with a read-only lifecycle predicate:
matching engine/micro/applied/skip counters, reset epilogue/norm state, model.grad=None, closed
optimizer groups, actual Adam subgroup step==completed step, finite correctly shaped CPU FP32 buffers.
Fresh engines still require zero buffers and absent optimizer state. No gradient clearing, no extra
step, no optimizer/model/data/math/seed/tolerance change. Existing exact-commit worktrees unchanged.

## Bounded matrix and verification

One new job, two RTX3090, 15min wall; driver720s+kill60s. Upper2520GPU-seconds including300s exit
and60s margin. Prior terminal actuals2+5+146+266=419; aggregate2939<=3120 original separate cap.
Same4433parameter/seed6, full4/prefix2/resume2to4/prefix3/resume3to4. No automatic retry.
Before release: CPU negative controls plus actual pinned Stage3 methods on CPU tensors, unchanged
runtime/hash/held-resource checks and independent verification. Actual GPU must preserve model,
FP32 masters, AdamW, static scaler, all RNG, counters and consumption; independent payload reader
must agree. Passing fake/CPU tests is not GPU qualification or permission for four effect fits.

## Thirteen preflight items

1. Actual node/toolchain/Socket settings in artifacts. 2. CPU new-branch negative controls first.
3. Synthetic fixture only, no real test/train reads. 4. Every rank and both cuts, no cherry-picking.
5. Exact fixture/math held fixed. 6. Save all actual shards/RNG. 7. File-trace and credential scan.
8. Same seed and RNG perturbation. 9. Secret scan before publishing. 10. Explicit wall/group cap.
11. No power or method inference from tiny engineering. 12. Preserve worker/Slurm/payload exits.
13. No changes to frozen protocols/membership or ADMITTED_RELEASES={}.
