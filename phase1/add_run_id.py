"""Inject run_id into every card of the merged corpus (dataset-release schema, v6).

Cards were never emitted with a physical-run identifier: aira-dojo writes one journal per
run, the card extractor flattened them, and the run boundary was lost. It is recoverable
because each batch file was written by iterating run directories, so a run's cards are
contiguous within a file -- see run_segment.py for the reconstruction and its two
validations (every present parent shares its child's segment; no segment mixes tasks).

This step is what makes run-level splits reproducible for anyone who downloads the corpus,
instead of requiring them to re-derive segmentation from file order. Once the collector
emits a real run id, delete this step and read the field directly.

Usage: python phase1/add_run_id.py IN.jsonl OUT.jsonl [run_map.json]
"""
import json, sys

src, dst = sys.argv[1], sys.argv[2]
mp = sys.argv[3] if len(sys.argv) > 3 else "phase1/card_run_map.json"
RUN = json.load(open(mp))

n = miss = 0
with open(dst, "w") as out:
    for l in open(src):
        d = json.loads(l)
        r = RUN.get(d["id"])
        if r is None:
            miss += 1
        d["run_id"] = r
        d.setdefault("provenance", {})["run_id_source"] = "reconstructed:file-contiguity"
        out.write(json.dumps(d) + "\n")
        n += 1
print(f"[add_run_id] {n} cards -> {dst}; unmapped {miss}")
if miss:
    print("[add_run_id] WARNING: unmapped cards carry run_id=null "
          "(regenerate the map with run_segment.py after adding a batch)")
    sys.exit(1)
