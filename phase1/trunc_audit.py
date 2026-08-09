"""How much of each program did the model actually see?

Every negative conclusion so far came from Qwen2.5-1.5B at max_len 2048 with head_frac 0.25
-- head 512 tokens plus tail 1536. If programs routinely run to 5-10k tokens, the model was
judging a fraction of the artifact, and "the code carries no orthogonal information" is a
statement about that fraction, not about the code. This measures the gap before any claim
about capacity is made either way.

Also asks the sharper question: is the DISCRIMINATIVE part of an ML script even in the kept
window? Head-25%/tail-75% keeps imports and the final fit/predict, and drops the middle --
which is where cross-validation setup, feature engineering, and leakage live.

Usage: python phase1/trunc_audit.py [cards.jsonl]
"""
import collections, json, statistics, sys

from transformers import AutoTokenizer

PATH = sys.argv[1] if len(sys.argv) > 1 else "phase1/cards_current_v7.jsonl"
MAXLEN, HEADFRAC = 2048, 0.25
tok = AutoTokenizer.from_pretrained(
    "/research/d7/spc/yzyang4/external/models/qwen2.5-1.5b-instruct")

cards = []
for l in open(PATH):
    d = json.loads(l)
    if d.get("code"):
        cards.append(d)
print(f"cards with code: {len(cards)}")

rng_sample = cards[::5]          # every 5th card keeps this a couple of minutes
lens, kept_frac = [], []
for d in rng_sample:
    ids = tok(d["code"][:60000], add_special_tokens=False)["input_ids"]
    lens.append(len(ids))
    kept_frac.append(min(1.0, MAXLEN / max(len(ids), 1)))
lens.sort()
n = len(lens)
print(f"\nsampled {n} programs; token length distribution:")
for q in (0.10, 0.25, 0.50, 0.75, 0.90, 0.99):
    print(f"  p{int(q*100):02d}: {lens[int(q*(n-1))]:>7,}")
print(f"  max: {lens[-1]:,}   mean: {statistics.mean(lens):,.0f}")
over = sum(1 for x in lens if x > MAXLEN)
print(f"\nprograms exceeding max_len={MAXLEN}: {over}/{n} = {over/n:.1%}")
print(f"mean fraction of tokens the model saw: {statistics.mean(kept_frac):.1%}")
print(f"median fraction: {statistics.median(kept_frac):.1%}")
for cap in (4096, 8192, 16384):
    o = sum(1 for x in lens if x > cap)
    kf = statistics.mean([min(1.0, cap / max(x, 1)) for x in lens])
    print(f"  at max_len={cap:>5}: {o/n:5.1%} still truncated, mean coverage {kf:.1%}")

# where does the discriminative content sit? count ML-methodology markers by position
print("\nwhere the methodology markers live (share of markers inside the kept window):")
MARK = ("kfold", "cross_val", "train_test_split", "stratified", "early_stop",
        "fit(", "predict(", "merge(", "groupby", "target", "leak")
inside = collections.Counter()
total = collections.Counter()
for d in rng_sample[:400]:
    code = d["code"][:60000]
    ids = tok(code, add_special_tokens=False)["input_ids"]
    if len(ids) <= MAXLEN:
        continue
    h = int(MAXLEN * HEADFRAC)
    keep_head = tok.decode(ids[:h])
    keep_tail = tok.decode(ids[len(ids) - (MAXLEN - h):])
    low, kh, kt = code.lower(), keep_head.lower(), keep_tail.lower()
    for m in MARK:
        c = low.count(m)
        if c:
            total[m] += c
            inside[m] += kh.count(m) + kt.count(m)
for m in MARK:
    if total[m]:
        print(f"  {m:18s} {inside[m]:>5}/{total[m]:<6} = {inside[m]/total[m]:.0%} visible")
tot_i, tot_t = sum(inside.values()), sum(total.values())
print(f"  {'ALL MARKERS':18s} {tot_i}/{tot_t} = {tot_i/max(tot_t,1):.0%} visible "
      f"(on truncated programs only)")
