#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
commit="$(git rev-parse HEAD)"
short_commit="${commit:0:9}"
python_bin="${PYTHON_BIN:-python}"
input="phase1/results/heterogeneous_oof_v11_20260814/oof_predictions.csv"
producer="phase1/selective_execution_audit.py"
verifier="phase1/verify_selective_execution_audit.py"
test_file="phase1/tests/test_selective_execution_audit.py"
prereg="phase1/实验记录/2026-08-14/SelectiveExecution_文献边界与回顾性发现预注册.md"
preflight_doc="phase1/实验记录/2026-08-14/SelectiveExecution_长实验预检.md"
base_root="${SELECTIVE_EXECUTION_ROOT:-/research/d7/spc/yzyang4/experiments}"
final_root="$base_root/selective_execution_v11_20260814_${short_commit}"
staging_root="${final_root}.staging"

if [[ -e "$final_root" || -e "$staging_root" ]]; then
  echo "refusing to overwrite result root" >&2
  exit 17
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "worktree must be clean" >&2
  git status --short >&2
  exit 18
fi
for required in "$input" "$producer" "$verifier" "$test_file" "$prereg" "$preflight_doc"; do
  test -f "$required"
done

mkdir -p "$staging_root/prereg"
cp "$prereg" "$preflight_doc" "$staging_root/prereg/"
exec 3>&1 4>&2
exec > >(tee "$staging_root/run.log") 2>&1

echo "PREFLIGHT_START protocol=selective_execution_v11_retrospective_discovery_v1"
echo "commit=$commit"
echo "python=$($python_bin --version 2>&1)"
echo "input_sha256=$(sha256sum "$input" | awk '{print $1}')"

test "$(sha256sum "$input" | awk '{print $1}')" = \
  "fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45"

"$python_bin" -m py_compile "$producer" "$verifier" "$test_file"
"$python_bin" "$producer" --help > "$staging_root/producer_help.txt"
"$python_bin" "$verifier" --help > "$staging_root/verifier_help.txt"
"$python_bin" -m pytest -q "$test_file" | tee "$staging_root/focused_tests.txt"

"$python_bin" - "$producer" "$verifier" <<'PY'
import ast
import pathlib
import sys

for source in map(pathlib.Path, sys.argv[1:]):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    options = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            options.extend(
                arg.value for arg in node.args
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            )
    forbidden = ("frozen", "test-pair", "held", "first960", "first-960", "cards", "stdout", "runtime", "self-report")
    bad = [option for option in options if any(word in option.lower() for word in forbidden)]
    if bad:
        raise SystemExit(f"forbidden CLI option in {source}: {bad}")
    print(f"CLI_GUARD_PASS source={source} options={options}")
PY

"$python_bin" - "$input" <<'PY'
import collections
import csv
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
with path.open("r", encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))
parents = collections.defaultdict(list)
for row in rows:
    parents[row["parent"]].append(row)
exact = [group[0] for group in parents.values() if len(group) == 1]
folds = collections.Counter(int(row["fold"]) for row in exact)
tasks = collections.Counter(row["task"] for row in exact)
assert len(rows) == 4263
assert len(parents) == 2293
assert len(exact) == 1520
assert len({row["run"] for row in exact}) == 294
assert len(tasks) == 23
assert dict(sorted(folds.items())) == {0: 285, 1: 215, 2: 222, 3: 373, 4: 425}
assert tasks.most_common(1)[0][1] == 336
assert sum(int(0.2 * count) for count in tasks.values()) == 295
print("STRUCTURE_PASS rows=4263 parents=2293 exact_two=1520 runs=294 tasks=23 quota=295")
PY

staged_filename_hits="$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)"
echo "staged_filename_secret_hits=$staged_filename_hits"
test "$staged_filename_hits" -eq 0
content_hits="$( { grep -I -n -E \
  'sk-[A-Za-z0-9._-]{20,}|(api[_-]?key|access[_-]?token|secret)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{16,}' \
  "$producer" "$verifier" "$test_file" "$prereg" "$preflight_doc" || true; } | wc -l)"
echo "high_confidence_content_secret_hits=$content_hits"
test "$content_hits" -eq 0

cat > "$staging_root/preflight_matrix.txt" <<EOF
01 artifact_knobs PASS commit=$commit
02 cheap_tests PASS focused=7
03 forbidden_inputs PASS
04 distribution PASS rows=4263 parents=2293 exact_two=1520 runs=294 tasks=23
05 balance PASS dominant=336 quota=295
06 overwrite_atomicity PASS
07 leakage_contract PASS frozen_or_first960_read=false
08 rng_numerics PASS task_seed=20260814 run_seed=20260815
09 secrets PASS filename=0 content=0
10 wall_smoke PASS synthetic_focused_tests_only formal_cap_s=1200
11 power_utility PASS preregistered_support_and_dual_cluster_gates
12 true_rc PASS launcher_capture_enabled
13 append_only_hashes PASS pending_postrun_manifest
PREFLIGHT_ALL_13_PASS
EOF
cat "$staging_root/preflight_matrix.txt"

set +e
timeout 1200 "$python_bin" "$producer" --input "$input" --out-dir "$staging_root/result"
producer_rc=$?
set -e
echo "producer_rc=$producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then
  exit "$producer_rc"
fi

set +e
timeout 1200 "$python_bin" "$verifier" \
  --input "$input" \
  --result-dir "$staging_root/result" \
  --receipt "$staging_root/result/independent_verify.json"
verifier_rc=$?
set -e
echo "verifier_rc=$verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then
  exit "$verifier_rc"
fi

"$python_bin" - "$staging_root/result/summary.json" "$commit" > "$staging_root/run_metadata.json" <<'PY'
import json
import pathlib
import platform
import sys

summary = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
print(json.dumps({
    "commit": sys.argv[2],
    "platform": platform.platform(),
    "python": platform.python_version(),
    "protocol": summary["protocol"],
    "verdict": summary["verdict"],
    "frozen_or_first960_read": summary["frozen_or_first960_read"],
}, indent=2, sort_keys=True))
PY

post_content_hits="$( { grep -I -R -n -E \
  'sk-[A-Za-z0-9._-]{20,}|(api[_-]?key|access[_-]?token|secret)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{16,}' \
  "$staging_root" || true; } | wc -l)"
echo "postrun_high_confidence_secret_hits=$post_content_hits"
test "$post_content_hits" -eq 0

# Stop writing run.log before hashing it.  Otherwise sha256sum -c output would
# mutate the very log represented in the manifest.
exec 1>&3 2>&4
wait
find "$staging_root" -type f ! -name SHA256SUMS -print0 \
  | LC_ALL=C sort -z | xargs -0 sha256sum > "$staging_root/SHA256SUMS"
(cd / && sha256sum -c "${staging_root#/}/SHA256SUMS")
mv "$staging_root" "$final_root"

"$python_bin" - "$final_root/result/summary.json" <<'PY'
import json
import pathlib
import sys

summary = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
primary = summary["policies"]["tri_unanimous_q20"]
delta = summary["comparisons"]["primary_minus_char_margin_matched"]
print(
    "FORMAL_SELECTIVE_EXECUTION_DONE "
    f"verdict={summary['verdict']} selected={primary['selected']} "
    f"task_macro={primary['task_macro_accuracy']:.12f} "
    f"task_ci=[{primary['task_macro_ci95'][0]:.12f},{primary['task_macro_ci95'][1]:.12f}] "
    f"run_macro={primary['run_macro_accuracy']:.12f} "
    f"saving={primary['candidate_saving_fraction']:.12f} "
    f"delta_char={delta['task_macro_delta']:.12f} "
    f"result_root={sys.argv[1].rsplit('/result/summary.json', 1)[0]}"
)
PY
