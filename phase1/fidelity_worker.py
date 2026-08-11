"""Dose-response worker: run each candidate under wall-clock caps, record every signal that
emerged by the cap.

Adapted from tools/regrade_worker.py (same container, same binds, same offline regime, same
pristine grader) with the one design change the experiment is about: the run is CUT at T
seconds, and what we keep is exactly what a budget-T selection policy would have to act on:

  stdout_val   the last validation-like number the program printed before the cut,
               parsed with a metric-keyword battery (the self-report channel at fidelity T)
  sub_score    pristine grade of submission.csv IF the program managed to write one
  progressed   how many bytes of stdout it produced (a liveness diagnostic)

Each cap is a FRESH workspace and a fresh process: warm caches across caps would flatter
the low-fidelity points. Caps run smallest first so a crash surfaces early and cheaply.
Resume-safe on (card_id, cap). Full fidelity is NOT run here -- the corpus already paid
for it (val_at_low / graded).

Usage: python fidelity_worker.py --manifest M --out O [--caps 30,120] [--limit N]
"""
import argparse, json, os, re, shutil, subprocess, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--manifest", default="phase1/fidelity_smoke.jsonl")
ap.add_argument("--out", default="phase1/fidelity_results.jsonl")
ap.add_argument("--caps", default="30,120")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--online", action="store_true",
                help="HF downloads via proxy -- the regime the collection actually ran in")
ap.add_argument("--dry-count", action="store_true")
a = ap.parse_args()
CAPS = [int(x) for x in a.caps.split(",")]

SIF = "/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif"
DATADIR = os.environ.get("MLE_BENCH_DATA_DIR", "/research/d7/spc/yzyang4/mle-bench-data")
GRADER = "/research/d7/spc/yzyang4/venvs/exp/bin/mlebench"
WORKBASE = Path(os.environ.get("FIDELITY_WORK", "/tmp/fidelity_work"))
HFCACHE = Path(os.environ.get("REGRADE_HF_CACHE", "/research/d7/spc/yzyang4/scratch/hf_cache"))
WORKBASE.mkdir(parents=True, exist_ok=True)
HFCACHE.mkdir(parents=True, exist_ok=True)

NVFIX = WORKBASE / "nvfix"
NV_OK = False
try:
    NVFIX.mkdir(parents=True, exist_ok=True)
    shutil.copy("/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4", NVFIX / "libnvidia-nvvm.so.4")
    NV_OK = os.path.exists("/etc/OpenCL/vendors/nvidia.icd")
except Exception as e:
    print(f"[fid] opencl-fix unavailable: {e}", flush=True)

done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        try:
            d = json.loads(l)
            done.add((d["card_id"], d["cap"]))
        except Exception:
            pass

nodes = [json.loads(l) for l in open(a.manifest) if l.strip()]
todo = [(nd, c) for nd in nodes for c in sorted(CAPS) if (nd["card_id"], c) not in done]
if a.limit:
    todo = todo[:a.limit]
if a.dry_count:
    print(len(todo)); raise SystemExit(0)
print(f"[fid] nodes={len(nodes)} caps={CAPS} done={len(done)} todo={len(todo)}", flush=True)

# metric-keyword battery: last match wins; keyword'd patterns outrank a bare "score".
# The metric word is REQUIRED next to the val word -- with it optional, the smoke matched
# "validation images: 649" on kuzushiji and returned 649.0 as an F1.
KEYED = re.compile(
    r"(?i)\b(?:val(?:idation)?|cv|oof|dev|holdout)[^\n=:]{0,40}?"
    r"(?:score|acc(?:uracy)?|auc|rmse|rmsle|mae|logloss|log[- ]?loss|loss|f1|kappa|"
    r"map@?\d*|pearson|spearman|rho|corr)"
    r"[^\n0-9]{0,24}?(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)")
BARE = re.compile(r"(?i)\b(?:score|accuracy|auc|logloss|kappa|f1)\s*[=:]\s*"
                  r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)")


def parse_val(txt):
    m = None
    for m_ in KEYED.finditer(txt):
        m = m_
    if m:
        return float(m.group(1)), "keyed"
    for m_ in BARE.finditer(txt):
        m = m_
    if m:
        return float(m.group(1)), "bare"
    return None, None


SCORE_RE = re.compile(r'"?score"?[=:]\s*([-+0-9.eE]+)')
for nd, cap in todo:
    comp = nd["competition"]
    wd = WORKBASE / f"{nd['card_id'][-24:].replace('/', '_')}_c{cap}"
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    (wd / "solution.py").write_text(nd["code"])
    pub = f"{DATADIR}/{comp}/prepared/public"
    binds = f"{wd}:/workspace,{pub}:/workspace/data:ro,{HFCACHE}:/hf"
    envs = ["PYTHONUNBUFFERED=1", "WANDB_DISABLED=1", "TQDM_DISABLE=1",
            "TF_CPP_MIN_LOG_LEVEL=3", "HOME=/tmp", "HF_HOME=/hf", "TORCH_HOME=/hf/torch"]
    if a.online:
        envs += ["HF_HUB_OFFLINE=0",
                 "http_proxy=http://137.189.90.241:8000/",
                 "https_proxy=http://137.189.90.241:8000/",
                 "HF_HUB_DISABLE_XET=1"]
    else:
        envs.append("HF_HUB_OFFLINE=1")
    extra = []
    if NV_OK:
        extra = ["--bind", "/etc/OpenCL/vendors/nvidia.icd:/etc/OpenCL/vendors/nvidia.icd",
                 "--bind", f"{NVFIX}:/mnt"]
        envs.append("LD_LIBRARY_PATH=/mnt:/.singularity.d/libs")
    t0 = time.time()
    cmd = (["timeout", "--signal=KILL", str(cap), "singularity", "exec", "--containall",
            "--cleanenv", "--nv", "--pwd", "/workspace", "--bind", binds] + extra +
           [SIF, "env"] + envs + ["python", "solution.py"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 255 and time.time() - t0 < 3:
        # instant 255 with no output is container startup contention, not the solution;
        # one retry after a pause before letting it stand as a result
        time.sleep(20)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
    wall = round(time.time() - t0, 1)
    out = (r.stdout or "")
    err = (r.stderr or "")
    # solutions log through either stream (tqdm/logging default to stderr); the agent
    # runtime that produced val_at_low saw the combined output, so the parser must too
    val, how = parse_val(out + "\n" + err)
    sub_score = None
    sub = wd / "submission.csv"
    if sub.exists():
        try:
            g = subprocess.run([GRADER, "grade-sample", str(sub), comp,
                                "--data-dir", DATADIR],
                               capture_output=True, text=True, timeout=600)
            m = SCORE_RE.search(g.stdout + g.stderr)
            sub_score = float(m.group(1)) if m else None
        except subprocess.TimeoutExpired:
            pass
    rec = {"card_id": nd["card_id"], "competition": comp, "cap": cap, "rc": r.returncode,
           "wall_s": wall, "stdout_val": val, "val_how": how,
           "sub_exists": sub.exists(), "sub_score": sub_score,
           "stdout_bytes": len(out), "stderr_bytes": len(err),
           "parent": nd.get("parent"),
           "stratum": nd.get("stratum"), "graded": nd.get("graded"),
           "val_at_low": nd.get("val_at_low"),
           "stdout_tail": out[-500:], "err_tail": err[-400:]}
    with open(a.out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[fid] {comp[:22]} {nd['card_id'][-8:]} cap={cap}: rc={r.returncode} "
          f"wall={wall} val={val}({how}) sub={sub.exists()}/{sub_score} "
          f"bytes={len(out)}", flush=True)
    shutil.rmtree(wd, ignore_errors=True)
print("[fid] FIDELITY_WORKER_DONE", flush=True)
