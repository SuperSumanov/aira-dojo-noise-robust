"""Value-RM sidecar: scores (task, code) with the trained LoRA head. CPU, stdlib HTTP.
POST /score {"task": str, "code": str} -> {"score": float in [0,1]}   (sigmoid of the BT logit)
Env: RM_DIR (adapter dir), RM_PORT (default 8765).
Fail-safe by design: any error returns 500; the MCTS client fails open to vanilla UCT.
"""
import json, math, os
from http.server import BaseHTTPRequestHandler, HTTPServer

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer
from peft import PeftModel

RM_DIR = os.environ.get("RM_DIR")
if not RM_DIR:
    raise RuntimeError("RM_DIR must point to a saved reward-model checkpoint directory")
PORT = int(os.environ.get("RM_PORT", "8765"))
meta = json.load(open(os.path.join(RM_DIR, "rm_meta.json")))
MAXLEN = int(meta.get("max_len", 2048)); HEADFRAC = float(meta.get("head_frac", 0.25))
TASK_COND = bool(meta.get("task_cond", True))

tok = AutoTokenizer.from_pretrained(meta["base_model"])
if tok.pad_token is None: tok.pad_token = tok.eos_token
if os.path.exists(os.path.join(RM_DIR, "adapter_config.json")):
    base = AutoModel.from_pretrained(meta["base_model"], torch_dtype=torch.float32)
    backbone = PeftModel.from_pretrained(base, RM_DIR).eval()
else:
    # full fine-tune checkpoint: the directory IS the model
    backbone = AutoModel.from_pretrained(RM_DIR, torch_dtype=torch.float32).eval()
head = nn.Linear(backbone.config.hidden_size, 1)
sd = torch.load(os.path.join(RM_DIR, "head.pt"), map_location="cpu")
head.load_state_dict({k: v.float() for k, v in sd.items()}); head.eval()
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
    h = backbone(input_ids=t, attention_mask=m).last_hidden_state[0, -1]
    return 1.0 / (1.0 + math.exp(-float(head(h).squeeze())))

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
