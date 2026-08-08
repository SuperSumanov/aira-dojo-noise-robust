"""Dump per-node RM scores for every unique node on value_pairs_runsplit's test side.

The gate-density check (gate_density.py, ported from the 08-06 critique doc's appendix D)
needs raw node scores, not pair hits. Rendering/pooling mirror rm_train_hf.py exactly:
task-conditioned header, head-25% truncation at max_len 2048, last-non-pad pooling, bf16.

Usage: python phase1/score_nodes.py CKPT_DIR OUT.json  (GPU, ~5 min for ~3k nodes)
"""
import json, sys

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

CKPT, OUT = sys.argv[1], sys.argv[2]
meta = json.load(open(CKPT + "/rm_meta.json"))
MAXLEN, HEADFRAC = int(meta["max_len"]), float(meta["head_frac"])

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

nodes = set()
for l in open("phase1/value_pairs_runsplit.jsonl"):
    p = json.loads(l)
    if p["intask_split"] == "test":
        nodes.update((p["better"], p["worse"]))
nodes = sorted(n for n in nodes if n in cards)
print(f"[score_nodes] {len(nodes)} unique test nodes, ckpt={CKPT}", flush=True)

tok = AutoTokenizer.from_pretrained(meta["base_model"])
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"


class RM(nn.Module):
    def __init__(self, path):
        super().__init__()
        try:
            self.backbone = AutoModel.from_pretrained(
                path, torch_dtype=torch.bfloat16, attn_implementation="flash_attention_2")
        except Exception:
            self.backbone = AutoModel.from_pretrained(path, torch_dtype=torch.bfloat16)
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)


model = RM(CKPT)
model.head.load_state_dict(torch.load(CKPT + "/head.pt", map_location="cpu"))
model = model.cuda().eval() if torch.cuda.is_available() else model.eval()
dev = next(model.parameters()).device


def render(cid):
    head = "# MLE-bench task: " + cards[cid]["task"]["name"] + "\n" if meta["task_cond"] else ""
    return head + (cards[cid].get("code") or "")[:60000]


def fit(ids):
    if len(ids) <= MAXLEN:
        return ids
    h = int(MAXLEN * HEADFRAC)
    return ids[:h] + ids[len(ids) - (MAXLEN - h):]


scores = {}
BS = 16
with torch.no_grad():
    for i in range(0, len(nodes), BS):
        chunk = nodes[i:i + BS]
        seqs = [fit(tok(render(c), add_special_tokens=False)["input_ids"]) for c in chunk]
        m = max(len(s) for s in seqs)
        pad = tok.pad_token_id
        ids = torch.tensor([s + [pad] * (m - len(s)) for s in seqs], device=dev)
        mask = torch.tensor([[1] * len(s) + [0] * (m - len(s)) for s in seqs], device=dev)
        h = model.backbone(input_ids=ids, attention_mask=mask).last_hidden_state
        idx = mask.sum(1) - 1
        pooled = h[torch.arange(h.size(0), device=dev), idx]
        out = model.head(pooled).squeeze(-1).float().tolist()
        for c, v in zip(chunk, out):
            scores[c] = v
        if (i // BS) % 20 == 0:
            print(f"  {i + len(chunk)}/{len(nodes)}", flush=True)

json.dump(scores, open(OUT, "w"))
print(f"[score_nodes] wrote {len(scores)} scores -> {OUT}", flush=True)
