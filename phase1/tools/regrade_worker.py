"""Re-grade arm — worker. For each manifest node x K reps: re-EXECUTE the node's code in the SAME
container image with the task's public data (offline env = our collection regime), then grade the
produced submission with the external pristine grader (mlebench grade-sample). Appends JSONL results:
{card_id, competition, rep, exec_rc, wall_s, score, orig_graded}. Resume-safe (skips done (id,rep)).
Usage: python regrade_worker.py --manifest M --out O [--k 3] [--cap 1500] [--limit N]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--manifest", default="/research/d7/spc/yzyang4/aira-dojo/phase1/regrade_manifest.jsonl")
ap.add_argument("--out", default="/research/d7/spc/yzyang4/aira-dojo/phase1/regrade_results.jsonl")
ap.add_argument("--k", type=int, default=3)
ap.add_argument("--cap", type=int, default=1500)
ap.add_argument("--limit", type=int, default=0, help="max (node,rep) executions this invocation (0=all)")
ap.add_argument("--online", action="store_true",
                help="match the ONLINE collection regime (HF downloads via proxy) instead of offline")
ap.add_argument("--dry-count", action="store_true", help="print remaining (node,rep) count and exit")
a = ap.parse_args()

SIF = "/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif"
DATADIR = os.environ.get("MLE_BENCH_DATA_DIR", "/research/d7/spc/yzyang4/mle-bench-data")
GRADER = "/research/d7/spc/yzyang4/venvs/exp/bin/mlebench"
WORKBASE = Path(os.environ.get("REGRADE_WORK", "/research/d7/spc/yzyang4/scratch/regrade_work"))

# OpenCL-in-container fix: stage node's driver-matched nvvm lib once; bind ICD + staged dir.
import shutil as _sh
NVFIX = WORKBASE / "nvfix"
NV_OK = False
try:
    NVFIX.mkdir(parents=True, exist_ok=True)
    _sh.copy("/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4", NVFIX / "libnvidia-nvvm.so.4")
    NV_OK = os.path.exists("/etc/OpenCL/vendors/nvidia.icd")
except Exception as e:
    print(f"[regrade] opencl-fix staging unavailable: {e}", flush=True)
print(f"[regrade] opencl_fix={'ON' if NV_OK else 'OFF'}", flush=True)

done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        try:
            d = json.loads(l)
            done.add((d["card_id"], d["rep"]))
        except Exception:
            pass

nodes = [json.loads(l) for l in open(a.manifest) if l.strip()]
todo = [(nd, r) for nd in nodes for r in range(a.k) if (nd["card_id"], r) not in done]
if a.limit:
    todo = todo[:a.limit]
if a.dry_count:
    print(len(todo)); raise SystemExit(0)
print(f"[regrade] nodes={len(nodes)} k={a.k} done={len(done)} todo={len(todo)}", flush=True)

SCORE_RE = re.compile(r'"?score"?[=:]\s*([-+0-9.eE]+)')
for nd, rep in todo:
    comp = nd["competition"]
    wd = WORKBASE / f"{nd['card_id'][:40].replace('/', '_')}_r{rep}"
    shutil.rmtree(wd, ignore_errors=True)
    wd.mkdir(parents=True)
    (wd / "solution.py").write_text(nd["code"])
    pub = f"{DATADIR}/{comp}/prepared/public"
    t0 = time.time()
    binds = f"{wd}:/workspace,{pub}:/workspace/data:ro"
    envs = ["PYTHONUNBUFFERED=1", "WANDB_DISABLED=1", "TQDM_DISABLE=1",
            "TF_CPP_MIN_LOG_LEVEL=3", "HOME=/tmp", "HF_HOME=/tmp/hf"]
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
    cmd = ["timeout", str(a.cap), "singularity", "exec", "--containall", "--cleanenv", "--nv",
           "--pwd", "/workspace", "--bind", binds] + extra + [SIF, "env"] + envs + ["python", "solution.py"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    wall = round(time.time() - t0, 1)
    score = None
    sub = wd / "submission.csv"
    if sub.exists():
        g = subprocess.run([GRADER, "grade-sample", str(sub), comp, "--data-dir", DATADIR],
                           capture_output=True, text=True, timeout=600)
        m = SCORE_RE.search(g.stdout + g.stderr)
        score = float(m.group(1)) if m else None
    err_tail = (r.stderr or "")[-400:]
    rec = {"card_id": nd["card_id"], "competition": comp, "rep": rep, "exec_rc": r.returncode,
           "wall_s": wall, "score": score, "orig_graded": nd.get("graded"), "err_tail": err_tail}
    with open(a.out, "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(f"[regrade] {comp[:24]} {nd['card_id'][-8:]} rep{rep}: rc={r.returncode} wall={wall}s score={score} err={ascii(err_tail[-160:])}", flush=True)
    shutil.rmtree(wd, ignore_errors=True)   # 学长's note: clean agent workdirs
print("[regrade] REGRADE_WORKER_DONE", flush=True)
