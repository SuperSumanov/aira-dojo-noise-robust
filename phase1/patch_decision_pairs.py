"""Fix decision_pairs.py: sets spanning fragments must not straddle the split.

Mechanism found 2026-08-08: siblings under a parent that was pruned from the corpus
(no grade) each become their own fragment root; the set's side followed ch[0]'s fragment
while siblings' fragments drew independently -> 49/847 test pairs had a sibling whose
fragment (and its whole descendant set) was on the training side.

Fix: compute every sibling's fragment root; if their hold-membership disagrees, drop the
set (counted); else use the agreed side. Sets under a present parent are untouched (one
shared root). Also dump the per-pair fragment root so downstream checkers need no replay.
"""
import io

P = "phase1/decision_pairs.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

old = ('        t = cards[ch[0]]["task"]["name"]' + NL +
       '        if t not in ORI:' + NL +
       '            continue' + NL +
       '        lower = ORI[t]' + NL +
       '        in_hold = tree_root(ch[0]) in hold[t]' + NL +
       '        split = "test" if in_hold else "train"')
new = ('        t = cards[ch[0]]["task"]["name"]' + NL +
       '        if t not in ORI:' + NL +
       '            continue' + NL +
       '        lower = ORI[t]' + NL +
       '        sides_ = {tree_root(c) in hold[t] for c in ch}' + NL +
       '        if len(sides_) > 1:' + NL +
       '            n["__dropped_cross_fragment_sets__", -1, "drop"] += 1' + NL +
       '            continue' + NL +
       '        in_hold = sides_.pop()' + NL +
       '        split = "test" if in_hold else "train"')
assert s.count(old) == 1, "anchor split"
s = s.replace(old, new, 1)

io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("decision_pairs.py: cross-fragment sets now dropped, side agreed by all siblings")
