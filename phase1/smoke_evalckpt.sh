#!/bin/bash
# CPU smoke for the --eval-ckpt branch (preflight rule: never let a GPU job die on a loader bug).
# 1) head.pt shape sanity  2) 4-pair end-to-end eval-only run on the login node.
set -u
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3

$P - <<'EOF'
import torch, json
for ck in ["phase1/ckpt_l2_v2data/N8000", "phase1/ckpt_l2_v3data/N8000",
           "phase1/ckpt_lookahead_v3/N24000"]:
    hd = torch.load(ck + "/head.pt", map_location="cpu")
    shapes = {k: tuple(v.shape) for k, v in hd.items()}
    print(ck, "head:", shapes)
    assert shapes.get("weight") == (1, 1536) and shapes.get("bias") == (1,), "bad head shapes"
sel = []
for l in open("phase1/decision_pairs_v1.jsonl"):
    d = json.loads(l)
    if d["intask_split"] == "test":
        sel.append(d)
    if len(sel) == 4:
        break
open("phase1/_smoke_pairs.jsonl", "w").write("".join(json.dumps(x) + "\n" for x in sel))
print("smoke pairs:", len(sel))
EOF
[ $? -ne 0 ] && { echo SMOKE_FAIL_HEAD; exit 1; }

rm -f phase1/_smoke_hits.jsonl phase1/_smoke_evalckpt.csv
RM_DUMP_HITS=phase1/_smoke_hits.jsonl $P phase1/rm_train_hf.py \
  --pairs phase1/_smoke_pairs.jsonl --cards phase1/cards_current.jsonl \
  --sizes 24000 --max-len 2048 --eval-cap 4 --bs 2 --seed 7 \
  --eval-ckpt phase1/ckpt_lookahead_v3/N24000 --out phase1/_smoke_evalckpt.csv
RC=$?
echo "SMOKE_RC=$RC"
echo "--- csv:"; cat phase1/_smoke_evalckpt.csv 2>/dev/null
echo "--- hits:"; cat phase1/_smoke_hits.jsonl 2>/dev/null
exit $RC
