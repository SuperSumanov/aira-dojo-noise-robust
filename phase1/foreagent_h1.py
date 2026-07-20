"""H1 de-risk on FOREAGENT: does the frozen Qwen2.5-Coder-7B layer-21 rep linearly encode the EXTERNAL
grade at SCALE (independent agents/models/tasks), the way it did on our 3 tabular tasks?

Reuses the EXACT prompt template (build_value_prompt, ablated = self-report masked) + feature construction
+ intra/loto probe from h1_ablation, so the number is apples-to-apples with our own (intra ~0.29, loto ~.2-.3).
GPU job. Caches features to feats_l21.npz for reuse.
"""
import os
import json
from collections import Counter

import numpy as np
import torch

from phase1.h1_ablation import intra, loto
from phase1.critics.qwen_backend import load_model, _chat

MODEL = os.environ.get("H1_MODEL", "/research/d7/spc/yzyang4/models/Qwen2.5-Coder-7B-Instruct")
ROOT = "/research/d7/spc/yzyang4/foreagent_slice"
LAYER = int(os.environ.get("H1_LAYER", "21"))
MAXCODE = 4000


def build_prompt(task, hib, code):
    """Replicates build_value_prompt with self-report/lineage MASKED (our 'ablated' condition)."""
    code = (code or "")[:MAXCODE]
    return "\n\n".join([
        f"# Task\n{task} (?, metric=?, higher_is_better={hib})",
        "# Cheap signals\nself_reported_val=None  runtime_s=None  error=None\nval_curve=[]",
        "# Lineage\nop=None depth=None parent_val=None",
        f"# Candidate code (truncated)\n```python\n{code}\n```",
        "# Output\nReply with ONLY one line: `SCORE: <float in [0,1]>`",
    ])


def main():
    if not torch.cuda.is_available():
        raise SystemExit("no CUDA on this node")
    rows = json.load(open(os.path.join(ROOT, "slice.json")))
    tasks = np.array([r["task"] for r in rows])
    y = np.array([(r["score"] if not r["is_lower_better"] else -r["score"]) for r in rows], float)
    C = np.array([[np.log1p(len(r["code"] or "")), np.log1p((r["code"] or "").count("\n"))] for r in rows], float)
    print(f"N={len(rows)}  tasks={len(set(tasks))}", flush=True)
    print("per-task n:", {t: int(n) for t, n in sorted(Counter(tasks).items())}, flush=True)

    model, tok = load_model(MODEL, "4bit")
    prompts = [_chat(tok, build_prompt(r["task"], not r["is_lower_better"], r["code"])) for r in rows]
    feats = []
    bs = 2
    for i in range(0, len(prompts), bs):
        enc = tok(prompts[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=2048).to(model.device)
        with torch.no_grad():
            out = model(**enc, output_hidden_states=True)
        hs = out.hidden_states[LAYER]
        m = enc["attention_mask"].unsqueeze(-1).to(hs.dtype)
        mp = (hs * m).sum(1) / m.sum(1).clamp(min=1)
        idx = enc["attention_mask"].sum(1) - 1
        ar = torch.arange(hs.size(0))
        last = hs[ar, idx]
        ll = out.logits[ar, idx].float()
        lp = torch.log_softmax(ll, -1)
        ent = -(lp.exp() * lp).sum(-1)
        feats.append(torch.cat([mp.float(), last.float(), ent.unsqueeze(-1)], -1).cpu().numpy())
        del out, hs
        torch.cuda.empty_cache()
        if (i // bs) % 25 == 0:
            print(f"  extracted {min(i + bs, len(prompts))}/{len(prompts)}", flush=True)
    X = np.vstack(feats)
    np.savez(os.path.join(ROOT, "feats_l21.npz"), X=X, y=y, tasks=tasks, C=C)
    print(f"features {X.shape}", flush=True)

    it, lt = intra(X, y, tasks), loto(X, y, tasks)
    itr, ltr = intra(X, y, tasks, C), loto(X, y, tasks, C)
    fi, fl = intra(C, y, tasks), loto(C, y, tasks)
    print(f"\n=== H1 replication on FOREAGENT subset_50 (frozen Qwen2.5-Coder-7B layer {LAYER}) ===", flush=True)
    print(f"  probe                         intra={it:+.3f}  loto={lt:+.3f}", flush=True)
    print(f"  probe + length-residualized   intra={itr:+.3f}  loto={ltr:+.3f}", flush=True)
    print(f"  length-only floor             intra={fi:+.3f}  loto={fl:+.3f}", flush=True)
    print(f"  (our own 3-task H1: intra ~0.29, loto ~0.2-0.3)", flush=True)

    green = (it > 0.15) and (itr > 0.10) and (lt > 0.05)
    print("\n=== VERDICT ===", flush=True)
    if green:
        print("  GREEN: H1 REPLICATES at scale on FOREAGENT (independent agents/models/~30 tasks) and survives"
              " length control -> the 'scale' half of Path A is de-risked.", flush=True)
    else:
        print(f"  NOT GREEN (intra={it:.3f} itr={itr:.3f} loto={lt:.3f}): H1 does not clearly replicate here."
              " Investigate task mix / image-code / prompt before committing GPU to the full study.", flush=True)
    print("\n=== done rc=0 ===", flush=True)


if __name__ == "__main__":
    main()
