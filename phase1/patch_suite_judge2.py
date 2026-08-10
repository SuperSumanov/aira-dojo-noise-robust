"""Fix two misleading rows in the suite table (line-anchored, no escape guessing).

1. The judge was entered via a derived node score (fraction of comparisons won). A node
   appears in one or two sampled comparisons, so that score takes three values and ranking
   by it measures sampling noise. A judge emits a PAIRWISE decision -- read it directly.
2. rm_*_sib covered 37% of test pairs (sibling nodes only), a different and easier subset
   than every other row. Label partial-coverage rows so they are never read as comparable.
"""
import io

P = "phase1/predictor_suite.py"
lines = io.open(P, encoding="utf-8").read().split("\n")
NL = chr(10)

hdr = next(i for i, l in enumerate(lines) if "--- trained critics" in l)
block = [
    'print("' + chr(92) + 'n--- LLM judges (pairwise decisions read directly) ---", flush=True)',
    'import os as _os',
    'for _tag, _path in (("judge_qwen_max", "phase1/judge_qwenmax.jsonl"),',
    '                    ("judge_deepseek", "phase1/judge_code8k.jsonl")):',
    '    if not _os.path.exists(_path):',
    '        continue',
    '    _dec = {}',
    '    for _l in open(_path):',
    '        _d = json.loads(_l)',
    '        if _d.get("correct") is None:',
    '            continue',
    '        # both orders were asked; averaging them is what keeps position bias out',
    '        _dec.setdefault((_d["better"], _d["worse"]), []).append(_d["correct"])',
    '    _avg = {k: sum(v) / len(v) for k, v in _dec.items()}',
    '    evaluate(_tag, lambda b, w, _a=_avg: _a.get((b, w)), 0.0, 30.0,',
    '             "order-averaged pairwise")',
    '',
]
lines[hdr:hdr] = block

i = next(i for i, l in enumerate(lines) if l.startswith("for tag, path in"))
j = i
while "):" not in lines[j]:
    j += 1
lines[i:j + 1] = [
    'for tag, path in (("rm_1.5b_2048_SIBSUBSET", "phase1/rm_scores_sibling.json"),',
    '                  ("embed_frozen_0.5b", "phase1/embed_scores.json"),',
    '                  ("rm_1.5b_2048", "phase1/rm_scores_testpairs.json")):',
]
k = next(i for i, l in enumerate(lines) if 'evaluate(tag, lambda b, w: (None if b not in sc' in l)
lines[k:k + 2] = [
    '    note = "PARTIAL COVERAGE, not comparable" if "SIBSUBSET" in tag else "eval-only"',
    '    evaluate(tag, lambda b, w, _s=sc: (None if b not in _s or w not in _s',
    '                                       else int(_s[b] > _s[w])), 0.0, 0.05, note)',
]
io.open(P, "w", encoding="utf-8", newline=NL).write(NL.join(lines))
print("predictor_suite.py patched: judges pairwise, partial-coverage rows labelled")
