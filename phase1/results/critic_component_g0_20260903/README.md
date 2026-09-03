# G0 launch — controlled-effect validation entry stage

Recorded 2026-09-03; scientific status: **no new effect result**.

## Updated outcome: failed before training (13:06 Hong Kong check)

Slurm accounting reports job 12181 `FAILED / 1:0`: actual start `11:58:33+08:00`, end `12:01:09+08:00`, elapsed 156 seconds. Two allocated GPUs therefore account for `0.08666666666666667 GPU-hours`. The queued timestamps below are retained as launch history, not current status.

Both ranks raised: `ValueError: DeepSpeed can't be used with save_only_model along with load_best_model_at_end.` This happened in Trainer construction, before `trainer.train()`. No train-begin event, optimizer step, dev evaluation, or checkpoint was produced. No new scientific evidence or training-throughput estimate exists. Source/model/input preflight passed, but import-only runtime testing missed this resolved configuration conflict; that omission is ours.

Evidence: worker log SHA-256 `28745e18359126e444ff49626d1fdce725bf6d18b0ab407e4a557bcfb8f71790`; failure marker `a086f4e9ff61802cf7c08352105b9205948a77581ca54ff5f35e59108e10a7ee`; launcher resource receipt `8c02a9ff1c5ee54f9c93633a9d362bbab727b1bd956ec1ccfdd1da02fe06e502`. All examined evidence had zero credential-shape hits; originals remain remote and unchanged.

### Proposed recovery, not applied or authorized to retry

Add an explicit G0-only mode that requires `max_steps=eval_steps=10`, disables `load_best_model_at_end`, and retains `save_only_model=true` plus `save_strategy=best`. Keep ordinary launcher defaults unchanged. There is only one evaluation/checkpoint in G0, so its unique selected endpoint remains checkpoint-10; no accuracy-driven new selection is introduced. The independent verifier still must enforce exactly one checkpoint/evaluation and all ten optimizer steps.

The CPU diagnostic executes the exact installed framework's incompatibility predicate over all eight DeepSpeed/model-only/reload combinations and inspects checkpoint-selection dependencies. It confirms the specific rejected combination and that the proposed flag resolves that guard. It does **not** instantiate the full Trainer, test DeepSpeed saving, prove numerical equivalence, or validate the complete GPU path. See `failure_diagnostic.json`.

Any successor first requires user retry approval, an exact source/control revision with the proposed bounded mode, full resolved-configuration preflight and checkpoint-saving regression. At most one additional two-GPU allocation of 7,044 seconds (`1:57:24`) would preserve the original cumulative 4-GPU-hour cap. No second GPU job has been submitted; the five-arm effect matrix remains unapproved.

## Actual submission

- User explicitly approved starting the previously quoted bounded G0 stage.
- Real Slurm job: `12181` (`critic_g0_20260903`), submitted `2026-09-03T03:12:49Z`.
- Last checked state: `PENDING`, reason `Resources`, runtime zero, restarts zero.
- Requested: `projgpu39`, `gpu_24h/gpu`, 2 PRO6000 GPUs, 12 CPUs, 2-hour walltime, at most 4 GPU-hours.
- Scheduler estimate: `2026-09-03T11:53:25+08:00` start; `13:53:25+08:00` hard end if that estimate holds. Not guaranteed.
- Submission latch: `/research/d7/spc/yzyang4/critic-component-g0/submissions/20260903-g0-r1`.
- Actual run root: `/research/d7/spc/yzyang4/critic-component-g0/runs/job-12181`.
- The scheduler initially defaulted to `Requeue=1`; while still pending, `scontrol update JobId=12181 Requeue=0` disabled automatic retry. Independently re-read: `Requeue=0`, `Restarts=0`. No second submission occurred.
- Archived `launch_helpers/g0_submit_once_20260903.sh` records the exact original invocation; it must **not** be re-executed. Its original remote SHA-256 is `f738f3516bd6dd8450c4c4b69d42935561177eea9476ed9ec7512975fa4c2753`; the subsequent scheduler correction above is part of this receipt.

## Fixed scientific contract

Qwen3-1.7B Base, seed 6, 16,384 context, bf16, ZeRO-3 with CPU parameter/optimizer offload, effective pair batch 128, LR 1e-5, cosine schedule, warmup ratio 0.03, exactly 10 optimizer steps and one complete historical-dev evaluation at step 10. Only checkpoint-10 may exist. No test-path argument, no prospective-cohort access, no agent-base update.

- Control: `a99bf8a78ee25fc0257dce5aabdc947ef0725839`; its four G0 blobs match public prelaunch head `f6dd78f3c8777ab150635f59a20bb276d8f0789a`.
- Trainer source: `51c7f480a844364a91cf1ee4ebd9dac18f6bb832`; clean, exact hash verified.
- Historical train/dev: 4,689 / 551 pairs; pair, endpoint and physical-run split-overlap gates previously passed. Complete input/model hashes revalidated in `/research/d7/spc/yzyang4/critic-component-g0/preflight-20260903-r1`.
- Model snapshot: `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`.
- Static-assets receipt SHA-256: `7ec7c836c7e0319638922021cc97d39f7af505da0bcb33658c392bf4523ba841`.

## Runtime repair before submission

Original Torch 2.5.1+cu121 had no compiled `sm_120` target; trainer import alone was not sufficient. First fresh-runtime installation failed on disk quota; a whole-site-packages overlay then failed `pip check` due to unrelated parent-environment conflicts. Both failures preceded all GPU submissions and model fits. Logs remain under `runtime-setup-20260903-r1` and `-r2`; only r1's own disposable download cache and empty temporary directory were removed. No experiment data or existing environment was deleted or overwritten.

The accepted r3 environment exposes only the recursive dependency closure (65 distributions, 161 links), reusing existing CUDA/Torch binaries and newly installed small dependencies without modifying their backing environments. It is an installation-specific environment, not a portable bundle. `PYTHONDONTWRITEBYTECODE=1` is passed to the allocation.

- Runtime: `/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective`.
- Python 3.11.15; Torch 2.11.0+cu128 with `sm_120`; NumPy 1.26.4; Transformers 5.12.1; Accelerate 1.14.0; DeepSpeed 0.19.3.
- `pip check`: no broken requirements; exact trainer import and CPUAdam builder compatibility passed on CPU.
- Dependency closure SHA-256: `5fad91f03344543e5389d0bf85438256b3eb4fed5aa0e8928f7c36e9875bf017`.
- Runtime compatibility receipt SHA-256: `91ee57b5ea61d8469495e57307e9ed746d5140cc36008fb4679aa91afce54d5e`.
- **GPU execution remains unvalidated until the allocation runs.** Installed package versions, backing RECORD hashes and critical binary hashes are included in the adjacent JSON receipts. No full package-content audit is claimed.

## Completion and interpretation

The existing monitor follows job 12181 only. No automatic retry, additional GPU/API work, or five-arm training is authorized. Completion requires the frozen independent verifier, step/checkpoint/evaluation cardinality, input/source/model hashes, timing events, two-GPU telemetry and finite metrics. A scheduler `COMPLETED` state alone is insufficient.

G0 estimates actual training/evaluation cost for the pre-existing global-quality-to-local-sibling calibration question. It neither tests the five-arm hypothesis nor provides evidence of capacity scaling. Its historical dev score must not select the model or be presented as a positive method result. Once validated, use walltime to quote a concrete five-arm configuration/run-count/GPU-hour budget; do not start that matrix without its authorization and data-identity gates.
