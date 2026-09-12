"""Post-closure safe terminal classification, without exporting raw logs."""
from pathlib import Path
from contextlib import closing
import json
import re
import sqlite3
from forets_environment_build_20260912 import read, write, encode, sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-2o9mw39n')


def run():
    finish=read(ROOT/'readout-finished.json')
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json'])
    rows=[]
    with closing(sqlite3.connect((ROOT/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        for row in summary['rows']:
            rid=row['run_id']
            paths=list((ROOT/'runs/srun_pool').glob('*/identities/'+rid+'*.bounded/execution/stderr.private.log'))
            if len(paths)!=1:raise ValueError('unique owned terminal log')
            raw=paths[0].read_bytes();text=re.sub(r'\x1b\[[0-9;]*m','',raw.decode(errors='replace'))
            exceptions=re.findall(r'^((?:[A-Za-z_]+\.)*[A-Za-z_]+(?:Error|Expired|Exception)):',text,re.M)
            cap=db.execute('select cap from scopes where scope=?',(rid,)).fetchone()[0]
            calls,held,unresolved=db.execute('select count(*),sum(held),sum(state="unresolved") from calls where scope=?',(rid,)).fetchone()
            label=('kernel_readiness_before_candidate_dispatch' if
                'KernelReadinessError: Kernel readiness failed before candidate dispatch' in text else
                'bounded_api_attempt_budget_stopped' if 'BoundedAttemptError: bounded API attempt failed: BudgetStopped' in text else
                row['termination_reason'])
            rows.append(dict(run_id=rid,technical_eligible=row['technical_eligible'],
                classification=label,last_exception_type=exceptions[-1] if exceptions else None,
                stderr_sha256=sha(raw),scope_cap_nano_usd=cap,scope_calls=calls,
                scope_final_held_nano_usd=held,scope_unresolved=unresolved))
    result=dict(role='posthoc_terminal_diagnosis_not_a_changed_eligibility_rule',rows=rows,
        summary_sha256=finish['files']['common-start-summary.json'],
        limitation='Exact pre-rejection ledger state was not captured. Shared concurrent-reservation pressure is a source-and-scope-based inference, not a replayed peak measurement.')
    digest=write(ROOT/'terminal-diagnostics.json',encode(result))
    print(json.dumps(dict(rows=rows,sha256=digest)))


if __name__=='__main__':run()
