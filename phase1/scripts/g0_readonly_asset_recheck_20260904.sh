#!/usr/bin/env bash
set -Eeo pipefail
set +u
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf PYTHONDONTWRITEBYTECODE=1
export CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
readonly control=/research/d7/spc/yzyang4/worktrees/g0_recovery_94ad7da_sparse
readonly source_root=/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b
readonly runtime=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective
readonly output=/research/d7/spc/yzyang4/critic-component-g0/source-repair-12288-20260904
readonly old=/research/d7/spc/yzyang4/critic-component-g0/recovery-preflight-20260903-r3
test -f "$output/repair.json"
test ! -e "$output/recheck.log"
exec >"$output/recheck.log" 2>&1
trap 'rc=$?; printf "recheck_exit=%s\n" "$rc" >"$output/recheck_exit.txt"' EXIT
cd "$output"
test "$(git -C "$control" rev-parse HEAD)" = 94ad7dafff1866c6d50eb54927a4bf56547facc2
test "$(git -C "$source_root" rev-parse HEAD)" = 5f3bc362db922c8edee2ef134656dfdb9a2b74fb
test -z "$(git -C "$control" status --porcelain --untracked-files=all)"
test -z "$(git -C "$source_root" status --porcelain --untracked-files=all)"
( cd "$control" && sha256sum -c "$old/control.sha256" )
"$runtime/bin/python" -B "$control/phase1/verify_critic_component_g0.py" assets \
 --source-root "$source_root" --expected-source-commit 5f3bc362db922c8edee2ef134656dfdb9a2b74fb \
 --train-pairs /research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl \
 --dev-pairs /research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl \
 --cards /research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json \
 --model-snapshot /research/d7/spc/yzyang4/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1 \
 --model-manifest "$control/phase1/manifests/qwen3-1.7b-base-ea980cb0a6c2ae4b936e82123acc929f1cec04c1.sha256" \
 --receipt "$output/static_assets_receipt.json"
"$runtime/bin/python" -B /tmp/g0_recovery_bound_recheck_20260903.py >"$output/recovery_binding.json"
test -z "$(git -C "$source_root" status --porcelain --untracked-files=all)"
printf 'RECHECK_COMPLETE_NO_SUBMISSION\n' >"$output/COMPLETE"
