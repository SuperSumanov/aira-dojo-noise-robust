"""Fix value_pairs.py's either-endpoint split rule (the leak the 08-06 critique found).

Old rule: test if EITHER endpoint is held -> 87.3% of test pairs had one endpoint whose
tree was trained on. Correct rule is three-way: both held -> test, neither -> train,
straddling -> DROP (labelling straddlers 'train' would stuff held nodes back into
training, which is worse than the original bug). Existing files were already repaired
post-hoc at run level by build_runsplit.py; this stops any future regeneration from
being born leaky.
"""
import io

P = "phase1/value_pairs.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

old = ('            now_hi = (ca if (oa < ob if lower else oa > ob) else cb)' + NL +
       '            f.write(json.dumps({')
new = ('            now_hi = (ca if (oa < ob if lower else oa > ob) else cb)' + NL +
       '            in_hi, in_lo = hi in hold, lo in hold' + NL +
       '            if in_hi != in_lo:' + NL +
       '                continue          # straddles the holdout boundary: drop, never train' + NL +
       '            f.write(json.dumps({')
assert s.count(old) == 1, "anchor A"
s = s.replace(old, new, 1)

old2 = '"intask_split": "test" if (hi in hold or lo in hold) else "train",'
new2 = '"intask_split": "test" if in_hi else "train",'
assert s.count(old2) == 1, "anchor B"
s = s.replace(old2, new2, 1)

io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("value_pairs.py: three-way split (both->test, neither->train, straddle->drop)")
