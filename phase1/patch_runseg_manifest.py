"""Make run_segment.py read phase1/corpus_manifest.txt instead of a hardcoded list.

Two hardcoded batch lists (here and in rebuild_corpus.sh) is a drift hazard: a new batch
added to one and not the other silently produces either a short corpus or unmapped cards.
One manifest, both readers.
"""
import io, re

P = "phase1/run_segment.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

start = s.index('FILES = [')
end = s.index(']', s.index('cards_senior_0805seq.jsonl')) + 1
new = ('FILES = [l.strip() for l in open("phase1/corpus_manifest.txt")' + NL +
       '         if l.strip()]   # single source of truth, shared with rebuild_corpus.sh')
s = s[:start] + new + s[end:]
assert "corpus_manifest" in s and "cards_senior_0724" not in s, "replacement failed"
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("run_segment.py now reads corpus_manifest.txt")
