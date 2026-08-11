"""Fix: the tfidf design matrix only covered the primary pair set.

`ids` was built from train + test, so the row index has no entry for a node that appears
only in the secondary sibling set, and tf_pred raised KeyError on the first such pair. The
matrix must span every node either set will ask about.

The fit stays on train_ids alone -- that is the leak fix from the earlier audit and must not
be undone here. Transforming additional rows with a vocabulary and idf learned from training
data only is exactly what a deployed model would do to an unseen program.
"""
P = "phase1/predictor_suite.py"
s = open(P, encoding="utf-8").read()

a = 'ids = sorted({c for p in train + test for c in (p["better"], p["worse"])})'
assert s.count(a) == 1, s.count(a)
s = s.replace(a, 'ids = sorted({c for p in train + test + EVAL2 '
                 'for c in (p["better"], p["worse"])})')

b = """def tf_pred(b, w):
    k = (b, w)
    if k not in _tcache:"""
assert s.count(b) == 1
s = s.replace(b, """def tf_pred(b, w):
    k = (b, w)
    if b not in pos or w not in pos:
        return None
    if k not in _tcache:""")

open(P, "w", encoding="utf-8").write(s)
print("patched", P)
print("check:", 'train + test + EVAL2' in s, '  fit still train-only:',
      'tf.fit([(cards[c].get("code") or "")[:20000] for c in train_ids])' in s)
