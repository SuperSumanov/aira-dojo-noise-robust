"""Build the real labeled card set from aira-dojo journals.

Scans a runs root for journal.jsonl, parses each into Cards, and KEEPS ONLY cards with a usable
label (``card.y is not None``) -- i.e. nodes carrying an official MLE-bench graded score AND medal
thresholds. HCE/T1 runs are auto-excluded: their metric_info["score"] is the HCE dval with no medal
thresholds, so normalize_graded yields y_norm=None and the card is dropped. Dedup is by node id.

Usage (run on the remote with any python that can import phase1):
    python -m phase1.build_cards <runs_root> <out.jsonl> [--tasks comp1,comp2,...]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter

from .cards import TaskInfo, parse_journal, save_cards

# competition_id -> featurizer task type (only affects the type one-hot in card_features)
TASK_TYPE = {
    "spaceship-titanic": "tabular",
    "playground-series-s3e18": "tabular",
    "nomad2018-predict-transparent-conductors": "tabular",
    "tabular-playground-series-may-2022": "tabular",
    "tabular-playground-series-dec-2021": "tabular",
    "aerial-cactus-identification": "image-cls",
    "leaf-classification": "image-cls",
    "denoising-dirty-documents": "image-cls",
    "spooky-author-identification": "nlp",
    "random-acts-of-pizza": "nlp",
    "google-quest-challenge": "nlp",
    "text-normalization-challenge-english-language": "nlp",
    "text-normalization-challenge-russian-language": "nlp",
    "tweet-sentiment-extraction": "nlp",
    "learning-agency-lab-automated-essay-scoring-2": "nlp",
    "us-patent-phrase-to-phrase-matching": "nlp",
    "kuzushiji-recognition": "image-cls",
    "petfinder-pawpularity-score": "image-cls",
    "whale-categorization-playground": "image-cls",
    "mlsp-2013-birds": "image-cls",
}


def _peek_competition(jp: str):
    """First node's competition_id identifies the task for the whole journal."""
    try:
        for line in open(jp):
            line = line.strip()
            if not line:
                continue
            mi = (json.loads(line).get("metric_info") or {})
            if mi.get("competition_id"):
                return mi["competition_id"]
    except Exception:
        return None
    return None


def build(runs_root: str, out_path: str, tasks=None):
    # case-insensitive: new runs write json/JOURNAL.jsonl (live), old runs also checkpoint/journal.jsonl.
    # both files hold the same content -> keep ONE per run dir (dedup) so we can also read in-progress runs.
    _jset = (glob.glob(os.path.join(runs_root, "**", "journal.jsonl"), recursive=True)
             + glob.glob(os.path.join(runs_root, "**", "JOURNAL.jsonl"), recursive=True))
    _byrun = {}
    for _j in _jset:
        _byrun.setdefault(os.path.dirname(os.path.dirname(_j)), _j)
    journals = sorted(_byrun.values())
    kept = {}                       # id -> Card (dedup)
    per_task = Counter()
    per_task_runs = Counter()
    scanned = skipped_hce = 0
    for jp in journals:
        comp = _peek_competition(jp)
        if comp is None or (tasks and comp not in tasks):
            continue
        scanned += 1
        task = TaskInfo(name=comp, type=TASK_TYPE.get(comp, "tabular"), metric="", desc=comp)
        n_before = len(kept)
        for c in parse_journal(jp, task):
            if c.y is None:         # no official grade+thresholds (e.g. HCE dval) -> drop
                continue
            kept.setdefault(c.id, c)
        gained = len(kept) - n_before
        if gained:
            per_task[comp] += gained
            per_task_runs[comp] += 1
        else:
            skipped_hce += 1        # journal had no usable label (likely HCE/T1 or all-buggy)
    cards = list(kept.values())
    save_cards(cards, out_path)
    print(f"[build_cards] scanned {scanned} journals ({skipped_hce} yielded no usable label)")
    print(f"[build_cards] {len(cards)} labeled cards -> {out_path}")
    for t in sorted(per_task):
        print(f"  {per_task[t]:>4} cards | {per_task_runs[t]:>2} runs | {t}")
    return cards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_root")
    ap.add_argument("out_path")
    ap.add_argument("--tasks", default=None, help="comma-separated competition_ids to keep")
    a = ap.parse_args()
    build(a.runs_root, a.out_path, set(a.tasks.split(",")) if a.tasks else None)


if __name__ == "__main__":
    main()
