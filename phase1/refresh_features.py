"""Refresh the id-keyed frozen-feature cache for the probe pipeline as the card set grows.

Modes (composable):
  --rebuild-cards : run build_cards over the runs root -> refresh cards jsonl (picks up new graded nodes)
  --migrate       : CPU-only. Attach current card ids (labeled order) to a legacy positional cache. No GPU.
  --extract       : GPU. Incrementally extract layer-21 self-report-masked features for cards NOT yet
                    cached, append, save. Reuses existing rows -> only new cards hit the model.

Built-in verify: --migrate reloads aligned to the same cards and asserts the XA is byte-identical
(identity reorder), so a silent misalignment can't slip through.

Feature semantics mirror b1_detector exactly: XA = hstack([extract_multilayer([mask_selfreport(c)],[21])[0][21], entropy]).
"""
import argparse
import numpy as np

from phase1.cards import load_cards
from phase1.dataset import labeled
from phase1 import feat_cache

CACHE = "phase1/_cache_b1_feats.npz"
CARDS = "phase1/cards_real_mm.jsonl"
LAYER = 21
MAXTOK = 4000


def _extract_XA(cards):
    from phase1.h1_ablation import extract_multilayer, mask_selfreport
    fA, eA = extract_multilayer([mask_selfreport(c) for c in cards], [LAYER], MAXTOK)
    return np.hstack([fA[LAYER], eA]).astype(np.float32)


def migrate(cards_path=CARDS, cache_path=CACHE):
    cards = labeled(load_cards(cards_path))
    ids0, XA = feat_cache._load_raw(cache_path)
    if ids0 is not None:
        print(f"[migrate] cache already id-keyed ({len(ids0)} rows); nothing to do")
        return
    if len(XA) != len(cards):
        raise SystemExit(f"[migrate] legacy cache {len(XA)} rows != {len(cards)} labeled cards; "
                         f"can't migrate positionally -- delete cache and --extract to rebuild")
    ids = [c.id for c in cards]
    feat_cache.save_cache(ids, XA, cache_path)
    XA2, mask = feat_cache.load_aligned(cards, cache_path)  # identity reorder for the same cards
    ok = bool(mask.all()) and np.array_equal(np.asarray(XA, np.float32), XA2)
    print(f"[migrate] {len(ids)} ids -> {cache_path} | identity-reorder verify: {'OK' if ok else 'FAIL'}")
    if not ok:
        raise SystemExit("[migrate] verify FAILED -- cache NOT trustworthy")


def extract(cards_path=CARDS, cache_path=CACHE):
    cards = labeled(load_cards(cards_path))
    ids0, XA0 = feat_cache._load_raw(cache_path)
    if ids0 is None:
        raise SystemExit("[extract] cache has no ids; run --migrate first (or delete cache for a full rebuild)")
    have = set(ids0)
    new = [c for c in cards if c.id not in have]
    print(f"[extract] {len(cards)} labeled cards | {len(have)} cached | {len(new)} to extract", flush=True)
    if not new:
        print("[extract] nothing new -- cache current")
        return
    XA_new = _extract_XA(new)
    ids = list(ids0) + [c.id for c in new]
    XA = np.vstack([np.asarray(XA0, np.float32), XA_new])
    feat_cache.save_cache(ids, XA, cache_path)
    print(f"[extract] appended {len(new)} -> cache now {len(ids)} rows, dim={XA.shape[1]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-cards", action="store_true")
    ap.add_argument("--migrate", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--runs-root", default="/research/d7/spc/yzyang4/aira-dojo-runs")
    ap.add_argument("--cards", default=CARDS)
    ap.add_argument("--cache", default=CACHE)
    a = ap.parse_args()
    if a.rebuild_cards:
        from phase1.build_cards import build
        build(a.runs_root, a.cards)
    if a.migrate:
        migrate(a.cards, a.cache)
    if a.extract:
        extract(a.cards, a.cache)
    if not (a.migrate or a.extract or a.rebuild_cards):
        print("nothing to do; pass --rebuild-cards / --migrate / --extract")
