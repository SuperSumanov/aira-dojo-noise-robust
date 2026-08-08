"""Reconstruct physical-run membership for every card, and size the fragment leak.

Cards carry no run id, but each batch file was written by iterating run directories, so a
run's cards are contiguous. Segment rule within a file: new segment when the task changes
OR lineage.step fails to increase (journal order is generation order).

Validation (must both hold or the reconstruction is rejected):
  V1 every present parent_id sits in the SAME segment as the child
  V2 no segment mixes tasks
Then quantify: fragments per run, and for each pairs file, the share of test pairs whose
endpoint RUN also contributed training pairs (the physical-level leak the fragment split
could not see).

Output: phase1/card_run_map.json  {card_id: "file:seg_idx"}

Usage: python phase1/run_segment.py
"""
import collections, json

FILES = [l.strip() for l in open("phase1/corpus_manifest.txt")
         if l.strip()]   # single source of truth, shared with rebuild_corpus.sh

run_of, cards = {}, {}
seg_tasks = {}
for fn in FILES:
    prev_task, prev_step, seg = None, None, -1
    try:
        fh = open("phase1/" + fn)
    except FileNotFoundError:
        print("[missing]", fn)
        continue
    for l in fh:
        d = json.loads(l)
        cards[d["id"]] = d
        t = d["task"]["name"]
        st = d["lineage"].get("step") or 0
        if t != prev_task or (prev_step is not None and st <= prev_step):
            seg += 1
        rid = f"{fn}:{seg}"
        run_of[d["id"]] = rid
        seg_tasks.setdefault(rid, set()).add(t)
        prev_task, prev_step = t, st

n_runs = len(seg_tasks)
v2_bad = sum(1 for s in seg_tasks.values() if len(s) > 1)
v1_bad = 0
cross_parent = collections.Counter()
for cid, d in cards.items():
    p = d["lineage"].get("parent_id")
    if p and p in cards and run_of[p] != run_of[cid]:
        v1_bad += 1
        cross_parent[run_of[cid].split(":")[0]] += 1
print(f"cards={len(cards)} runs reconstructed={n_runs}")
print(f"V1 parent-in-other-segment violations: {v1_bad} {dict(cross_parent.most_common(5))}")
print(f"V2 mixed-task segments: {v2_bad}")
ok = v1_bad == 0 and v2_bad == 0
print("SEGMENTATION:", "VALID" if ok else "REJECTED")
if ok:
    json.dump(run_of, open("phase1/card_run_map.json", "w"))
    print("wrote phase1/card_run_map.json")
    sizes = collections.Counter(run_of.values())
    per_run = collections.Counter(sizes.values())
    print("run size histogram (size->count):",
          dict(sorted(per_run.items())[:10]), "... max run size:", max(sizes.values()))
    # fragments per run
    root = {}
    def tr(c, g=0):
        if c in root:
            return root[c]
        p = cards.get(c, {}).get("lineage", {}).get("parent_id")
        r = c if (not p or p not in cards or g > 200) else tr(p, g + 1)
        root[c] = r
        return r
    frag_of_run = collections.defaultdict(set)
    for cid in cards:
        frag_of_run[run_of[cid]].add(tr(cid))
    fr = [len(v) for v in frag_of_run.values()]
    print(f"fragments/run: mean {sum(fr)/len(fr):.1f}  max {max(fr)}  "
          f"runs with >1 fragment: {sum(1 for x in fr if x > 1)}/{len(fr)}")
    # physical leak per pairs file: test pairs with an endpoint whose RUN has train pairs
    for pf in ["value_pairs_v3.jsonl", "budget_pairs_v2.jsonl", "budget_pairs_v3.jsonl",
               "decision_pairs_v1b.jsonl"]:
        tr_runs, te_pairs = set(), []
        try:
            fh = open("phase1/" + pf)
        except FileNotFoundError:
            continue
        for l in fh:
            p = json.loads(l)
            if p["better"] not in run_of or p["worse"] not in run_of:
                continue
            if p["intask_split"] == "train":
                tr_runs.add(run_of[p["better"]])
                tr_runs.add(run_of[p["worse"]])
            else:
                te_pairs.append((run_of[p["better"]], run_of[p["worse"]]))
        leak = sum(1 for a, b in te_pairs if a in tr_runs or b in tr_runs)
        print(f"{pf:28s} test pairs with run-level train contact: "
              f"{leak}/{len(te_pairs)} = {leak/max(len(te_pairs),1):.1%}")
