"""Posthoc all-run error taxonomy; export no raw code/logs or credentials."""
import collections
import json
import re
from pathlib import Path

from forets_environment_build_20260912 import read, sha, write, encode
from inspect_forets_singlevote_execution_20260913 import ROOT

SECRET = re.compile(r'(?<![a-z0-9])sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|'
                    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', re.I)
RULES = {
    'xgboost_fit_keyword': ('XGBClassifier.fit() got an unexpected keyword argument',),
    'early_stopping_without_eval': ('For early stopping, at least one dataset and eval metric',),
    'categorical_fill_new_category': ('Cannot setitem on a Categorical with a new category',),
    'target_column_missing': ("KeyError: 'Transported'",),
    'target_type_unknown': ("Got 'unknown' instead",),
}


def classify(text):
    matches = [name for name, terms in RULES.items() if any(term in text for term in terms)]
    return matches or ['other_or_no_recognized_error']


def run():
    finish = read(ROOT / 'readout-finished.json')
    if finish['status'] != 'verified':
        raise ValueError('whole readout required')
    summary = read(ROOT / 'wallclock-summary.json', finish['summary_sha256'])
    rows, receipts = [], []
    for r in summary['rows']:
        path = ROOT / 'runs' / r['run_id'] / 'checkpoint/journal.jsonl'
        if not path.exists():
            receipts.append(dict(run_id=r['run_id'], journal_sha256=None,
                credential_shape_hits=None, missing_journal=True))
            continue  # preserve unavailable post-analysis logs, never impute success
        raw = path.read_bytes()
        text = raw.decode()
        hits = len(SECRET.findall(text))
        # Redact remotely before parsing any model-generated field.
        safe = SECRET.sub('[REDACTED]', text)
        receipts.append(dict(run_id=r['run_id'], journal_sha256=sha(raw), credential_shape_hits=hits))
        for line in safe.splitlines():
            node = json.loads(line)
            if node['step'] == 0:
                continue  # synthetic root can carry placeholder terminal text
            term = node.get('term_out') or ''
            if isinstance(term, list):
                term = '\n'.join(str(x) for x in term)
            if not isinstance(term, str):
                raise ValueError('terminal schema')
            if not term:
                continue  # root placeholder, not a completed execution log
            rows.append(dict(run_id=r['run_id'], task=r['task'], seed=r['seed'], arm=r['arm'],
                step=node['step'], categories=classify(term)))
        if sha(path.read_bytes()) != sha(raw):
            raise ValueError('journal changed after closure')
    groups = []
    for task in sorted({r['task'] for r in rows}):
        for arm in ('uniform_random', 'critic_topk_random'):
            rs = [r for r in rows if (r['task'], r['arm']) == (task, arm)]
            groups.append(dict(task=task, arm=arm, saved_journal_executions=len(rs),
                counts=dict(collections.Counter(c for r in rs for c in r['categories']))))
    result = dict(role='posthoc_taxonomy_not_causal_or_full_execution_coverage',
        summary_sha256=finish['summary_sha256'], inspector_sha256=sha(Path(__file__).read_bytes()),
        rows=rows, groups=groups, receipts=receipts,
        supersedes_root_counting_first_pass_sha256=sha((ROOT / 'singlevote-journal-errors.json').read_bytes()),
        limitation='Journal can omit returned calls interrupted before analysis. Other category is not success. No raw logs or new execution.')
    digest = write(ROOT / 'singlevote-journal-errors-v2.json', encode(result))
    print(json.dumps(dict(groups=groups, sha256=digest)))


if __name__ == '__main__':
    run()
