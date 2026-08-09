"""Score every held-out sibling node with the run-clean checkpoint.

selective_exec.py needs the critic's ranking WITHIN a sibling set, not pairwise hits, so
each node needs a scalar. Rendering and pooling mirror rm_train_hf.py exactly (task-
conditioned header, head-25% truncation at the checkpoint's max_len, last-non-pad pooling)
-- any drift here would silently change what is being measured.

Only nodes in held-out runs that have at least one sibling are scored; the model never saw
those runs, so this is a clean counterfactual.

Usage: python phase1/score_siblings.py CKPT_DIR OUT.json
"""
import collections, json, sys

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

CKPT, OUT = sys.argv[1], sys.argv[2]
meta = json.load(open(CKPT + "/rm_meta.json"))
MAXLEN, HEADFRAC = int(meta["max_len"]), float(meta["head_frac"])
RUN = json.load(open("phase1/card_run_map.json"))
HOLD = set(json.load(open("phase1/runsplit_holdruns.json")))

cards = {}
for l in open("phase1/cards_current_v7.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d
kids = collections.defaultdict(list)
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p:
        kids[p].append(cid)

nodes = set()
for parent, ch in kids.items():
    ch = [c for c in ch if c in cards]
    if len(ch) >= 2 and all(RUN.get(c) in HOLD for c in ch):
        nodes.update(ch)
nodes = sorted(nodes)
print(f"[score_siblings] {len(nodes)} nodes in held-out sibling sets, ckpt={CKPT}",
      flush=True)

tok = AutoTokenizer.from_pretrained(meta["base_model"])
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"


class RM(nn.Module):
    def __init__(self, path):
        super().__init__()
        try:
            self.backbone = AutoModel.from_pretrained(
                path, torch_dtype=torch.bfloat16,
                attn_implementation="flash_attention_2")
        except Exception:
            self.backbone = AutoModel.from_pretrained(path, torch_dtype=torch.bfloat16)
        self.head = nn.Linear(self.backbone.config.hidden_size, 1, dtype=torch.bfloat16)


model = RM(CKPT)
model.head.load_state_dict(torch.load(CKPT + "/head.pt", map_location="cpu"))
model = (model.cuda() if torch.cuda.is_available() else model).eval()
dev = next(model.parameters()).device


def render(cid):
    head = ("# MLE-bench task: " + cards[cid]["task"]["name"] + "\n"
            if meta.get("task_cond", True) else "")
    return head + (cards[cid].get("code") or "")[:60000]


def fit(ids):
    if len(ids) <= MAXLEN:
        return ids
    h = int(MAXLEN * HEADFRAC)
    return ids[:h] + ids[len(ids) - (MAXLEN - h):]


scores, BS = {}, 16
with torch.no_grad():
    for i in range(0, len(nodes), BS):
        chunk = nodes[i:i + BS]
        seqs = [fit(tok(render(c), add_special_tokens=False)["input_ids"]) for c in chunk]
        m = max(len(s) for s in seqs)
        pad = tok.pad_token_id
        ids = torch.tensor([s + [pad] * (m - len(s)) for s in seqs], device=dev)
        msk = torch.tensor([[1] * len(s) + [0] * (m - len(s)) for s in seqs], device=dev)
        h = model.backbone(input_ids=ids, attention_mask=msk).last_hidden_state
        idx = msk.sum(1) - 1
        out = model.head(h[torch.arange(h.size(0), device=dev), idx]).squeeze(-1).float()
        for c, v in zip(chunk, out.tolist()):
            scores[c] = v
        if (i // BS) % 25 == 0:
            print(f"  {i + len(chunk)}/{len(nodes)}", flush=True)

json.dump(scores, open(OUT, "w"))
print(f"[score_siblings] wrote {len(scores)} scores -> {OUT}", flush=True)
