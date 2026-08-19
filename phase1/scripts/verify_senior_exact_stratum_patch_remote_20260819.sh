#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u

base=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/senior_stratum_patch_92a9651
base_commit=92a9651f2e13a9e43623235b82c07c19721bc2ee
patch=${1:?patch path required}
expected_patch_sha=9f1445ae331846a4748cf82a41bebec7fd19fc28d28b4d8821c9f9333fa20f0a
python=/research/d7/spc/yzyang4/venvs/exp/bin/python
log=/research/d7/spc/yzyang4/prospective_decision_v1/stratum_patch_remote_verify_20260819.log

test "$(sha256sum "$patch" | cut -d' ' -f1)" = "$expected_patch_sha"
test ! -e "$worktree"
exec > >(tee "$log") 2>&1
cleanup() {
  if [[ -e "$worktree" ]]; then
    git -C "$base" worktree remove --force "$worktree"
  fi
}
trap cleanup EXIT

GIT_LFS_SKIP_SMUDGE=1 git -C "$base" worktree add --detach "$worktree" "$base_commit"
test "$(git -C "$worktree" rev-parse HEAD)" = "$base_commit"
git -C "$worktree" diff --quiet -- \
  src/mle_critic/scripts/preprocess/build_batch_value_pairs.sh \
  src/mle_critic/src/preprocess/build_bt_pairs \
  src/mle_critic/test
git -C "$worktree" apply --check "$patch"
git -C "$worktree" apply "$patch"
git -C "$worktree" diff --check

cd "$worktree"
"$python" -m py_compile \
  src/mle_critic/src/preprocess/build_bt_pairs/build_subtree_pairs.py \
  src/mle_critic/src/preprocess/build_bt_pairs/verify_experiment_strata.py
"$python" -m pytest -q \
  src/mle_critic/test/test_build_subtree_pairs.py::test_cross_config_nodes_are_never_paired \
  src/mle_critic/test/test_build_subtree_pairs.py::test_same_config_cross_run_pair_carries_contract_receipts \
  src/mle_critic/test/test_build_subtree_pairs.py::test_mixed_config_within_physical_run_fails_closed \
  src/mle_critic/test/test_verify_experiment_strata.py
git diff --stat
echo SENIOR_EXACT_STRATUM_PATCH_REMOTE_VERIFY_PASS
