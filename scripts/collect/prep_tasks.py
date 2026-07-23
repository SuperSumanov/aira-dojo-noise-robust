"""Portable prep for the 12-task collection split (学长 2026-07-24).
Run with the dojo venv python from the repo root:  python scripts/collect/prep_tasks.py
Needs: Kaggle rules accepted on the web for each competition; ~/.kaggle/kaggle.json; proxy env if applicable.
Idempotent; robust verification (description.md present AND prepared >50KB — guards against the
empty-dir false positive when rules aren't accepted); creates task yaml + prepared/public.tar (sand needs it).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TCDIR = REPO / "src/dojo/configs/task/mlebench"

# .env for MLE_BENCH_DATA_DIR
for line in (REPO / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))
DATADIR = os.environ.get("MLE_BENCH_DATA_DIR")
assert DATADIR, "MLE_BENCH_DATA_DIR missing (.env)"
MLEBENCH = str(Path(sys.executable).parent / "mlebench")
if not os.path.exists(MLEBENCH):
    MLEBENCH = shutil.which("mlebench") or sys.exit("mlebench CLI not found in venv/PATH")

TRAIN = ["leaf-classification", "kuzushiji-recognition", "petfinder-pawpularity-score",
         "random-acts-of-pizza", "spooky-author-identification", "google-quest-challenge",
         "tabular-playground-series-may-2022", "text-normalization-challenge-english-language",
         "mlsp-2013-birds"]
VAL = ["text-normalization-challenge-russian-language", "tweet-sentiment-extraction",
       "whale-categorization-playground"]


def robust_ok(t):
    pub = Path(DATADIR) / t / "prepared/public"
    if not (pub / "description.md").is_file():
        return False, 0
    r = subprocess.run(f"du -sk {DATADIR}/{t}/prepared", shell=True, capture_output=True, text=True)
    kb = int(r.stdout.split()[0]) if r.stdout.split() and r.stdout.split()[0].isdigit() else 0
    return kb > 50, kb


results = {}
for t in TRAIN + VAL:
    yaml = TCDIR / f"{t}.yaml"
    if not yaml.exists():
        yaml.write_text(f"# @package task\n\ndefaults:\n - mlebench/_default\n\nname: {t}\n")
    ok, kb = robust_ok(t)
    if not ok:
        print(f"===== preparing {t} =====", flush=True)
        try:
            r = subprocess.run(f"{MLEBENCH} prepare -c {t} --data-dir {DATADIR} < /dev/null",
                               shell=True, capture_output=True, text=True, timeout=5400)
            tail = ((r.stdout or "") + (r.stderr or ""))[-300:]
        except subprocess.TimeoutExpired:
            tail = "TIMEOUT 90min"
        ok, kb = robust_ok(t)
        blocked = "accept" in tail.lower() and ("EOF" in tail or "prompt_user" in tail)
        results[t] = "PREPARED (%dKB)" % kb if ok else ("RULES-BLOCKED -> accept at kaggle.com/c/%s/rules" % t if blocked else "FAILED: " + tail[-140:])
    else:
        results[t] = f"already prepared ({kb}KB)"
    if ok:
        tarp = Path(DATADIR) / t / "prepared/public.tar"
        if not tarp.exists():
            subprocess.run(f"tar -cf {tarp} -C {DATADIR}/{t}/prepared public", shell=True)

print("\n===== SUMMARY =====")
for t, s in results.items():
    grp = "TRAIN" if t in TRAIN else "VAL"
    print(f"  [{grp}] {t:48s} {s}")
