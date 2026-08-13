"""Validate/preserve source run IDs and inject fallback IDs into legacy corpus cards.

Cards were never emitted with a physical-run identifier: aira-dojo writes one journal per
run, the card extractor flattened them, and the run boundary was lost. It is recoverable
because each batch file was written by iterating run directories, so a run's cards are
contiguous within a file -- see run_segment.py for the reconstruction and its two
validations (every present parent shares its child's segment; no segment mixes tasks).

This step makes run-level splits reproducible for anyone who downloads the corpus.  When
an input card already carries a source-truth run ID, it must exactly match the validated
map and its provenance is preserved.  Only legacy cards receive the contiguity-derived
provenance marker.

Usage: python phase1/add_run_id.py IN.jsonl OUT.jsonl [run_map.json]
"""
import json, math, sys

from phase1.build_cards import TASK_TYPE

src, dst = sys.argv[1], sys.argv[2]
mp = sys.argv[3] if len(sys.argv) > 3 else "phase1/card_run_map.json"
RUN = json.load(open(mp))

n = miss = task_type_fixes = quarantined_labels = explicit_preserved = 0
with open(dst, "w") as out:
    for l in open(src):
        d = json.loads(l)
        r = RUN.get(d["id"])
        if r is None:
            miss += 1
        task_name = d["task"]["name"]
        if task_name not in TASK_TYPE:
            raise ValueError(f"unknown task type for {task_name}; update TASK_TYPE first")
        expected_type = TASK_TYPE[task_name]
        if d["task"].get("type") != expected_type:
            task_type_fixes += 1
            d["task"]["type"] = expected_type
        label = d.get("label") or {}
        label_values = [label.get("graded"), label.get("y_norm")]
        if any(value is not None and
               (not isinstance(value, (int, float)) or not math.isfinite(float(value)))
               for value in label_values):
            quarantined_labels += 1
            label["graded"] = None
            label["y_norm"] = None
            label["medal_bucket"] = "invalid"
            d["label"] = label
            d.setdefault("provenance", {})["label_status"] = \
                "quarantined:nonfinite_label"
        existing_run = d.get("run_id")
        if existing_run is not None:
            if str(existing_run) != str(r):
                raise ValueError(
                    f"explicit run_id disagrees with validated map for {d['id']}: "
                    f"{existing_run} != {r}"
                )
            explicit_preserved += 1
        d["run_id"] = r
        provenance = d.setdefault("provenance", {})
        if existing_run is None:
            provenance["run_id_source"] = "reconstructed:file-contiguity"
        else:
            provenance.setdefault("run_id_source", "explicit:batch-card")
        provenance["task_type_source"] = "phase1.build_cards:TASK_TYPE"
        out.write(json.dumps(d, allow_nan=False) + "\n")
        n += 1
print(f"[add_run_id] {n} cards -> {dst}; unmapped {miss}; "
      f"task-type fixes {task_type_fixes}; quarantined labels {quarantined_labels}; "
      f"explicit run ids preserved {explicit_preserved}")
if miss:
    print("[add_run_id] WARNING: unmapped cards carry run_id=null "
          "(regenerate the map with run_segment.py after adding a batch)")
    sys.exit(1)
