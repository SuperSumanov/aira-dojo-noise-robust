"""Post-readout execution metadata only; never infer success from exit status."""
import collections
import json
from pathlib import Path
import sqlite3

from forets_environment_build_20260912 import read, sha, write, encode

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')


def classify(call):
    if call['state'] == 'started':
        return 'unfinished'
    if call['state'] != 'returned':
        return call['state']
    metadata = call['execution_metadata']
    if metadata['timed_out_reported']:
        return 'program_timeout'
    code = metadata['exit_code_reported']
    if code is None:
        return 'exit_unknown'
    if type(code) is not int:
        raise ValueError('exit-code type')
    return 'exit_zero_not_submission_validation' if code == 0 else 'program_error'


def run():
    finish = read(ROOT / 'readout-finished.json')
    if finish['status'] != 'verified':
        raise ValueError('whole-matrix readout first')
    summary = read(ROOT / 'wallclock-summary.json', finish['summary_sha256'])
    prepared = read(ROOT / 'prepared.json', read(ROOT / 'build.json')['prepared_sha256'])
    planned = {r['run_id']: r for r in prepared['run_configs']}
    rows = []
    for row in summary['rows']:
        rid = row['run_id']
        cfg = read(ROOT / 'configs' / (rid + '.json'), planned[rid]['config_sha256'])
        checkpoint = Path(cfg['solver']['checkpoint_path'])
        if not checkpoint.resolve().is_relative_to(ROOT):
            raise ValueError('foreign checkpoint')
        for path in sorted((checkpoint / 'forets-candidates-private').glob('batch-*.sqlite')):
            before = sha(path.read_bytes())
            with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
                values = db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
            if len(values) != 1 or sha(values[0][0].encode()) != values[0][1]:
                raise ValueError('snapshot hash')
            snapshot = json.loads(values[0][0])
            for call in snapshot['task_calls']:
                rows.append(dict(run_id=rid, task=row['task'], seed=row['seed'], arm=row['arm'],
                    batch_step=snapshot['binding']['step'], call_id=call['call_id'],
                    role=call['intent']['role'], state=classify(call),
                    execution_metadata=call['execution_metadata'], task_wall_ns=call['task_wall_ns'],
                    ledger_sha256=before))
            if sha(path.read_bytes()) != before:
                raise ValueError('concurrent mutation')
    groups = []
    for task in sorted({r['task'] for r in rows}):
        for arm in ('uniform_random', 'critic_topk_random'):
            group = [r for r in rows if (r['task'], r['arm']) == (task, arm)]
            groups.append(dict(task=task, arm=arm, calls=len(group),
                by_role={role: dict(collections.Counter(r['state'] for r in group if r['role'] == role))
                         for role in ('candidate', 'debug')}))
    result = dict(role='posthoc_development_diagnostic_not_new_effect_test',
        summary_sha256=finish['summary_sha256'], inspector_sha256=sha(Path(__file__).read_bytes()),
        limitation='Exit zero is not valid submission; timed-out and unfinished calls stay distinct. No new execution or raw logs.',
        rows=rows, groups=groups)
    digest = write(ROOT / 'singlevote-execution-metadata.json', encode(result))
    print(json.dumps(dict(calls=len(rows), groups=groups, sha256=digest)))


if __name__ == '__main__':
    run()
