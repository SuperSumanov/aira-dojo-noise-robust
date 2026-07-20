"""Recon FOREAGENT agent_runs: confirm (tree/parent links, per-node self-report, external grade, operators)
are all present before pulling a powered slice for the illusion-atlas. Also count runs/agents for power.
"""
import os
import json
import collections
import pprint

os.environ.update({
    "https_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "http_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "HF_HOME": "/research/d7/spc/yzyang4/cache/hf",
    "HF_HUB_CACHE": "/research/d7/spc/yzyang4/cache/hf/hub",
})
from huggingface_hub import list_repo_files, hf_hub_download

REPO = "zjunlp/PredictBeforeExecute"
files = list_repo_files(REPO, repo_type="dataset")
ar = [f for f in files if f.startswith("agent_runs/")]


def dl(p):
    return hf_hub_download(REPO, filename=p, repo_type="dataset")


# agents + runs
agents = sorted(set(f.split("/")[1] for f in ar if len(f.split("/")) > 2))
run_ids = sorted(set("/".join(f.split("/")[:3]) for f in ar if len(f.split("/")) > 2))
per_agent = collections.Counter(r.split("/")[1] for r in run_ids)
print("AGENTS under agent_runs:", agents, flush=True)
print("distinct runs:", len(run_ids), " per-agent:", dict(per_agent), flush=True)
bn = collections.Counter(os.path.basename(f) for f in ar)
print("agent_runs basenames (top20):", dict(bn.most_common(20)), flush=True)

jr = [f for f in ar if f.endswith("journal.json")]
fj = [f for f in ar if f.endswith("filtered_journal.json")]
md = [f for f in ar if f.endswith("metadata.json")]
ev = [f for f in ar if f.endswith("eval_output.json")]
print(f"counts: journal.json={len(jr)} filtered_journal={len(fj)} metadata.json={len(md)} eval_output.json={len(ev)}", flush=True)

# ---- journal.json: tree + parent + per-node self-report? ----
if jr:
    p = dl(jr[0]); j = json.load(open(p))
    print(f"\n=== journal.json sample: {jr[0]}", flush=True)
    print("top type:", type(j).__name__, flush=True)
    nodes = j if isinstance(j, list) else (j.get("nodes") or j.get("journal") or j.get("data"))
    if isinstance(j, dict):
        print("top keys:", list(j.keys())[:20], flush=True)
    if isinstance(nodes, list) and nodes:
        n0 = nodes[0]
        print(f"#nodes={len(nodes)}  first-node keys:", list(n0.keys()), flush=True)
        # show a node with a parent + metric, code trimmed
        for nd in nodes:
            if nd.get("parent") not in (None, "") or nd.get("parents"):
                pprint.pprint({k: (str(v)[:120] if k in ("code", "plan", "analysis", "term_out") else v)
                               for k, v in nd.items()}, width=140)
                break
        # what fields look like metric / parent across nodes
        keyset = collections.Counter()
        for nd in nodes:
            keyset.update(nd.keys())
        print("\nfield frequency across nodes:", dict(keyset), flush=True)

# ---- metadata.json: self-report / operator? ----
if md:
    p = dl(md[0]); print(f"\n=== metadata.json sample: {md[0]}\n{open(p).read()[:1800]}", flush=True)

print("\n=== recon done ===", flush=True)
