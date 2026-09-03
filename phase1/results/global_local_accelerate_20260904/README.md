# Exact Accelerate partial-update validation

Historical-development engineering only; no accuracy, scaling, or search-utility claim.

- Remote output: `/tmp/gl-accelerate-20260904-XmQYTa/run-r2`.
- Summary SHA-256: `a16b7d3a7935d65a6fdb1de1a56c725f68941f6cbe0d15ec8b8a7c8e20fb7d4a`.
- Matrix: world 2/4 × G-to-L/Ghash-to-L; synthetic two-parameter CPU model only.
- Four distributed trajectories, 16 global optimizer updates, 204 all-rank forwards.
- Exact runtime: Torch 2.11.0+cu128, Transformers 5.12.1, Accelerate 1.14.0, DeepSpeed 0.19.3.
- The active execution path is Accelerate + CPU DDP, not DeepSpeed, ZeRO-3, bf16, or the default Trainer loop.
- Per-update counts are 128, 48, 128, 81. Every rank participates in every used microstep.
- Source-bound manual synchronization and exact pair-mean scaling match an independent full-update reference at rtol=atol=1e-12.
- G/Ghash input and synchronization traces are identical; the hash arm never requests true global targets.

Failure history is retained. r1 incorrectly ran the full-world receipt verifier on each rank's local subset and failed before a complete artifact. r2 moved that same check after all-gather. r2's controlled Python workload returned zero and wrote all artifacts, but the outer Bash wrapper subsequently failed while parsing its final case statement. The direct, independent JSON-only verifier returned zero; the wrapper itself is not reported as a successful command.

An earlier source-inspection command mistakenly created the worktree's default `.venv`, which was not the G0 runtime. It installed 251 packages, then failed because Accelerate was absent. The exact generated `.venv` (1,235,908,246 apparent bytes) was path-validated and removed; G0's actual selective runtime and source files were not modified. Shared download-cache entries were not purged.

The source-specific loss/pooling bridge is also saved in `source_loss_bridge.json` (SHA-256 `c8e3a8fc903431403f2af9e35b51cd6fc8d5f245c72923dd4bec01a6e48a2b17`). Only the exact AST bodies of the senior source's `compute_loss` and reward-model `forward` were executed with synthetic tensors; the real model constructor was never called. All 48 float32/float64 loss-and-gradient cases and eight pooling rows passed. A deliberately unadapted canonical orientation was detected as wrong. The first bridge run's scalar-conversion warning was removed by explicit detach in result logging; r2 returned zero without that warning.

No real records, model weights, GPU allocation, paid API, frozen cohort, or outcome values were accessed. The existing pending G0 was not resubmitted or changed. Full production reward-model integration and ZeRO-3/bf16 checkpoint recovery remain unverified.

Publication checks: the eight inspected staged source/protocol/summary blobs match the original SHA-256 values, including unchanged frozen v2. Narrow LF attributes prevent Windows checkout conversion. Existing trailing blank lines in hash-bound sources are retained; the whitespace check disables only `blank-at-eof`, not trailing-space or indentation checks. The related local regression has 213 passes and two documented skips. The credential-shape scan found zero hit files; all ten sensitive-filename-expression matches are the reviewed token-budget code/receipt family, not credentials.

The first post-push Windows archive exposed a missing LF attribute on the older frozen v2 dependency: 48 passed, one failed, one skipped. Its published Git blob stayed unchanged; only the exported CRLF bytes differed. Adding that exact attribute, without editing v2 or any tested scientific payload, produced a clean 49-pass/one-skip export. Both attempts and their hashes are retained in `publication_verification.json`.
