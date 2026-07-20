"""Recon FOREAGENT public corpus (zjunlp/PredictBeforeExecute) structure BEFORE pulling any large slice.

Goal: understand how (solution code, external grade, task) are laid out so we can pull a MINIMAL slice
(a few tasks x few dozen solutions) to replicate H1 -- NOT the ~158GB whole thing. Also confirm the Qwen
extractor model + huggingface_hub are in place on the cluster.
"""
import os
import sys

os.environ.update({
    "https_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "http_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "HF_HOME": "/research/d7/spc/yzyang4/cache/hf",
    "HF_HUB_CACHE": "/research/d7/spc/yzyang4/cache/hf/hub",
})

MODEL = "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct"
print("Qwen extractor model present:", os.path.isdir(MODEL), flush=True)

try:
    import huggingface_hub as H
    print("huggingface_hub version:", H.__version__, flush=True)
except Exception as e:
    print("NO huggingface_hub in this venv:", repr(e), flush=True)
    sys.exit(0)

from huggingface_hub import list_repo_files

REPO = "zjunlp/PredictBeforeExecute"
try:
    files = list_repo_files(REPO, repo_type="dataset")
except Exception as e:
    print("ERR list_repo_files:", repr(e), flush=True)
    sys.exit(0)

print(f"\nN files in {REPO}: {len(files)}", flush=True)

# top-level layout
tops = {}
for f in files:
    t = f.split("/")[0]
    tops[t] = tops.get(t, 0) + 1
print("\nTOP-LEVEL entries (name -> file count):", flush=True)
for k in sorted(tops):
    print(f"  {k:40s} {tops[k]}", flush=True)

# guess where code + grades live: show distinct file basenames / extensions
import collections
bn = collections.Counter(os.path.basename(f) for f in files)
ext = collections.Counter(os.path.splitext(f)[1] for f in files)
print("\nfile extensions:", dict(ext), flush=True)
print("\ntop-30 basenames:", flush=True)
for name, c in bn.most_common(30):
    print(f"  {name:40s} {c}", flush=True)

print("\nsample full paths (first 40):", flush=True)
for f in files[:40]:
    print("  ", f, flush=True)

# a deeper path sample to see nesting under the first task-like dir
print("\nsample paths under the largest top dir:", flush=True)
big = max(tops, key=tops.get)
sub = [f for f in files if f.startswith(big + "/")][:40]
for f in sub:
    print("  ", f, flush=True)

print("\n=== recon done ===", flush=True)
