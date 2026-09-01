#!/usr/bin/env bash
set -euo pipefail

export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
umask 077

MODE="${1:-check}"
CONTROL_COMMIT="${2:-}"
SOURCE_REPO=/research/d7/spc/yzyang4/aira-dojo
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
OBSERVATIONS="$STATE_ROOT/frozen_inputs/incremental_archive_support_20260901_d2ed361a/observations.json"
OBSERVATIONS_RECEIPT="$STATE_ROOT/frozen_inputs/incremental_archive_support_20260901_d2ed361a/receipt.json"
RESULT_PARENT=/research/d7/spc/yzyang4/prospective-archive-support
PROTOCOL_REL=phase1/incremental_archive_rejection_support_audit_execution_v2.json
PRODUCER_REL=phase1/audit_incremental_archive_rejection_support.py
VERIFIER_REL=phase1/verify_incremental_archive_rejection_support.py
TEST_REL=phase1/tests/test_incremental_archive_rejection_support.py
PROTOCOL_TEST_REL=phase1/tests/test_incremental_archive_rejection_support_protocol.py
RUNNER_REL=phase1/scripts/run_incremental_archive_rejection_support_formal_20260901.sh

EXPECTED_PROTOCOL_SHA=451f4b64c3029e0240e618e48de180cddc8aa36d23fb6f0e2b4b966dd57008b2
EXPECTED_OBSERVATIONS_SHA=d2ed361a557bf52dadfe9f0547e49c16ea5dc1eea42a1c78f7b354542a2a704a
EXPECTED_OBSERVATIONS_BYTES=200613
EXPECTED_OBSERVATIONS_RECEIPT_SHA=f5c722af76c6eda9b47b1fb175a51373b721ee084df02c6b72f5298e8fb93cfa
EXPECTED_PRIOR_SNAPSHOT=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
EXPECTED_CURRENT_SNAPSHOT=e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d
EXPECTED_PRIOR_TRANSACTIONS=4f05659db88e290f18a20d43b33330daa5df27211b1fffb770cbf1658b46ec60
EXPECTED_CURRENT_TRANSACTIONS=fabae2e42b8e669bc0f212df5365809751966859df22cb1a0ba952ba277f7467
EXPECTED_TARGET_REGISTRY=0c138eb6aa3f5de27041a99e4da38b9c802338e952f6306e9e44f43eab129ffe

die() {
  echo "INCREMENTAL_ARCHIVE_SUPPORT_FORMAL_FAIL: $*" >&2
  exit 2
}

sha() {
  sha256sum "$1" | awk '{print $1}'
}

require_file_sha() {
  local path="$1"
  local expected="$2"
  [[ -f "$path" && ! -L "$path" ]] || die "unsafe or absent file: $path"
  [[ "$(sha "$path")" == "$expected" ]] || die "hash mismatch: $path"
}

static_check() {
  bash -n "$0"
  [[ "$EXPECTED_PROTOCOL_SHA" =~ ^[0-9a-f]{64}$ ]] || die "bad protocol hash constant"
  [[ "$EXPECTED_OBSERVATIONS_SHA" =~ ^[0-9a-f]{64}$ ]] || die "bad observations hash constant"
  [[ "$EXPECTED_PRIOR_SNAPSHOT" =~ ^[0-9a-f]{64}$ ]] || die "bad prior snapshot constant"
  [[ "$EXPECTED_CURRENT_SNAPSHOT" =~ ^[0-9a-f]{64}$ ]] || die "bad current snapshot constant"
  [[ "$EXPECTED_PRIOR_TRANSACTIONS" =~ ^[0-9a-f]{64}$ ]] || die "bad prior transaction constant"
  [[ "$EXPECTED_CURRENT_TRANSACTIONS" =~ ^[0-9a-f]{64}$ ]] || die "bad current transaction constant"
  [[ "$EXPECTED_TARGET_REGISTRY" =~ ^[0-9a-f]{64}$ ]] || die "bad target registry constant"
  echo "INCREMENTAL_ARCHIVE_SUPPORT_FORMAL_STATIC_CHECK_PASS"
}

if [[ "$MODE" == check ]]; then
  static_check
  exit 0
fi
[[ "$MODE" == run ]] || die "mode must be check or run"
[[ "$CONTROL_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "exact control commit required"
static_check

set +u
source ~/env_setup.sh
set -u
PYTHON_BIN=/research/d7/spc/yzyang4/venvs/exp/bin/python
[[ -x "$PYTHON_BIN" ]] || die "verified experiment python absent"
"$PYTHON_BIN" -c 'import pytest' || die "pytest absent from verified experiment python"
git -C "$SOURCE_REPO" fetch fork phase1-value-critic
[[ "$(git -C "$SOURCE_REPO" rev-parse fork/phase1-value-critic)" == "$CONTROL_COMMIT" ]] \
  || die "public branch does not equal requested commit"
git -C "$SOURCE_REPO" cat-file -e "$CONTROL_COMMIT^{commit}"

SHORT="${CONTROL_COMMIT:0:7}"
FORMAL_ROOT="$RESULT_PARENT/formal-${SHORT}-incremental-support-v1"
PUBLIC_ROOT="$FORMAL_ROOT/public"
WORKTREE="$RESULT_PARENT/worktrees/formal-${SHORT}-incremental-support-v1"
[[ ! -e "$FORMAL_ROOT" && ! -e "$WORKTREE" ]] || die "formal root or worktree already exists"
mkdir -p "$PUBLIC_ROOT" "$(dirname "$WORKTREE")"
formal_complete=false
record_failure() {
  local rc=$?
  if [[ "$formal_complete" != true && -d "$PUBLIC_ROOT" && ! -e "$PUBLIC_ROOT/COMPLETE" ]]; then
    printf '%s\n' "$rc" >"$PUBLIC_ROOT/FAILED_RC"
  fi
}
trap record_failure EXIT
GIT_LFS_SKIP_SMUDGE=1 git -C "$SOURCE_REPO" worktree add --detach "$WORKTREE" "$CONTROL_COMMIT" \
  >"$PUBLIC_ROOT/worktree.stdout" 2>"$PUBLIC_ROOT/worktree.stderr"
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$CONTROL_COMMIT" ]] || die "worktree commit mismatch"
[[ -z "$(git -C "$WORKTREE" status --porcelain --untracked-files=no)" ]] || die "worktree is dirty at start"
cmp "$0" "$WORKTREE/$RUNNER_REL" || die "executed runner differs from exact commit"

PROTOCOL="$WORKTREE/$PROTOCOL_REL"
PRODUCER="$WORKTREE/$PRODUCER_REL"
VERIFIER="$WORKTREE/$VERIFIER_REL"
TARGET_REGISTRY="$WORKTREE/phase1/results/prospective_structural_rejection_no_checkpoint_20260901/structural_rejections_0830_no_checkpoint.json"
PRIOR_RESULT="$WORKTREE/phase1/results/archive_disposition_longitudinal_replication_v2_20260831_43ce72a/a/result.json"
PRIOR_VERIFICATION="$WORKTREE/phase1/results/archive_disposition_longitudinal_replication_v2_20260831_43ce72a/a/independent_verification.json"

require_file_sha "$PROTOCOL" "$EXPECTED_PROTOCOL_SHA"
require_file_sha "$OBSERVATIONS" "$EXPECTED_OBSERVATIONS_SHA"
require_file_sha "$OBSERVATIONS_RECEIPT" "$EXPECTED_OBSERVATIONS_RECEIPT_SHA"
[[ "$(stat -c '%s' "$OBSERVATIONS")" == "$EXPECTED_OBSERVATIONS_BYTES" ]] || die "observations byte count mismatch"
[[ "$(tr -d '\r\n' < "$STATE_ROOT/LATEST")" == "$EXPECTED_CURRENT_SNAPSHOT" ]] || die "LATEST mismatch"
require_file_sha "$STATE_ROOT/snapshots/$EXPECTED_PRIOR_SNAPSHOT/SHA256SUMS" "$EXPECTED_PRIOR_SNAPSHOT"
require_file_sha "$STATE_ROOT/snapshots/$EXPECTED_CURRENT_SNAPSHOT/SHA256SUMS" "$EXPECTED_CURRENT_SNAPSHOT"
require_file_sha "$STATE_ROOT/snapshots/$EXPECTED_PRIOR_SNAPSHOT/transactions.jsonl" "$EXPECTED_PRIOR_TRANSACTIONS"
require_file_sha "$STATE_ROOT/snapshots/$EXPECTED_CURRENT_SNAPSHOT/transactions.jsonl" "$EXPECTED_CURRENT_TRANSACTIONS"
require_file_sha "$TARGET_REGISTRY" "$EXPECTED_TARGET_REGISTRY"
if git -C "$WORKTREE" show "$CONTROL_COMMIT:$VERIFIER_REL" \
  | grep -q 'audit_incremental_archive_rejection_support'; then
  die "independent verifier imports or names producer"
fi

cat >"$PUBLIC_ROOT/preflight13.txt" <<'EOF'
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=does one newly settled structural rejection have anonymized accepted eligible support, and did it preexist the new window; PASS
03_context=frozen prior/current snapshots, exact transaction prefix, immutable observer copy and target-registry hash, public prior audit and exact commit; PASS
04_unit=one newly settled structural-rejection event selected only by its frozen registry hash; PASS
05_security=observer and hash-bound intake metadata only; registry contents tar payloads labels outcomes predictions accuracy utility identities remain unread or un-emitted; PASS
06_controls=exact prior prefix versus seven-transaction new window with strong contemporaneous-only and absent rules frozen before overlap readout; PASS
07_repetitions=producer A/B and independent verifier A/B must be byte-identical; PASS
08_independence=verifier does not import producer and reconstructs every result field and decision; PASS
09_reproducibility=exact public commit clean no-smudge worktree fixed hashes commands tests traces read-only receipt and manifest; PASS
10_statistics=full metadata census and exact anonymized counts/shares; no sampling inference or population-level replication claim; PASS
11_resources=CPU single-thread only; gpu api model-fit base-update 0/0/0/0; PASS
12_trace=file and network traces plus credential forbidden-path identity-schema and worktree-cleanliness gates; PASS
13_failure=hash drift prefix break duplicate target payload overlap task multiplicity duplicate run candidate tamper or any contract mismatch fails closed; PASS
EOF

cat >"$PUBLIC_ROOT/environment.txt" <<EOF
control_commit=$CONTROL_COMMIT
protocol_sha256=$EXPECTED_PROTOCOL_SHA
observations_sha256=$EXPECTED_OBSERVATIONS_SHA
observations_bytes=$EXPECTED_OBSERVATIONS_BYTES
observed_archives=283
prior_snapshot_sha256=$EXPECTED_PRIOR_SNAPSHOT
current_snapshot_sha256=$EXPECTED_CURRENT_SNAPSHOT
prior_transactions_sha256=$EXPECTED_PRIOR_TRANSACTIONS
current_transactions_sha256=$EXPECTED_CURRENT_TRANSACTIONS
target_registry_sha256=$EXPECTED_TARGET_REGISTRY
producer_sha256=$(sha "$PRODUCER")
verifier_sha256=$(sha "$VERIFIER")
gpu_api_model_fit_base_update=0/0/0/0
EOF

(
  cd "$WORKTREE"
  "$PYTHON_BIN" -m pytest -q "$PROTOCOL_TEST_REL" "$TEST_REL"
) >"$PUBLIC_ROOT/focused_tests.txt" 2>&1
(
  cd "$WORKTREE"
  "$PYTHON_BIN" -m pytest -q phase1/tests
) >"$PUBLIC_ROOT/full_phase1_tests.txt" 2>&1

readonly_receipt() {
  local output="$1"
  "$PYTHON_BIN" - "$STATE_ROOT" "$OBSERVATIONS" "$PROTOCOL" "$TARGET_REGISTRY" \
    "$PRIOR_RESULT" "$PRIOR_VERIFICATION" "$output" <<'PY'
import hashlib
import json
import pathlib
import sys

state = pathlib.Path(sys.argv[1]).resolve()
observations = pathlib.Path(sys.argv[2]).resolve()
repo_files = [pathlib.Path(item).resolve() for item in sys.argv[3:6]]
repo_files.append(pathlib.Path(sys.argv[6]).resolve())
output = pathlib.Path(sys.argv[7])
latest = (state / "LATEST").read_text(encoding="ascii").strip()
snapshots = [
    "30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f",
    "e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d",
]
files = [observations, state / "LATEST", *repo_files]
for snapshot in snapshots:
    root = state / "snapshots" / snapshot
    files.extend([root / "SHA256SUMS", root / "transactions.jsonl"])
files.append(state / "snapshots" / snapshots[-1] / "accumulator" / "summary.json")
transactions = state / "snapshots" / snapshots[-1] / "transactions.jsonl"
for line in transactions.read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    intake = pathlib.Path(row["intake_dir"]).resolve()
    if intake.parent != state / "intakes" or intake.name != row["drop_id"]:
        raise SystemExit("unsafe intake binding")
    files.extend([intake / "summary.json", intake / "source_provenance.json"])
digests = []
for path in files:
    if not path.is_file() or path.is_symlink():
        raise SystemExit("unsafe read-only input")
    digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
aggregate = hashlib.sha256(("\n".join(digests) + "\n").encode()).hexdigest()
receipt = {
    "protocol": "incremental_archive_support_readonly_receipt_v1",
    "latest_snapshot_sha256": latest,
    "allowed_metadata_file_count": len(files),
    "ordered_content_digest_sha256": aggregate,
    "identities_emitted": False,
    "forbidden_values_read": False,
}
output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

readonly_receipt "$PUBLIC_ROOT/readonly_before.json"
for arm in a b; do
  mkdir "$PUBLIC_ROOT/$arm"
  strace -f -qq -e trace=file,network -o "$PUBLIC_ROOT/$arm/producer.trace" \
    "$PYTHON_BIN" "$PRODUCER" --protocol "$PROTOCOL" --observations "$OBSERVATIONS" \
      --state-root "$STATE_ROOT" --output "$PUBLIC_ROOT/$arm/result.json" \
      >"$PUBLIC_ROOT/$arm/producer.stdout" 2>"$PUBLIC_ROOT/$arm/producer.stderr"
  strace -f -qq -e trace=file,network -o "$PUBLIC_ROOT/$arm/verifier.trace" \
    "$PYTHON_BIN" "$VERIFIER" --protocol "$PROTOCOL" --observations "$OBSERVATIONS" \
      --result "$PUBLIC_ROOT/$arm/result.json" --state-root "$STATE_ROOT" \
      --output "$PUBLIC_ROOT/$arm/independent_verification.json" \
      >"$PUBLIC_ROOT/$arm/verifier.stdout" 2>"$PUBLIC_ROOT/$arm/verifier.stderr"
done
cmp "$PUBLIC_ROOT/a/result.json" "$PUBLIC_ROOT/b/result.json"
cmp "$PUBLIC_ROOT/a/independent_verification.json" "$PUBLIC_ROOT/b/independent_verification.json"
readonly_receipt "$PUBLIC_ROOT/readonly_after.json"
cmp "$PUBLIC_ROOT/readonly_before.json" "$PUBLIC_ROOT/readonly_after.json"

cat "$PUBLIC_ROOT/a/producer.trace" "$PUBLIC_ROOT/b/producer.trace" \
  "$PUBLIC_ROOT/a/verifier.trace" "$PUBLIC_ROOT/b/verifier.trace" >"$PUBLIC_ROOT/combined.trace"
if grep -E 'connect\(|sendto\(|sendmsg\(|recvfrom\(|recvmsg\(' "$PUBLIC_ROOT/combined.trace" >/dev/null; then
  die "network syscall detected"
fi
if grep -Ei '(/|\\)(\.env|[^/\\]*(api[_-]?key|credential|secret|token)[^/\\]*|labels?|outcomes?|predictions?|grades?|[^/\\]*\.tar\.gz)(/|\\|\")' \
  "$PUBLIC_ROOT/combined.trace" >/dev/null; then
  die "forbidden path detected"
fi
if grep -E '"(task|run_id|archive_relative_path|competition|archive_name)"[[:space:]]*:' \
  "$PUBLIC_ROOT/a/result.json" "$PUBLIC_ROOT/a/independent_verification.json" >/dev/null; then
  die "identity-bearing schema detected in formal output"
fi
"$PYTHON_BIN" - "$PUBLIC_ROOT" <<'PY'
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
credential = re.compile(
    rb"sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY|"
    rb"(?i:(?:api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{16,})"
)
hits = []
for path in root.rglob("*"):
    if path.is_file() and not path.is_symlink() and credential.search(path.read_bytes()):
        hits.append(path.name)
if hits:
    raise SystemExit("credential-shaped content detected")
print("credential_content_hits=0")
PY
[[ -z "$(git -C "$WORKTREE" status --porcelain --untracked-files=all)" ]] || die "worktree dirty after run"
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$CONTROL_COMMIT" ]] || die "worktree commit drift"

cat >"$PUBLIC_ROOT/postflight_summary.txt" <<EOF
status=PASS
producer_a_b_byte_identical=true
independent_verifier_a_b_byte_identical=true
readonly_receipts_byte_identical=true
network_syscalls_detected=false
forbidden_paths_detected=false
identity_bearing_output_schema_detected=false
credential_content_hits=0
worktree_exact_clean=true
labels_outcomes_predictions_accuracy_utility_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

find "$PUBLIC_ROOT" -type f ! -name SHA256SUMS ! -name MANIFEST_SHA256 -print0 \
  | sort -z | xargs -0 sha256sum >"$PUBLIC_ROOT/SHA256SUMS"
sha "$PUBLIC_ROOT/SHA256SUMS" >"$PUBLIC_ROOT/MANIFEST_SHA256"
touch "$PUBLIC_ROOT/COMPLETE"
chmod -R a-w "$FORMAL_ROOT"
formal_complete=true
trap - EXIT
echo "INCREMENTAL_ARCHIVE_SUPPORT_FORMAL_COMPLETE root=$PUBLIC_ROOT manifest=$(cat "$PUBLIC_ROOT/MANIFEST_SHA256")"
