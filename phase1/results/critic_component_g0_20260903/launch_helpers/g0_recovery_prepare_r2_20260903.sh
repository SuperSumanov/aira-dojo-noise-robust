#!/usr/bin/env bash
# No sbatch here. All model/data inputs remain pinned; CPU verification only.
set -Eeo pipefail
set +u
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf GIT_LFS_SKIP_SMUDGE=1 PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
readonly control=/research/d7/spc/yzyang4/worktrees/g0_recovery_94ad7da_sparse
readonly oldcontrol=/research/d7/spc/yzyang4/worktrees/g0_shared_a99bf8a_nosmudge
readonly source_root=/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b
readonly runtime=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective
readonly root=/research/d7/spc/yzyang4/critic-component-g0/recovery-preflight-20260903-r2
test ! -e "$root"
test ! -e "$control"
mkdir -m 0700 "$root"
exec >"$root/preflight.log" 2>&1
trap 'rc=$?; printf "preflight_exit=%s\n" "$rc" >"$root/exit_status.txt"' EXIT
git -C "$oldcontrol" fetch https://github.com/SuperSumanov/aira-dojo-noise-robust.git phase1-value-critic
git -C "$oldcontrol" cat-file -e 94ad7dafff1866c6d50eb54927a4bf56547facc2^{commit}
git -C "$oldcontrol" worktree add --detach --no-checkout "$control" 94ad7dafff1866c6d50eb54927a4bf56547facc2
git -C "$control" sparse-checkout set --no-cone \
 '/phase1/verify_critic_component_g0.py' \
 '/phase1/scripts/critic_component_g0_worker_20260821.sh' \
 '/phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch' \
 '/phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256' \
 '/phase1/tests/test_verify_critic_component_g0.py'
git -C "$control" checkout --detach 94ad7dafff1866c6d50eb54927a4bf56547facc2
test -z "$(git -C "$control" status --porcelain --untracked-files=all)"
test "$(git -C "$source_root" rev-parse HEAD)" = 5f3bc362db922c8edee2ef134656dfdb9a2b74fb
test -z "$(git -C "$source_root" status --porcelain --untracked-files=all)"
cd "$control"
/research/d7/spc/yzyang4/venvs/exp/bin/python -m pytest -p no:cacheprovider phase1/tests/test_verify_critic_component_g0.py -q >"$root/focused_tests.txt" 2>&1
"$runtime/bin/python" phase1/verify_critic_component_g0.py assets \
 --source-root "$source_root" --expected-source-commit 5f3bc362db922c8edee2ef134656dfdb9a2b74fb \
 --train-pairs /research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl \
 --dev-pairs /research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl \
 --cards /research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json \
 --model-snapshot /research/d7/spc/yzyang4/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1 \
 --model-manifest "$control/phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256" \
 --receipt "$root/static_assets_receipt.json"
"$runtime/bin/python" /tmp/g0_recovery_bound_recheck_20260903.py >"$root/recovery_binding.json"
sha256sum phase1/verify_critic_component_g0.py phase1/scripts/critic_component_g0_worker_20260821.sh \
 phase1/scripts/critic_component_g0_shared_pro6000_20260821.sbatch >"$root/control.sha256"
printf 'RECOVERY_PREFLIGHT_COMPLETE gpu_jobs=0 model_fits=0\n' >"$root/COMPLETE"
