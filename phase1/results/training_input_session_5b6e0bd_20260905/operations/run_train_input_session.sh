#!/usr/bin/env bash
set -euo pipefail
umask 077
archive=/tmp/train_input_session_5b6e0bd.tar
test "$(sha256sum "$archive" | cut -d' ' -f1)" = 5f53119b6dea831cfd5352bd6a3c62d4143cb3bbf4f72c98147a28919455d567
root=$(mktemp -d /tmp/train-input-session-5b6e0bd-XXXXXX)
printf 'CPU_WORK_DIR=%s\n' "$root"
mkdir "$root/code"
tar -xf "$archive" -C "$root/code"
cd "$root/code"
export CUDA_VISIBLE_DEVICES= HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 GLOO_SOCKET_IFNAME=lo
export CRITIC_SESSION_COMMIT=5b6e0bdd65f3e42860fd40e2d28120de90ed6d7e
export TRITON_CACHE_DIR="$root/triton" TORCH_EXTENSIONS_DIR="$root/extensions"
export PYTHONPATH="$root/code"
py=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python
source_root=/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b
test "$(git -C "$source_root" rev-parse HEAD)" = 5f3bc362db922c8edee2ef134656dfdb9a2b74fb
test ! -w "$source_root"
trap 'printf "%s\n" "$?" > "$root/exit_status.txt"' EXIT
/research/d7/spc/yzyang4/venvs/exp/bin/python -B -m pytest -q -p no:cacheprovider \
  phase1/tests/test_global_local_training_inputs.py phase1/tests/test_training_input_session_fixture.py \
  phase1/tests/test_global_local_critic_session.py phase1/tests/test_global_local_critic_consumer.py > "$root/tests.txt" 2>&1
tail -n 2 "$root/tests.txt"
for repeat in a b; do
  /usr/bin/strace -f -qq -e trace=%file -o "$root/$repeat.trace" \
    "$py" -B -m phase1.scripts.validate_training_input_session_cpu_20260905 \
      --source-root "$source_root" --output "$root/$repeat" > "$root/$repeat.log" 2>&1
  tail -n 1 "$root/$repeat.log"
done
"$py" -B -m phase1.scripts.verify_training_input_session_cpu_20260905 --root "$root" > "$root/independent.log" 2>&1
printf 'TRAIN_INPUT_SESSION_AB_COMPLETE\n'
