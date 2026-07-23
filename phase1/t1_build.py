"""T1 harness — builder. Produces three artifacts from the runs root:
  (a) phase1/cards_t1_labeled.jsonl : graded cards, per-task min-max labels (build_cards + relabel flow)
  (b) phase1/cards_t1_all.jsonl     : ALL parseable cards incl. buggy/unlabeled (for the buggy classifier)
  (c) phase1/t1_buggy_labels.jsonl  : {id, is_buggy, task} scanned straight from journals (ground truth)
Prints counts + overlap verification. CPU only.
"""
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, "/research/d7/spc/yzyang4/aira-dojo")
from phase1.cards import TaskInfo, parse_journal, save_cards
from phase1.build_cards import TASK_TYPE, _peek_competition, build

ROOT = "/research/d7/spc/yzyang4/aira-dojo-runs"

# ---- (a) labeled cards via the existing verified flow + min-max relabel ----
build(ROOT, "phase1/cards_t1_labeled_raw.jsonl")
os.system("/research/d7/spc/yzyang4/venvs/aira/bin/python -m phase1.relabel_minmax "
          "phase1/cards_t1_labeled_raw.jsonl phase1/cards_t1_labeled.jsonl")

# ---- journal set (same case-insensitive per-run dedup as build_cards) ----
_j = (glob.glob(os.path.join(ROOT, "**", "journal.jsonl"), recursive=True)
      + glob.glob(os.path.join(ROOT, "**", "JOURNAL.jsonl"), recursive=True))
byrun = {}
for j in _j:
    byrun.setdefault(os.path.dirname(os.path.dirname(j)), j)
journals = sorted(byrun.values())

# ---- (b) all cards (keep unlabeled/buggy) ----
kept = {}
for jp in journals:
    comp = _peek_competition(jp)
    if comp is None:
        continue
    task = TaskInfo(name=comp, type=TASK_TYPE.get(comp, "tabular"), metric="", desc=comp)
    for c in parse_journal(jp, task):
        if c.code and c.code.strip():
            kept.setdefault(c.id, c)
save_cards(list(kept.values()), "phase1/cards_t1_all.jsonl")

# ---- (c) is_buggy ground truth by node id ----
lab = {}
for jp in journals:
    comp = _peek_competition(jp)
    if comp is None:
        continue
    for line in open(jp):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        nd = d.get("data", d)
        if not isinstance(nd, dict) or "is_buggy" not in nd:
            continue
        nid = nd.get("id")
        if nid:
            lab[f"{comp}__{nid}"] = bool(nd.get("is_buggy"))
with open("phase1/t1_buggy_labels.jsonl", "w") as f:
    for i, b in lab.items():
        f.write(json.dumps({"id": i, "is_buggy": b}) + "\n")

# ---- verification ----
all_ids = set(kept.keys())
lab_ids = set(lab.keys())
overlap = len(all_ids & lab_ids)
n_buggy = sum(1 for i in all_ids if lab.get(i))
print(f"[t1_build] labeled cards: see build output above")
print(f"[t1_build] all cards: {len(all_ids)}  | buggy-label coverage: {overlap}/{len(all_ids)} "
      f"({100*overlap/max(1,len(all_ids)):.0f}%)  | buggy among covered: {n_buggy}")
per = Counter(kept[i].task.name for i in all_ids)
for t, n in per.most_common():
    print(f"    {n:5d}  {t}")
assert overlap / max(1, len(all_ids)) > 0.9, "buggy-label coverage <90% -- id mismatch, investigate"
print("[t1_build] done OK")
