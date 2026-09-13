"""Write closed-parent facts only; never activate an account or dispatch a job."""
from contextlib import closing
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
from forets_environment_build_20260912 import read,write,encode,sha
from compare_scope_classic_20260914 import ES,CLASSIC,scope_summary,reference_summary
from build_scope_preservation_20260914 import AUTH_PARENT


def run():
    closure=read(ES/'readout-finished.json')
    if closure.get('status')!='verified':raise ValueError('full sixteen-run closure')
    scope=read(ES/'edit-scope-summary.json',closure['files']['edit-scope-summary.json'])
    cc=read(CLASSIC/'readout-finished.json');reference=read(CLASSIC/'summary.json',cc['summary_sha256'])
    a=scope_summary(scope['rows']);b=reference_summary(scope['rows'],reference['rows'])
    with closing(sqlite3.connect((ES/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT digest,stopped FROM auth').fetchall()!=[(AUTH_PARENT,0)]:raise ValueError('account identity/live state')
        calls=db.execute('SELECT * FROM calls ORDER BY id').fetchall()
    counts=[len(calls),sum(r[2] for r in calls),sum(r[3] or 0 for r in calls),sum(r[4]=='unresolved' for r in calls)]
    if counts[3]!=2:raise ValueError('new unsettled calls require review')
    conditions=dict(original_scope_gate=a['original_development_gate'],strong_reference_gate=b['successor_reference_gate'],
        headroom_for_two_concurrent_requests=counts[1]+2*700_000_000<=10**10)
    facts=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),parent=str(ES),authorization=AUTH_PARENT,
        counts=counts,calls_sha256=sha(encode(calls)),closure_sha256=sha((ES/'readout-finished.json').read_bytes()),
        reference_closure_sha256=sha((CLASSIC/'readout-finished.json').read_bytes()),
        comparison_conditions=conditions,dispatch_allowed=all(conditions.values()),
        script_sha256=sha(Path(__file__).read_bytes()),
        warning='Investment gate only, not significance or novelty. This command starts no successor.')
    target=ES/'scope-successor-facts.json'
    print(json.dumps(dict(sha256=write(target,encode(facts)),**facts)))


if __name__=='__main__':os.umask(0o077);run()
