"""Id-keyed frozen-feature cache so the probe pipeline scales as the card set grows.

Legacy cache stored only XA positionally (row k <-> the k-th labeled card at cache-build time) --
fragile: any card add/reorder silently misaligns features and labels. Here rows are keyed by
card.id and aligned on load, so cards can be added/reordered without silent misalignment.
"""
import numpy as np


def save_cache(ids, XA, path):
    ids = [str(i) for i in ids]
    XA = np.asarray(XA, dtype=np.float32)
    assert len(ids) == len(XA), f"{len(ids)} ids vs {len(XA)} rows"
    assert len(set(ids)) == len(ids), "duplicate ids in cache"
    np.savez(path, ids=np.array(ids), XA=XA)


def _load_raw(path):
    """Return (ids_or_None, XA). ids is None for a legacy positional cache."""
    d = np.load(path, allow_pickle=True)
    XA = d["XA"]
    ids = [str(i) for i in d["ids"]] if "ids" in d.files else None
    return ids, XA


def load_aligned(cards, path):
    """Return (XA_aligned, mask): XA_aligned has one row per cached card, in the order of the
    cards for which a row exists; mask[i] tells whether cards[i] was found. For a legacy cache
    (no ids) fall back to positional and require an exact length match."""
    ids, XA = _load_raw(path)
    want = [c.id for c in cards]
    if ids is None:
        if len(XA) != len(want):
            raise SystemExit(
                f"legacy positional cache has {len(XA)} rows but {len(want)} cards; "
                f"run `python -m phase1.refresh_features --migrate` then `--extract`")
        return np.asarray(XA, np.float32), np.ones(len(want), bool)
    pos = {i: k for k, i in enumerate(ids)}
    mask = np.array([i in pos for i in want])
    rows = [pos[i] for i in want if i in pos]
    return np.asarray(XA[rows], np.float32), mask
