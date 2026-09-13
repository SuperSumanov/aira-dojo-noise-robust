"""Bounded remotely redacted explanation for every exit-zero buggy saved node."""
import json
from pathlib import Path
import re
from forets_environment_build_20260912 import read,write,encode,sha
from inspect_branching_completion_errors_20260913 import SECRET

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')


def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('closure')
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json']);rows=[]
    for r in summary['rows']:
        path=ROOT/'runs'/r['run_id']/'checkpoint/journal.jsonl';raw=path.read_bytes()
        for line in raw.splitlines():
            n=json.loads(line)
            if not (n['step']>0 and n.get('exit_code')==0 and n.get('is_buggy') is True):continue
            analysis=SECRET.sub('[REDACTED]',n.get('analysis') or '')
            output=SECRET.sub('[REDACTED]',n.get('term_out') or '')
            code=SECRET.sub('[REDACTED]',n['code'])
            interesting=[x[:450] for x in output.splitlines() if re.search(r'(?i)valid|accuracy|auc|score|loss|error|warning',x)]
            print_lines=[x.strip()[:450] for x in code.splitlines() if 'print(' in x]
            rows.append(dict(run_id=r['run_id'],step=n['step'],code_sha256=sha(n['code'].encode()),journal_sha256=sha(raw),
                analysis=analysis[:2200],execution_metric_lines=interesting[-12:],program_print_statements=print_lines[:12]))
    result=dict(role='posthoc_redacted_explanation_no_reexecution',rows=rows,script_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(sha256=write(ROOT/'analysis-mismatch.json',encode(result)),rows=rows)))


if __name__=='__main__':main()
