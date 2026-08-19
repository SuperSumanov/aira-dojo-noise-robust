#!/usr/bin/env bash
set -eo pipefail

base=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/pair_mismatch_5396d84
result=/research/d7/spc/yzyang4/prospective_decision_v1/formal_pair_mismatch_5396d84
source_commit=5396d847ada82aa5444c39061a7ed5a5fa25cbbd

source ~/env_setup.sh
set -u
git -C "$base" cat-file -e "$source_commit^{commit}"
test ! -e "$worktree"
test ! -e "$result"
GIT_LFS_SKIP_SMUDGE=1 git -C "$base" worktree add --detach "$worktree" "$source_commit"
test -z "$(git -C "$worktree" status --porcelain)"
bash "$worktree/phase1/scripts/run_senior_augmented_pair_mismatch_remote_20260819.sh" \
  "$worktree" "$source_commit" "$result"
