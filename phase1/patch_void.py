"""Mark the superseded stratifier so nobody reads its numbers as current.

gap_strat.py stratified on the wrong variable. Deleting it would hide that an earlier
verdict was published and withdrawn, which is exactly what the record should preserve, so
it stays in the tree with the reason stated at the top of the file.
"""
P = "phase1/gap_strat.py"
s = open(P, encoding="utf-8").read()
mark = "VOIDED 2026-08-12"
if mark in s:
    print("already marked")
    raise SystemExit(0)

note = f'''"""{mark} -- superseded by phase1/gap_strat3.py. Kept for audit, do not cite.

This script stratified lookahead pairs on |graded(better) - graded(worse)|. That is not the
margin the label encodes: a lookahead pair's better/worse is decided by what each node's
SUBTREE reached, and the file records that margin as gap_raw. The two coincide on 100.00% of
the 3,804 rows where steps_to_best == [0,0] and on 10.4% overall (phase1/confirm_gap.py), so
gap_raw is the label margin and every verdict printed below is indexed on the wrong axis.

Corrected results: phase1/gap_strat3.txt (lookahead) and phase1/gap_strat4.txt (the clean
budget-0 sibling set). Write-up: phase1/实验记录/2026-08-12/.
"""

'''
open(P, "w", encoding="utf-8").write(note + s)
print("marked", P)
