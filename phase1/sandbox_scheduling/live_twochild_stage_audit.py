"""Closed-trial stage coverage, never a replacement for the outcome gates.

Only operator counts/configuration/hashes leave the remote host. Development
journals are parsed for operator metadata; their candidate text/scores are not
reported. Prediction files, generation responses and protected cohorts are not read.
"""
import json
from pathlib import Path

from lifecycle_pilot import read, sha, write
from live_root_exposure_audit import mechanism

ROOT = Path('/research/d7/spc/yzyang4/scheduling-live-twochild-20261010-v1')
PLAN = '082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6'


def counts(nodes, children):
    if type(children) is not int or children != 2:
        raise ValueError('exact two-child scope')
    result = dict(recorded_drafts=0, recorded_debugs=0, recorded_improves=0)
    names = {'draft':'recorded_drafts','debug':'recorded_debugs','improve':'recorded_improves'}
    for node in nodes:
        operators = node.get('operators_used')
        if not isinstance(operators,list) or not operators or operators[0] not in names:
            raise ValueError('unrecognized journal operator; do not infer phase')
        result[names[operators[0]]] += 1
    result['recorded_nodes'] = len(nodes)
    result['root_draft_quota_unfinished'] = result['recorded_drafts'] < children
    result['recorded_improve_present'] = result['recorded_improves'] > 0
    return result


def main():
    if sha(ROOT/'plan.json') != PLAN or not (ROOT/'closed.json').exists():
        raise ValueError('exact closed trial required')
    primary = ROOT/'readout-v1/summary.json'
    if read(primary)['plan_sha256'] != PLAN:
        raise ValueError('primary closeout first')
    plan = read(ROOT/'plan.json')
    schedule = plan['schedule']
    if sorted(r['index'] for r in schedule) != list(range(16)):
        raise ValueError('all16 assigned runs retained')
    source = ROOT/'source/src/dojo/solvers/mcts/mcts.py'
    if sha(source) != plan['files'][str(source.relative_to(ROOT))]:
        raise ValueError('native source drift')
    proof = mechanism(source.read_text(encoding='utf-8'))
    if not proof['fixed_root_draft_batch_before_next_selection']:
        raise ValueError('unsupported source mechanism')
    rows = []
    for assignment in schedule:
        index = assignment['index']
        config = ROOT/'configs'/f'{index}.json'
        if sha(config) != plan['files'][str(config.relative_to(ROOT))]:
            raise ValueError('frozen config drift')
        cfg = read(config)['solver']
        if cfg['num_children'] != 2 or cfg['time_limit_secs'] != 1500:
            raise ValueError('changed common baseline')
        journal = ROOT/f'episode-{index}/checkpoint/journal.jsonl'
        row = dict(**assignment,journal_observed=journal.exists(),config_sha256=sha(config))
        if journal.exists():
            nodes = [json.loads(s) for s in journal.read_text().splitlines() if s.strip()]
            row.update(counts(nodes,cfg['num_children']),journal_sha256=sha(journal))
        rows.append(row)
    result = dict(plan_sha256=PLAN,primary_sha256=sha(primary),analysis_sha256=sha(__file__),
        source_mechanism=proof,assigned=16,rows=rows,changes_primary_gate=False,
        boundary='Descriptive stage exposure of all assigned runs. Journal records only: Improve count is not an improvement in score, success, native acceptance, or proof about interrupted/unrecorded calls. Missing journals are not zero counts. No across-configuration causal comparison.')
    out = ROOT/'stage-coverage-v1.json'
    write(out,result)
    print(json.dumps(dict(written=True,sha256=sha(out),assigned=16,
        observed_journals=sum(r['journal_observed'] for r in rows),
        recorded_improves=sum(r.get('recorded_improves',0) for r in rows)),sort_keys=True))


if __name__ == '__main__':
    main()
