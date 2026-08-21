# Component-split critic G0 static preflight

- Status: `G0_STATIC_ASSETS_PASS_SCHEDULER_PERMISSION_BLOCKED`.
- GPU jobs / API calls / held-out test reads: `0 / 0 / 0`.
- Patched training source: `51c7f480a844364a91cf1ee4ebd9dac18f6bb832`, clean detached worktree.
- Fixed input rows: train/dev=`4689/551`; Cards=`31742`; all byte sizes and SHA-256 values passed.
- Pinned model: `Qwen/Qwen3-1.7B-Base` at revision
  `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`; 10 files / 3,452,692,285 bytes all passed the
  repository-relative SHA-256 manifest.
- Offline config/tokenizer load passed: `model_type=qwen3`, `hidden_size=2048`, tokenizer size `151669`.
- Runtime: Python 3.12.13, torch 2.5.1+cu121, transformers 5.12.1, accelerate 1.14.0,
  DeepSpeed 0.19.3.
- Static asset verification finished in 34.23 seconds with exit status 0 and max RSS 737,016 KiB.
- Final receipt SHA-256: `da2774c0dabcd195a86d75d5580317301812629c161402ea49073cdd57f2ff7b`;
  verifier SHA-256: `f6cba4eb78c7bc3d9f344605c7450cd87dd57d8e133c52043ab4bc0592adc960`.
- Current user association is account/QoS `gpu/gpu`; both explicit and default `sbatch --test-only`
  attempts for `zliang_gpu` returned `allocation failure: Invalid qos specification`. No job was submitted.

The package is engineering-ready but is not a scientific result. It must not be submitted until the exact
1-run / 2-GPU / 2-hour hard-cap budget is approved and an authorized Pro6000 submitter is used.
