"""Repair the flip re-splitter after two changes stepped on it.

build_runsplit's generic loop skips flip records (they carry x/y, not better/worse), so my
re-run left budget_flip_v3_runsplit.jsonl empty -- fix_flip_runsplit.py is the tool that
actually writes it. But that tool reads runsplit_holdruns.json as a plain list, and the
frozen-holdout patch upgraded the file to {"hold": [...], "all": [...]}. Teach it both
shapes, then run it so the artifact is restored rather than left clobbered.
"""
P = "phase1/fix_flip_runsplit.py"
s = open(P, encoding="utf-8").read()
a = 'hold = set(json.load(open("phase1/runsplit_holdruns.json")))'
b = '''_h = json.load(open("phase1/runsplit_holdruns.json"))
hold = set(_h["hold"] if isinstance(_h, dict) else _h)'''
if b in s:
    print("already patched")
elif a in s:
    open(P, "w", encoding="utf-8").write(s.replace(a, b))
    print("patched", P)
else:
    raise SystemExit("anchor not found")
