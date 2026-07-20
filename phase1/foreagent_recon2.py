"""Recon 2: nail the schema of FOREAGENT's curated slice so we can build (code, self-report, external-grade, task).

Key questions:
 (1) solutions_subset_50 layout + how many solutions per task (slice size).
 (2) eval_output.json  -> which field is the EXTERNAL grade? is higher better?
 (3) metadata.json     -> does it carry the agent's SELF-REPORTED validation metric? (needed for our redundancy thesis)
 (4) task list + orientation source (leaderboard / grade.py).
"""
import os
import collections

os.environ.update({
    "https_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "http_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "HF_HOME": "/research/d7/spc/yzyang4/cache/hf",
    "HF_HUB_CACHE": "/research/d7/spc/yzyang4/cache/hf/hub",
})
from huggingface_hub import list_repo_files, hf_hub_download

REPO = "zjunlp/PredictBeforeExecute"
files = list_repo_files(REPO, repo_type="dataset")


def dl(path):
    return hf_hub_download(REPO, filename=path, repo_type="dataset")


def show(prefix, n=40):
    sub = [f for f in files if f.startswith(prefix)]
    print(f"\n### {prefix}  ({len(sub)} files)", flush=True)
    bn = collections.Counter(os.path.basename(f) for f in sub)
    print("  basenames:", dict(bn.most_common(12)), flush=True)
    # solution groups = dir holding a code.py
    groups = sorted(set(os.path.dirname(f) for f in sub if f.endswith("code.py")))
    print(f"  #solution groups (dirs with code.py): {len(groups)}", flush=True)
    # per-task counts if layout is prefix/<task>/...
    per = collections.Counter(f[len(prefix):].split("/")[0] for f in sub if f.endswith("code.py"))
    print(f"  #distinct level-1 under prefix: {len(per)}", flush=True)
    print("  sample per-level-1 code.py counts:", dict(list(per.items())[:10]), flush=True)
    for f in sub[:n]:
        print("   ", f, flush=True)


show("solutions_subset_50/")
show("solutions_subset_15/")

# tasks list
tnames = sorted(set(f.split("/")[1] for f in files if f.startswith("tasks/") and len(f.split("/")) > 2))
print(f"\n### TASKS ({len(tnames)}):", flush=True)
for t in tnames:
    print("   ", t, flush=True)

# ---- pull a few small JSONs from subset_50 to read fields ----
pref = "solutions_subset_50/"
evs = [f for f in files if f.startswith(pref) and f.endswith("eval_output.json")]
mds = [f for f in files if f.startswith(pref) and f.endswith("metadata.json")]
print(f"\nsubset_50: {len(evs)} eval_output.json, {len(mds)} metadata.json", flush=True)

if evs:
    p = dl(evs[0])
    print(f"\n=== EVAL_OUTPUT sample: {evs[0]}\n{open(p).read()[:2500]}", flush=True)
if mds:
    p = dl(mds[0])
    print(f"\n=== METADATA sample: {mds[0]}\n{open(p).read()[:2500]}", flush=True)

cds = [f for f in files if f.startswith(pref) and f.endswith("code.py")]
if cds:
    p = dl(cds[0])
    print(f"\n=== CODE head: {cds[0]}\n{''.join(open(p, encoding='utf-8', errors='replace').readlines()[:20])}", flush=True)

# task orientation hint: leaderboard.csv header + grade.py head for one task
lbs = [f for f in files if f.startswith("tasks/") and f.endswith("leaderboard.csv")]
if lbs:
    p = dl(lbs[0])
    print(f"\n=== LEADERBOARD head: {lbs[0]}\n{''.join(open(p, encoding='utf-8', errors='replace').readlines()[:4])}", flush=True)

print("\n=== recon2 done ===", flush=True)
