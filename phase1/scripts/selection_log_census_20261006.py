"""Post-hoc bounded log census. Unknown output formats are not negative evidence.

Only old approved development records and the closed factorial batch are read.
No new execution, labels, fitting, selection rule or causal prevalence estimate.
Source echoes in tracebacks must not count as executed model-selection events.
"""
import ast
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys

B = Path('/research/d7/spc/yzyang4')
R = B/'collateral-factorial-20261006-v1'
SOURCE_SHA = '4c96405a1d58dcddbf228b801cd7516085a56a2d1eae5d9bd601c2384eb452e4'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    raw = Path(p).read_bytes()
    assert not SECRET.search(raw), 'credential-shape hit; no raw output'
    return json.loads(raw)


def inspect(terminal):
    lines = terminal.splitlines()
    tables, selections = [], []
    for i, line in enumerate(lines):
        if re.fullmatch(r'OOF AUC per model:\s*', line):
            values = {}
            for following in lines[i+1:i+12]:
                m = re.fullmatch(r'\s+([a-zA-Z0-9_-]+)\s*=\s*(0?\.\d+|1\.0+)\s*', following)
                if m:
                    values[m[1]] = float(m[2])
                elif values:
                    break
            if values:
                tables.append(values)
        m = re.fullmatch(r'Models kept in blend[^\\\n]*:\s*(\[[^\\\n]*\])', line)
        if m:
            try:
                names = ast.literal_eval(m[1])
            except (ValueError, SyntaxError):
                continue
            if isinstance(names, list) and names and all(isinstance(x, str) and re.fullmatch(r'[a-zA-Z0-9_-]+', x) for x in names):
                selections.append(names)
        m = re.fullmatch(r'Blend \([\d.]+\) < best single \(([a-zA-Z0-9_-]+)=[\d.]+\); using single model\.', line)
        if m:
            selections.append([m[1]])
    return dict(tables=tables, selections=selections)


def tests():
    assert inspect('print("OOF AUC per model:")\\nprint("  xgb = 0.7")')['tables'] == []
    assert inspect('OOF AUC per model:\n   xgb = 0.70000\nDone')['tables'] == [dict(xgb=.7)]
    assert inspect("Models kept in blend: ['xgb', 'lgb']")['selections'] == [['xgb','lgb']]
    assert inspect("print(\"Models kept in blend: ['xgb']\")")['selections'] == []
    assert inspect('Blend (0.680) < best single (xgb=0.690); using single model.')['selections'] == [['xgb']]
    assert inspect('OOF AUC per model:\n  not = a number')['tables'] == []
    return dict(fixtures=6, status='PASS')


def main():
    os.umask(0o077)
    source = B/'collateral-local-20261006-v2/summary.json'
    assert digest(source) == SOURCE_SHA
    rows = read(source)['rows']
    seen, counts = set(), collections.defaultdict(collections.Counter)
    records = []
    for row in rows:
        if row['status'] != 'PARSED':
            continue
        key = row['task'], row['child_sha256']
        if key in seen:
            continue
        seen.add(key)
        path = B/row['batch']/f"episode-{row['episode']}"/f"action-{row['step']}"/'node.private.json'
        terminal = read(path)['terminal']
        found = inspect(terminal)
        c = counts[row['task']]
        c['unique_children'] += 1
        c['substring_header_hits_not_execution_evidence'] += 'OOF AUC per model' in terminal
        c['executed_table_recognized'] += bool(found['tables'])
        c['selection_list_recognized'] += bool(found['selections'])
        c['last_recognized_selection_single'] += bool(found['selections'] and len(found['selections'][-1]) == 1)
        records.append(dict(task=row['task'], code_sha256=row['child_sha256'], source_sha256=digest(path),
                            table_recognized=bool(found['tables']), selection_sizes=[len(x) for x in found['selections']]))
    with (R/'readout-v1/runs.csv').open(newline='') as f:
        runs = list(csv.DictReader(f))
    case0 = []
    for row in runs:
        if row['case'] != '0':
            continue
        path = R/f"episode-{row['index']}"/'action-0/terminal.private.json'
        found = inspect(read(path)['terminal'])
        assert found['tables'] and found['selections'] == [['xgb']]
        case0.append(dict(arm=row['arm'], source_sha256=digest(path), **found,
                          prediction_sha256=row['prediction_sha256']))
    hashes = {r['arm']:r['prediction_sha256'] for r in case0}
    assert hashes['P'] == hashes['PC'] and hashes['C'] == hashes['CP']
    result = dict(status='POSTHOC_DESCRIPTIVE_ONLY', source_sha256=SOURCE_SHA,
        script_sha256=digest(__file__), tests=tests(), source_rows=len(rows), counts=dict(counts),
        records=records, case0=case0, boundary=__doc__,
        caveats=['Parser recognizes narrow known log formats; all unrecognized cases remain unknown.',
                 'Code hashes are not independent physical runs or tasks.',
                 'A logged selection is evidence of that execution, not permanent component irrelevance.',
                 'Case0 is a selected mechanistic example, not a prevalence estimate or deployable benefit.'])
    out = R/'selection-log-v1'; out.mkdir(mode=0o700, exist_ok=False)
    with (out/'summary.json').open('x') as f:
        json.dump(result, f, sort_keys=True, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(dict(counts=dict(counts), case0=case0, sha256=digest(out/'summary.json'))))


if __name__ == '__main__':
    print(json.dumps(tests())) if sys.argv[1:] == ['--tests'] else main()
