"""T1 harness — incremental GPU feature extraction into id-keyed caches (cold-start safe, chunked saves).
Extracts layer-21 self-report-masked frozen features for (a) labeled cards, (b) all cards.
Resume-safe: saves the cache every CHUNK cards; re-running skips already-cached ids.
"""
import os
import sys

import numpy as np

sys.path.insert(0, "/research/d7/spc/yzyang4/aira-dojo")
from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1.h1_ablation import extract_multilayer, mask_selfreport
from phase1 import feat_cache


def mask_preexec(c):
    """TRUE pre-execution view for the buggy classifier: also strip post-exec fields
    (error flag + runtime) that mask_selfreport leaves in (leak found 2026-07-23)."""
    m = mask_selfreport(c)
    for f in ("error", "runtime_s", "exec_time", "exit_code"):
        if hasattr(m.obs, f):
            setattr(m.obs, f, None)
    return m

LAYER = 21
MAXTOK = 4000
CHUNK = 250


def ensure(cards, cache_path, tag, masker=mask_selfreport):
    if os.path.exists(cache_path):
        ids0, XA0 = feat_cache._load_raw(cache_path)
        ids0 = list(ids0 or [])
        XA0 = np.asarray(XA0, np.float32) if len(ids0) else None
    else:
        ids0, XA0 = [], None
    have = set(ids0)
    new = [c for c in cards if c.id not in have]
    print(f"[{tag}] cards={len(cards)} cached={len(have)} to_extract={len(new)}", flush=True)
    for i in range(0, len(new), CHUNK):
        batch = new[i:i + CHUNK]
        fA, eA = extract_multilayer([masker(c) for c in batch], [LAYER], MAXTOK)
        XAn = np.hstack([fA[LAYER], eA]).astype(np.float32)
        XA0 = XAn if XA0 is None else np.vstack([XA0, XAn])
        ids0 = ids0 + [c.id for c in batch]
        feat_cache.save_cache(ids0, XA0, cache_path)
        print(f"[{tag}] cached {len(ids0)}/{len(cards)}", flush=True)
    print(f"[{tag}] done: cache={len(ids0)} rows", flush=True)


ensure(labeled(load_cards("phase1/cards_t1_labeled.jsonl")), "phase1/_cache_t1_lab.npz", "labeled")
ensure(load_cards("phase1/cards_t1_all.jsonl"), "phase1/_cache_t1_pre.npz", "all-preexec", masker=mask_preexec)
print("=== t1_extract done ===", flush=True)
