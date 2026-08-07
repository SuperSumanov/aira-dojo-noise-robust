"""Value-RM sidecar: scores (task, code) with a full-FT Bradley–Terry model. CPU, stdlib HTTP.
POST /score {"task": str, "code": str} -> {"score": float in [0,1]}   (sigmoid of the BT logit)
Env: RM_DIR (checkpoint dir), RM_BASE_MODEL when rm_meta.json is absent, RM_PORT (default 8765).
Fail-safe by design: any error returns 500; the MCTS client fails open to vanilla UCT.
"""
import json, math, os
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch

from .bradley_terry_evaluation import load_checkpoint

RM_DIR = os.environ.get("RM_DIR")
if not RM_DIR:
    raise RuntimeError("RM_DIR must point to a saved reward-model checkpoint directory")
PORT = int(os.environ.get("RM_PORT", "8765"))
model, tok, meta = load_checkpoint(RM_DIR, base_model=os.environ.get("RM_BASE_MODEL"))
MAXLEN = int(meta.get("max_len", 2048)); HEADFRAC = float(meta.get("head_frac", 0.25))
TASK_COND = bool(meta.get("task_cond", True))
print(f"[rm_server] loaded {RM_DIR} (max_len={MAXLEN})", flush=True)

def fit(ids):
    if len(ids) <= MAXLEN: return ids
    h = int(MAXLEN * HEADFRAC)
    return ids[:h] + ids[len(ids) - (MAXLEN - h):]

@torch.no_grad()
def score(task, code):
    text = (f"# MLE-bench task: {task}\n{code}") if TASK_COND else code
    ids = fit(tok(text, add_special_tokens=False)["input_ids"])
    t = torch.tensor([ids]); m = torch.ones_like(t)
    logit = model(input_ids=t, attention_mask=m)["logits"][0]
    return 1.0 / (1.0 + math.exp(-float(logit)))

REQ_COUNT = [0]

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        try:
            d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            s = score(d.get("task", ""), d.get("code", ""))
            REQ_COUNT[0] += 1
            if REQ_COUNT[0] % 10 == 1:
                print(f"[rm_server] served {REQ_COUNT[0]} scores", flush=True)
            b = json.dumps({"score": s}).encode()
            self.send_response(200)
        except Exception as e:
            b = json.dumps({"error": str(e)[:200]}).encode()
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

print(f"[rm_server] listening :{PORT}", flush=True)
HTTPServer(("127.0.0.1", PORT), H).serve_forever()
