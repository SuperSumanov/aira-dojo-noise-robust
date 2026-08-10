"""Exact permutation is only tractable to n=10 (10! = 3.6M); 12! = 479M does not finish.
Switch to Monte Carlo above that, with enough draws that the resolution is far finer than
the 0.01 threshold, and say which method produced the p so the two are never confused."""
import io
P = "phase1/c2_verdict.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

old = ("ge = tot = 0" + NL +
       "for perm in itertools.permutations(range(n)):" + NL +
       "    tot += 1" + NL +
       "    if spearman(xs, [ys[i] for i in perm]) >= r:" + NL +
       "        ge += 1" + NL +
       "p1 = ge / tot")
new = ("import math as _m, random as _rnd" + NL +
       "if _m.factorial(n) <= 4_000_000:" + NL +
       "    ge = tot = 0" + NL +
       "    for perm in itertools.permutations(range(n)):" + NL +
       "        tot += 1" + NL +
       "        if spearman(xs, [ys[i] for i in perm]) >= r:" + NL +
       "            ge += 1" + NL +
       "    method = 'exact'" + NL +
       "else:" + NL +
       "    # +1 in numerator and denominator: the unbiased Monte-Carlo p, which can never" + NL +
       "    # report 0 and stays conservative at small counts" + NL +
       "    _g = _rnd.Random(7)" + NL +
       "    tot = 200_000" + NL +
       "    idx = list(range(n))" + NL +
       "    ge = 1" + NL +
       "    for _ in range(tot):" + NL +
       "        _g.shuffle(idx)" + NL +
       "        if spearman(xs, [ys[i] for i in idx]) >= r:" + NL +
       "            ge += 1" + NL +
       "    tot += 1" + NL +
       "    method = 'Monte Carlo'" + NL +
       "p1 = ge / tot")
assert s.count(old) == 1, "perm anchor"
s = s.replace(old, new, 1)
s = s.replace('print(f"    one-sided exact permutation p = {p1:.4f} over {tot:,} permutations")',
              'print(f"    one-sided {method} permutation p = {p1:.4f} over {tot:,} draws")', 1)
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("c2_verdict.py: Monte-Carlo permutation above 10 folds")
