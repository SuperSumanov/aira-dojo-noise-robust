"""Download a MINIMAL slice of FOREAGENT (zjunlp/PredictBeforeExecute) subset_50 and parse into
(task, sid, code, external-grade) rows for the H1 de-risk. Pulls ONLY *.py + eval_output.json
(skips the big .pth/.npy/.csv). Also writes the GPU sbatch (LF, on-cluster, to avoid CRLF).
"""
import os
import json
import glob
from collections import Counter

os.environ.update({
    "https_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "http_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "HF_HOME": "/research/d7/spc/yzyang4/cache/hf",
    "HF_HUB_CACHE": "/research/d7/spc/yzyang4/cache/hf/hub",
})
from huggingface_hub import snapshot_download

ROOT = "/research/d7/spc/yzyang4/foreagent_slice"
os.makedirs(ROOT, exist_ok=True)
os.makedirs("/research/d7/spc/yzyang4/logs", exist_ok=True)

print("downloading subset_50 code + eval_output.json (skipping big model/data files) ...", flush=True)
snapshot_download(
    "zjunlp/PredictBeforeExecute", repo_type="dataset", local_dir=ROOT,
    allow_patterns=["solutions_subset_50/**/*.py", "solutions_subset_50/**/eval_output.json"],
    max_workers=8,
)

base = os.path.join(ROOT, "solutions_subset_50")
rows = []
for task in sorted(os.listdir(base)):
    cdir = os.path.join(base, task, "code")
    if not os.path.isdir(cdir):
        continue
    for pyf in sorted(glob.glob(os.path.join(cdir, "solution_*.py"))):
        name = os.path.basename(pyf)[:-3]
        evalf = os.path.join(cdir, "submission_" + name, "eval_output.json")
        if not os.path.exists(evalf):
            continue
        try:
            ev = json.load(open(evalf))
        except Exception:
            continue
        score = ev.get("score")
        if score is None or not ev.get("valid_submission", False):
            continue
        code = open(pyf, encoding="utf-8", errors="replace").read()
        if len(code.strip()) < 20:
            continue
        rows.append({
            "task": task, "sid": name, "code": code, "score": float(score),
            "is_lower_better": bool(ev.get("is_lower_better", False)),
            "beat_ratio": ev.get("beat_ratio"),
        })

json.dump(rows, open(os.path.join(ROOT, "slice.json"), "w"))
per = Counter(r["task"] for r in rows)
print(f"\nPARSED {len(rows)} graded solutions across {len(per)} tasks", flush=True)
for t, n in sorted(per.items()):
    print(f"  {t[:44]:44s} {n}", flush=True)

# write GPU sbatch (generated on-cluster => LF, no CRLF)
sb = "/research/d7/spc/yzyang4/scripts/foreagent_h1.sbatch"
with open(sb, "w") as f:
    f.write("#!/bin/bash\n")
    for line in ["-c 6", "-p gpu_2h", "--qos gpu", "--account gpu", "--gres=gpu:1",
                 "-C rtx3090", "-o /research/d7/spc/yzyang4/logs/foreagent_h1.%j.log"]:
        f.write(f"#SBATCH {line}\n")
    f.write("cd /research/d7/spc/yzyang4/aira-dojo\n")
    f.write("/research/d7/spc/yzyang4/venvs/critic/bin/python -m phase1.foreagent_h1\n")
print("\nwrote sbatch ->", sb, flush=True)
print("=== slice done ===", flush=True)
