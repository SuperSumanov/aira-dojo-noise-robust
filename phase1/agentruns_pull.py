"""Pull FOREAGENT agent_runs journals + eval grades, build parent->child improve/edit edges with BOTH
self-report(metric) and external grade(eval score), for the powered illusion-atlas. Saves edges.json.

Per edge: agent, task, stage(operator), dVal (self-report change), dTrue (external-grade change), df (A1
factor deltas child-parent). Orientation: external by is_lower_better; self-report by its metric arrow.
"""
import os
import re
import ast
import json
import glob
import collections

os.environ.update({
    "https_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "http_proxy": "http://proxy.cse.cuhk.edu.hk:8000",
    "HF_HOME": "/research/d7/spc/yzyang4/cache/hf",
    "HF_HUB_CACHE": "/research/d7/spc/yzyang4/cache/hf/hub",
})
from huggingface_hub import snapshot_download
from phase1.a1_mechanism import feats

ROOT = "/research/d7/spc/yzyang4/foreagent_agentruns"
os.makedirs(ROOT, exist_ok=True)
NUM = re.compile(r"[-+]?\d*\.?\d+")
NAMES = list(feats("").keys())


def pf(s):
    if not s:
        return None
    m = NUM.findall(str(s))
    return float(m[-1]) if m else None


def parse_metric(m):
    """journal 'metric' is a dict / dict-repr like {'value': 0.99, 'maximize': True}. Return (value, maximize)."""
    if m is None:
        return None, None
    d = m if isinstance(m, dict) else None
    if d is None:
        try:
            d = ast.literal_eval(str(m))
        except Exception:
            d = None
    if isinstance(d, dict):
        v = d.get("value")
        mx = d.get("maximize")
        return (float(v) if v is not None else None), (bool(mx) if mx is not None else None)
    return pf(m), None  # fallback: a bare number, orientation unknown


def main():
    if os.environ.get("SKIP_DL"):
        print("SKIP_DL set -> parsing cached files only (no download)", flush=True)
    else:
        print("downloading agent_runs journals + eval_output.json ...", flush=True)
        try:
            snapshot_download(
                "zjunlp/PredictBeforeExecute", repo_type="dataset", local_dir=ROOT,
                allow_patterns=["agent_runs/*/*/logs/journal.json",
                                "agent_runs/*/*/logs/all_nodes/*/eval_output.json"],
                max_workers=4,
            )
        except Exception as e:
            print(f"[warn] snapshot_download incomplete ({type(e).__name__}: {str(e)[:200]}); "
                  "parsing whatever is on disk (resume-safe)", flush=True)

    runs = sorted(glob.glob(os.path.join(ROOT, "agent_runs", "*", "*")))
    edges = []
    n_runs_ok = 0
    for run in runs:
        agent = run.split(os.sep)[-2]
        if agent.startswith("__"):
            continue
        jp = os.path.join(run, "logs", "journal.json")
        if not os.path.exists(jp):
            continue
        try:
            J = json.load(open(jp))
        except Exception:
            continue
        nodes = J.get("nodes") if isinstance(J, dict) else J
        n2p = J.get("node2parent", {}) if isinstance(J, dict) else {}
        if not nodes:
            continue
        # external-grade lookup keyed by short node id (dir name node_<short>)
        evl = {}
        task = None
        for ef in glob.glob(os.path.join(run, "logs", "all_nodes", "*", "eval_output.json")):
            short = os.path.basename(os.path.dirname(ef)).replace("node_", "")
            try:
                ev = json.load(open(ef))
            except Exception:
                continue
            sc = ev.get("score")
            if sc is None or not ev.get("valid_submission", False):
                continue
            evl[short] = (float(sc), bool(ev.get("is_lower_better", False)))
            task = ev.get("competition_id", task)
        if not evl or task is None:
            continue
        byid = {str(n.get("id")): n for n in nodes}
        bystep = {n.get("step"): n for n in nodes}
        used = False
        for n in nodes:
            if n.get("is_buggy"):
                continue
            nid = str(n.get("id"))
            par = n.get("parent")
            if par is None:
                par = n2p.get(nid)
            p = byid.get(str(par)) or bystep.get(par)
            if p is None:
                continue
            cs = evl.get(nid[:8]); ps = evl.get(str(p.get("id"))[:8])
            if cs is None or ps is None:
                continue
            cval, cmx = parse_metric(n.get("metric"))
            pval, pmx = parse_metric(p.get("metric"))
            if cval is None or pval is None:
                continue
            ilb = cs[1]
            dTrue = (-cs[0] if ilb else cs[0]) - (-ps[0] if ilb else ps[0])
            cmax = cmx if cmx is not None else (not ilb)      # orient self-report by its own maximize flag
            pmax = pmx if pmx is not None else (not ps[1])
            dVal = (cval if cmax else -cval) - (pval if pmax else -pval)
            fc = feats(n.get("code") or ""); fp = feats(p.get("code") or "")
            edges.append(dict(agent=agent, task=task, stage=(n.get("stage") or "").lower(),
                              dTrue=dTrue, dVal=dVal, df={k: fc[k] - fp[k] for k in NAMES}))
            used = True
        n_runs_ok += used
    json.dump(edges, open(os.path.join(ROOT, "edges.json"), "w"))
    print(f"\nEDGES={len(edges)} from {n_runs_ok} runs", flush=True)
    print("per-agent:", dict(collections.Counter(e["agent"] for e in edges)), flush=True)
    print("per-stage:", dict(collections.Counter(e["stage"] for e in edges)), flush=True)
    tc = collections.Counter(e["task"] for e in edges)
    print(f"tasks={len(tc)}  per-task(top15): {dict(tc.most_common(15))}", flush=True)
    print("=== pull done ===", flush=True)


if __name__ == "__main__":
    main()
