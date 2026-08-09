"""Frozen code embeddings: the suite member that isolates what fine-tuning actually buys.

The trained critic and the char n-gram land within a point of each other (0.649 vs 0.666),
which says the bottleneck is not model capacity. A frozen-representation predictor splits
that further: mean-pool a pretrained LM over the program, fit a linear ranker on the
embeddings, and never update a single weight. If frozen + linear matches the fine-tuned
model, fine-tuning bought nothing and the ceiling is in the representation, not the head.

This is also the natural analogue of the NAS zero-cost proxies that NAS-Bench-Suite-Zero
found competitive with everything fancier -- same experiment, different search space.

Mean pooling over the attention mask rather than last-token pooling: the fine-tuned model
uses last-token because it was trained that way, but an untrained head has no reason to
prefer the final position, and mean pooling is the standard frozen-embedding recipe.

Usage: python phase1/embed_extract.py MODEL_DIR OUT.json [--max-len 2048]
"""
import argparse, json

import torch
from transformers import AutoModel, AutoTokenizer

ap = argparse.ArgumentParser()
ap.add_argument("model")
ap.add_argument("out")
ap.add_argument("--max-len", type=int, default=2048)
ap.add_argument("--head-frac", type=float, default=0.25)
ap.add_argument("--cards", default="phase1/cards_current_v7.jsonl")
ap.add_argument("--pairs", default="phase1/value_pairs_runsplit.jsonl")
a = ap.parse_args()

cards = {}
for l in open(a.cards):
    d = json.loads(l)
    cards[d["id"]] = d
need = set()
for l in open(a.pairs):
    p = json.loads(l)
    if p["better"] in cards and p["worse"] in cards:
        need.update((p["better"], p["worse"]))
need = sorted(need)
print(f"[embed] {len(need)} nodes to embed with {a.model} @ {a.max_len}", flush=True)

tok = AutoTokenizer.from_pretrained(a.model)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "right"
model = AutoModel.from_pretrained(a.model, torch_dtype=torch.bfloat16)
model = (model.cuda() if torch.cuda.is_available() else model).eval()
dev = next(model.parameters()).device


def fit(ids):
    if len(ids) <= a.max_len:
        return ids
    h = int(a.max_len * a.head_frac)
    return ids[:h] + ids[len(ids) - (a.max_len - h):]


out, BS = {}, 8
with torch.no_grad():
    for i in range(0, len(need), BS):
        chunk = need[i:i + BS]
        seqs = [fit(tok("# MLE-bench task: " + cards[c]["task"]["name"] + "\n"
                        + (cards[c].get("code") or "")[:60000],
                        add_special_tokens=False)["input_ids"]) for c in chunk]
        m = max(len(s) for s in seqs)
        pad = tok.pad_token_id
        ids = torch.tensor([s + [pad] * (m - len(s)) for s in seqs], device=dev)
        msk = torch.tensor([[1] * len(s) + [0] * (m - len(s)) for s in seqs], device=dev)
        h = model(input_ids=ids, attention_mask=msk).last_hidden_state
        mask = msk.unsqueeze(-1).to(h.dtype)
        pooled = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
        for c, v in zip(chunk, pooled.float().cpu().tolist()):
            out[c] = [round(x, 5) for x in v]
        if (i // BS) % 100 == 0:
            print(f"  {i + len(chunk)}/{len(need)}", flush=True)

json.dump(out, open(a.out, "w"))
print(f"[embed] wrote {len(out)} embeddings (dim {len(next(iter(out.values())))}) "
      f"-> {a.out}", flush=True)
