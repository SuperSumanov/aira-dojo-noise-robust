"""Post-closure descriptive failure/cost/partial-output census; no new scoring."""
import hashlib,json,re,statistics
from collections import Counter
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert (R/'all-closed.json').exists() and (R/'closed.json').exists()
    summary=read(R/'readout-v1/summary.json');verify=read(R/'readout-v1/verification.json')
    assert verify['status']=='PASS' and verify['summary_sha256']==sha(R/'readout-v1/summary.json')
    accounting=summary['accounting'].split('|')
    assert accounting[0]=='15227' and accounting[1]=='COMPLETED'
    gpu_hours=int(accounting[2])*int(re.search(r'gres/gpu=(\d+)',accounting[3]).group(1))/3600
    rows=[];counts=Counter();valid_new=[]
    for s in read(R/'plan.json')['schedule']:
        ep=R/f'episode-{s["index"]}';check=read(ep/'action-1/result.json')
        result=read(ep/'action-2/result.json') if (ep/'action-2/result.json').exists() else None
        node=read(ep/'action-1/node.private.json');raw=(ep/'worker.private.log').read_bytes()
        assert not SECRET.search(raw),'credential-shaped log withheld'
        text=re.sub(r'\x1b\[[0-9;]*m','',raw.decode(errors='replace'))
        segments=[x for x in text.split('Executing code:')[1:] if repr(node['code']) in x]
        assert len(segments)==1,'ambiguous action-to-log binding'
        lines=segments[0].splitlines();streams=[]
        for j,line in enumerate(lines):
            if 'Stream output (length=' not in line:continue
            value=[]
            for after in lines[j+1:]:
                if re.match(r'^\[\d{4}-\d\d-\d\d ',after):break
                if after.startswith('... '):value.append(after[4:])
            streams.append('\n'.join(value).strip())
        check_status='success' if check['successful_check'] else 'timeout' if check['timed_out'] else 'error'
        final_status='valid' if result and result['valid'] else 'timeout' if result and result['timed_out'] else 'execution_error' if result else 'format_reject'
        if result is None:assert read(ep/'action-2/format.json')['status']=='REJECT','unclassified missing final result'
        final_errors=[]
        if result and not result['valid']:
            final_node=read(ep/'action-2/node.private.json')
            final_errors=sorted(set(re.findall(r'\b([A-Za-z][A-Za-z0-9]*(?:Error|Exception)):',final_node['terminal'])))
        initial=next(r['initial'] for r in summary['rows'] if r['index']==s['index'])
        gain=(initial-result['metric'] if s['task']=='spooky-author-identification' else result['metric']-initial) if result and result['valid'] else None
        if gain is not None:valid_new.append(gain)
        counts['check_'+check_status]+=1;counts['final_'+final_status]+=1
        lost=check_status!='success' and bool(streams)
        if lost:counts['failed_checks_with_received_streams_discarded']+=1
        rows.append(dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],
            check_status=check_status,check_exec_seconds=check['exec_seconds'],
            received_stream_blocks=len(streams),partial_streams_discarded=lost,
            received_public_metric_text=any(re.search(r'(?:OOF|AUC|log.?loss).*?\d\.\d',v,re.I) for v in streams),
            stream_text_sha256=[hashlib.sha256(v.encode()).hexdigest() for v in streams],
            stream_recovery='log-indent/whitespace normalized, not byte-identical raw streams',
            final_status=final_status,final_errors=final_errors,final_candidate_gain=gain,
            check_node_sha256=sha(ep/'action-1/node.private.json'),worker_log_sha256=sha(ep/'worker.private.log')))
    report=dict(status='DESCRIPTIVE_COMPLETE',summary_sha256=sha(R/'readout-v1/summary.json'),
        source_sha256=sha(Path(__file__)),rows=rows,counts=dict(counts),
        valid_new_improved=sum(x>1e-12 for x in valid_new),valid_new_tied=sum(abs(x)<=1e-12 for x in valid_new),
        valid_new_worse=sum(x< -1e-12 for x in valid_new),gpu_hours=gpu_hours,
        max_observed_check_seconds=max(r['check_exec_seconds'] for r in rows),
        qualifications=['Public-CV logs only, no protected cohort or final test.',
        'Native polling overshoots nominal per-action timeout; all actual wall time was charged to the common 900-second trajectory cap.',
        'Partial streams include headers/progress/repeated incumbent metrics; presence alone is not useful new discriminating evidence.',
        'Both arms share the same original channel. Fix is tested for future use, not applied to this completed batch.',
        'Equal retained outcomes do not establish policy equivalence or general futility. No new efficacy score, seed, task or fit added.'])
    with (R/'readout-v1/census.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(report,sort_keys=True))
if __name__=='__main__':main()
