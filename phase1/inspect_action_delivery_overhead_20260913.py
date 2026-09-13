"""Post-closure persistence timing and exact payload comparison; no reselection."""
import json
from pathlib import Path
import statistics
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')

def run():
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified':raise ValueError('closed independent readout required')
    for n,h in finish['files'].items():
        if sha((ROOT/n).read_bytes())!=h:raise ValueError('closed result drift')
    summary=read(ROOT/'action-delivery-summary.json');original=read(ROOT/'wallclock-summary.json')
    action_proofs={p['run_id']:p for p in summary['proofs']};original_proofs={p['run_id']:p for p in original['proofs']}
    rows=[]
    for r in summary['rows']:
        directory=ROOT/'incumbents'/r['run_id']/'action-incumbents';times=[];commits=[];partial=0
        for path in sorted(directory.glob('action-*.commit.json')):
            try:c=read(path)
            except json.JSONDecodeError:
                partial+=1;continue  # Same incomplete-commit rule as the frozen reader.
            data=directory/c['data_file']
            if path.is_symlink() or data.is_symlink() or data.parent!=directory:raise ValueError('path')
            raw=data.read_bytes();d=json.loads(raw)
            if sha(raw)!=c['data_sha256']:raise ValueError('action hash')
            elapsed=(c['durable_ns']-d['observation_ns'])/1e9
            if elapsed<0:raise ValueError('negative persistence interval')
            times.append(elapsed);commits.append(sha(path.read_bytes()))
        a=action_proofs.get(r['run_id']);b=original_proofs.get(r['run_id'])
        rows.append(dict(run_id=r['run_id'],records=len(times),incomplete_commits_ignored=partial,recording_seconds_lower_bound=sum(times),
            median_data_record_seconds=statistics.median(times) if times else None,max_data_record_seconds=max(times) if times else None,
            exact_submission_bytes_differ=(a['submission_sha256']!=b['submission_sha256']) if a and b else None,
            code_bytes_differ=r['selected_submission_differs'],commit_hashes=commits))
    out=dict(role='post_closeout_persistence_timing_and_exact_submission_identity',rows=rows,
        source_summary_sha256=sha((ROOT/'action-delivery-summary.json').read_bytes()),
        observed_data_record_seconds_total=sum(r['recording_seconds_lower_bound'] for r in rows),
        limitation='Intervals include node projection, payload construction and data write/fsync; exclude the following commit write/fsync and original journal logging. Lower bound, not full recording overhead or an uninstrumented counterfactual.')
    digest=write(ROOT/'action-overhead.json',encode(out));print(json.dumps(dict(summary_sha256=digest,**out)))

if __name__=='__main__':run()
