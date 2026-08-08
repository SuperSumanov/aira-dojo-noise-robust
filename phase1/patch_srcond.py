"""Add --sr-cond: let the model SEE the agent's own reported validation score.

Every RM we have trained is code-only. It reaches 0.667 while the free self-report reaches
0.780 on the same pairs -- but on the 444 pairs the self-report gets WRONG, the code-only
model is right 55.9% (CI lower bound 0.512). So the code carries information orthogonal to
the self-report; we have simply never given a model both at once and asked it to beat the
self-report alone. Gating failed because the gate could not locate the disagreement region;
conditioning needs no gate.

The score goes in the HEAD (survives head-25% truncation by construction, unlike the budget
line which needed tail handling). Missing self-report is stated explicitly rather than
omitted, so 'no score' is a learnable state instead of an invisible one -- it is also what
deployment sees.

Raw value, not a within-task z-score: normalising would require task statistics computed
over the eval pool, which leaks distributional information across the split. The task name
is already in the header, so per-task calibration is learnable.
"""
import io

P = "phase1/rm_train_hf.py"
s = io.open(P, encoding="utf-8").read()
NL = chr(10)

# --- flag ---
old = 'ap.add_argument("--budget-cond", action="store_true", help="expose remaining budget to the model")'
new = (old + NL +
       'ap.add_argument("--sr-cond", action="store_true",' + NL +
       '                help="expose the agent\'s own reported validation score to the model")')
assert s.count(old) == 1, "anchor flag"
s = s.replace(old, new, 1)

# --- collect self-reports alongside code/task ---
old2 = ('code, ctask = {}, {}' + NL +
        'for l in open(a.cards):' + NL +
        '    d = json.loads(l)' + NL +
        '    code[d["id"]] = (d.get("code") or "")[:60000]' + NL +
        '    ctask[d["id"]] = (d.get("task") or {}).get("name", "")')
new2 = ('code, ctask, csr = {}, {}, {}' + NL +
        'for l in open(a.cards):' + NL +
        '    d = json.loads(l)' + NL +
        '    code[d["id"]] = (d.get("code") or "")[:60000]' + NL +
        '    ctask[d["id"]] = (d.get("task") or {}).get("name", "")' + NL +
        '    try:' + NL +
        '        _v = float((d.get("obs") or {}).get("val_at_low"))' + NL +
        '        csr[d["id"]] = _v if _v == _v and abs(_v) != float("inf") else None' + NL +
        '    except (TypeError, ValueError):' + NL +
        '        csr[d["id"]] = None')
assert s.count(old2) == 1, "anchor cards"
s = s.replace(old2, new2, 1)

# --- render: inject the reported score into the head ---
old3 = ('def render(cid, budget=None):' + NL +
        '    head = ""' + NL +
        '    if a.task_cond:' + NL +
        '        head += "# MLE-bench task: " + ctask.get(cid, "") + NL')
new3 = ('def render(cid, budget=None):' + NL +
        '    head = ""' + NL +
        '    if a.task_cond:' + NL +
        '        head += "# MLE-bench task: " + ctask.get(cid, "") + NL' + NL +
        '    if a.sr_cond:' + NL +
        '        _s = csr.get(cid)' + NL +
        '        head += ("# agent-reported validation score: " +' + NL +
        '                 ("unavailable (no score produced)" if _s is None' + NL +
        '                  else format(_s, ".6g")) + NL)')
assert s.count(old3) == 1, "anchor render"
s = s.replace(old3, new3, 1)

# --- record it in the CSV so a row is self-describing ---
old4 = '"acc_len_ctrl": acc_len, "stratified": a.eval_stratify,'
new4 = '"acc_len_ctrl": acc_len, "stratified": a.eval_stratify, "sr_cond": a.sr_cond,'
assert s.count(old4) == 1, "anchor csv"
s = s.replace(old4, new4, 1)

io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("rm_train_hf.py: --sr-cond added (head placement, explicit 'unavailable', CSV column)")
