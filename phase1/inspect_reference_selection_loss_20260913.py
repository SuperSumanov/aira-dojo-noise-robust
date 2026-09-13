"""Inspect all closed development journals for delivery/filtering, no reselection."""
import json
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')


def main():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('full closure')
    summary=read(ROOT/'common-start-summary.json',finish['files']['common-start-summary.json']);rows=[]
    for r in summary['rows']:
        path=ROOT/'runs'/r['run_id']/'checkpoint/journal.jsonl';raw=path.read_bytes();nodes=[]
        for line in raw.splitlines():
            n=json.loads(line)
            info=n.get('metric_info') or {}
            if not isinstance(info,dict):raise ValueError('metric info schema')
            # No analysis/log text, credentials or candidate source is exported.
            grade={k:info.get(k) for k in ('score','valid_submission','is_lower_better')}
            if any(v is not None and type(v) not in (int,float,bool) for v in grade.values()):raise ValueError('numeric fields only')
            nodes.append(dict(step=n['step'],parents=n['parents'],code_sha256=sha(n['code'].encode()),
                final_selected=n['code']!='' and sha(n['code'].encode())==r['selected_code_sha256'],
                is_buggy=n.get('is_buggy'),exit_code=n.get('exit_code'),search_metric=n.get('metric'),
                maximize=n.get('metric_maximize'),execution_seconds=n.get('exec_time'),external_report_fields=grade))
        if sha(path.read_bytes())!=sha(raw):raise ValueError('journal drift')
        rows.append(dict(run_id=r['run_id'],journal_sha256=sha(raw),nodes=nodes))
    result=dict(role='posthoc_all_run_selection_diagnostic_not_new_outcome_or_oracle',source_tree=summary['source_tree'],rows=rows,
        summary_sha256=finish['files']['common-start-summary.json'],script_sha256=sha(Path(__file__).read_bytes()),
        limitation='No reselection or recovered e2e score. Search-visible metrics may be agent reported and are not a new trusted evaluator. Protected cohorts are not accessed.')
    print(json.dumps(dict(sha256=write(ROOT/'selection-diagnostic.json',encode(result)),rows=rows)))


if __name__=='__main__':main()
