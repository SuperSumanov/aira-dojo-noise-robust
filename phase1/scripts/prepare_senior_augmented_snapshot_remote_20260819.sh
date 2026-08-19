#!/usr/bin/env bash
set -eo pipefail
source "$HOME/env_setup.sh"
set -u

REPO="/research/d7/spc/yzyang4/aira-dojo"
COMMIT="92a9651f2e13a9e43623235b82c07c19721bc2ee"
WORKTREE="/research/d7/spc/yzyang4/worktrees/senior_augmented_${COMMIT:0:7}_nosmudge"
FILES=(
  data/augmented_mle_critic/augmented_cards_current.json
  data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl
  data/augmented_mle_critic/runsplit_holdruns.json
  data/augmented_mle_critic/gap_filter.json
)

if [[ -e "$WORKTREE" ]]; then
  echo "PREEXISTING_TARGET=$WORKTREE" >&2
  exit 2
fi

git -C "$REPO" fetch fork dojo-reproduce
test "$(git -C "$REPO" rev-parse FETCH_HEAD)" = "$COMMIT"
GIT_LFS_SKIP_SMUDGE=1 git -C "$REPO" worktree add --detach "$WORKTREE" "$COMMIT"
git -C "$WORKTREE" lfs pull fork dojo-reproduce \
  --include="$(IFS=,; echo "${FILES[*]}")" \
  --exclude=""

cd "$WORKTREE"
test "$(sha256sum "${FILES[0]}" | cut -d' ' -f1)" = 5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb
test "$(stat -c%s "${FILES[0]}")" = 604190866
test "$(sha256sum "${FILES[1]}" | cut -d' ' -f1)" = c669d672d0a2aeee6da97393e3e832a312295aa5aebd7cd457ff297a27d4d9d2
test "$(stat -c%s "${FILES[1]}")" = 6025690
test "$(sha256sum "${FILES[2]}" | cut -d' ' -f1)" = 1323a43b2f52722a66c3fc84fb48e6d8d208c8b8c096eccf4bc7dc14937bb5de
test "$(stat -c%s "${FILES[2]}")" = 118448
test "$(sha256sum "${FILES[3]}" | cut -d' ' -f1)" = 9078f50c19cad880a5274b3f6197fbf3b90b4d3f2f867c97d8ba029a0d1c6891
test "$(stat -c%s "${FILES[3]}")" = 1282

# High-confidence, quiet scan.  Never print matched bytes.
credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
for file in "${FILES[@]}"; do
  if LC_ALL=C grep -aEq "$credential_pattern" "$file"; then
    echo "CREDENTIAL_SHAPED_BYTES_REFUSED=$file" >&2
    exit 2
  fi
done

test "$(git rev-parse HEAD)" = "$COMMIT"
test -z "$(git status --porcelain)"
echo "SENIOR_AUGMENTED_SNAPSHOT_READY commit=$COMMIT credential_files=0"
sha256sum "${FILES[@]}"
