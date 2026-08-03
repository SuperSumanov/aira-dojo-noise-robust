"""Pre-flight for the queued batchqua run, before it takes a GPU slot.

The pairs were built from per-batch card files rebuilt out of raw journals, but the trainer
resolves code through cards_current.jsonl. If the id schemes diverged, pairs would silently
drop at load ("p[better] in code") and the job would train on nothing or crash late.

Checks:
  1  every pair id resolves in cards_current
  2  no byte-identical program spans the train/test boundary (whitespace-normalised hash)
  3  no duplicate records within any split
  4  per-group pair counts and gap distributions are sane
"""
import collections, hashlib, json, statistics

cards = {}
for l in open("phase1/cards_current.jsonl"):
    d = json.loads(l)
    cards[d["id"]] = d

recs = [json.loads(l) for l in open("phase1/batchqua_pairs.jsonl")]
ids = {r["better"] for r in recs} | {r["worse"] for r in recs}
missing = [i for i in ids if i not in cards]
print(f"[1] id resolution: {len(ids)} distinct ids, {len(missing)} missing from cards_current"
      + ("   OK" if not missing else "   FAIL"))
if missing:
    for m in missing[:5]:
        print("     missing:", m)

tr_nodes = {r[k] for r in recs if r["intask_split"] == "train" for k in ("better", "worse")}
te_nodes = {r[k] for r in recs if r["intask_split"] == "test" for k in ("better", "worse")}


def h(cid):
    return hashlib.md5(" ".join((cards[cid].get("code") or "").split()).encode()).hexdigest()


shared = {h(c) for c in tr_nodes if c in cards} & {h(c) for c in te_nodes if c in cards}
print(f"[2] byte-identical programs across train/test: {len(shared)}"
      + ("   OK" if not shared else "   FAIL"))

seen = collections.Counter((r["better"], r["worse"], r["intask_split"]) for r in recs)
dups = sum(1 for v in seen.values() if v > 1)
print(f"[3] duplicate records within a split: {dups}" + ("   OK" if not dups else "   FAIL"))

print("[4] per-group composition:")
grp = collections.defaultdict(list)
for r in recs:
    key = (r["intask_split"], r["task"].split("::")[0] if "::" in r["task"] else "train")
    grp[(r["intask_split"], r["task"])].append(r["gap_raw"])
for (sp, t), gs in sorted(grp.items()):
    print(f"     {sp:5s} {t[:40]:40s} n={len(gs):5d} med_gap={statistics.median(gs):.4f}")
node_overlap = tr_nodes & te_nodes
print(f"[extra] node-level train/test overlap: {len(node_overlap)}"
      + ("   OK" if not node_overlap else "   FAIL"))
