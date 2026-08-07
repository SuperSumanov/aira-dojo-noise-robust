"""Make decision_baselines.py take the pairs file as argv[1] (default v1)."""
import io
P = "phase1/decision_baselines.py"
s = io.open(P, encoding="utf-8").read()
old = 'CARDS, PAIRS = "phase1/cards_current.jsonl", "phase1/decision_pairs_v1.jsonl"'
new = ('import sys' + chr(10) +
       'CARDS = "phase1/cards_current.jsonl"' + chr(10) +
       'PAIRS = sys.argv[1] if len(sys.argv) > 1 else "phase1/decision_pairs_v1.jsonl"' + chr(10) +
       'print("pairs file:", PAIRS)')
assert s.count(old) == 1
io.open(P, "w", encoding="utf-8", newline=chr(10)).write(s.replace(old, new, 1))
print("parameterized")
