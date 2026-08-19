#!/usr/bin/env bash
set -euo pipefail

base=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/pair_mismatch_be51a27
result=/research/d7/spc/yzyang4/prospective_decision_v1/formal_pair_mismatch_be51a27
source_commit=be51a278ed02c03f3b277789684174bb449662db

git -C "$base" fetch myfork phase1-value-critic
test "$(git -C "$base" rev-parse myfork/phase1-value-critic^{commit})" != ""
test ! -e "$worktree"
test ! -e "$result"
git -C "$base" worktree add --detach "$worktree" "$source_commit"
test -z "$(git -C "$worktree" status --porcelain)"
bash "$worktree/phase1/scripts/run_senior_augmented_pair_mismatch_remote_20260819.sh" \
  "$worktree" "$source_commit" "$result"
