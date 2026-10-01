"""Fixed complete-denominator readout. Reads ONLY this new development pilot."""
import argparse,csv,hashlib,json,math,statistics
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
def read(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def collect(root):
    plan=read(root/'plan.json');rows=[]
    for s in plan['schedule']:
        ep=root/f'episode-{s["index"]}';actions=[];gens=[];attempts=0
        for i in range(5):
            d=ep/f'action-{i}'
            if (d/'feedback.json').exists():attempts+=1
            if (d/'result.json').exists():
                r=read(d/'result.json')
                if r['elapsed_seconds']>1800:raise ValueError('late result')
                if r['valid'] and (not r['execution_started'] or r['exit_code']!=0 or r['timed_out'] or r['metric'] is None or not math.isfinite(r['metric'])):raise ValueError('invalid success')
                actions.append(r)
            if (d/'generation.private.json').exists():
                g=read(d/'generation.private.json');gens.append({'usage':g.get('usage',{}),'generation_seconds':g['generation_seconds']})
        started=(ep/'launch.json').exists();finished=(ep/'finished.json').exists();closed=(ep/'closed.json').exists()
        valid=[r for r in actions if r['valid']]
        best=(min if s['task']=='spooky-author-identification' else max)([r['metric'] for r in valid]) if valid else None
        initial=next((r for r in actions if r['step']==0),None);initial_value=initial['metric'] if initial and initial['valid'] else None
        # A closed step with no finished receipt may have been killed at its deadline.
        status=read(ep/'finished.json')['status'] if finished else ('budget_exhausted' if closed and read(ep/'closed.json')['worker_deadline_reached'] else ('running' if started else 'not_started'))
        direction=-1 if s['task']=='spooky-author-identification' else 1
        def tokens(key):
            values=[g['usage'].get(key) for g in gens]
            return sum(values) if len(gens)==attempts and all(type(v) is int for v in values) else None
        row={**s,'status':status,'step_closed':closed,'actions_returned':len(actions),'valid_actions':len(valid),'generation_attempts':attempts,'unknown_usage_attempts':attempts-len(gens),'generated_modifications':len(gens),'initial_valid':initial_value is not None,'initial_metric':initial_value,'selected_metric':best,'oriented_development_gain':direction*(best-initial_value) if best is not None and initial_value is not None else None,'first_valid_seconds':valid[0]['elapsed_seconds'] if valid else None,'completed_generator_seconds':sum(g['generation_seconds'] for g in gens),'prompt_tokens':tokens('prompt_tokens'),'completion_tokens':tokens('completion_tokens'),'returned_task_execution_seconds':sum(r['exec_seconds'] for r in actions),'episode_elapsed_seconds':read(ep/'finished.json')['elapsed_seconds'] if finished and 'elapsed_seconds' in read(ep/'finished.json') else None,'budget_seconds':1800,'commit':plan['base_commit'],'plan_sha256':digest(root/'plan.json'),'initial_executed_code_sha256':initial.get('executed_code_sha256') if initial else None}
        rows.append(row)
    comparisons=[]
    for start in range(6):
        group={r['arm']:r for r in rows if r['start']==start}
        for high,low in [('C','B'),('B','A'),('C','A')]:
            h,l=group[high],group[low];done=h['step_closed'] and l['step_closed'] and h['status'] in ('completed','budget_exhausted') and l['status'] in ('completed','budget_exhausted');d=-1 if h['task']=='spooky-author-identification' else 1
            paired=done and h['selected_metric'] is not None and l['selected_metric'] is not None
            observed_initial=h['initial_metric'] is not None and l['initial_metric'] is not None
            observed_hash=h['initial_executed_code_sha256'] is not None and l['initial_executed_code_sha256'] is not None
            comparisons.append({'task':h['task'],'start':start,'contrast':high+'-'+low,'both_closed':done,'both_valid':paired,'validity_difference':int(h['selected_metric'] is not None)-int(l['selected_metric'] is not None) if done else None,'oriented_gain_difference':h['oriented_development_gain']-l['oriented_development_gain'] if paired and observed_initial else None,'oriented_selected_difference':d*(h['selected_metric']-l['selected_metric']) if paired else None,'initial_metric_equal':h['initial_metric']==l['initial_metric'] if done and observed_initial else None,'initial_code_equal':h['initial_executed_code_sha256']==l['initial_executed_code_sha256'] if done and observed_hash else None})
    return {'rows':rows,'comparisons':comparisons,'scope':'development code-start, not full E2E/independent final eval; max four modifications plus 1800s deadline','planned':18,'started':sum(r['status']!='not_started' for r in rows),'closed':sum(r['step_closed'] for r in rows),'valid_among_closed':sum(r['step_closed'] and r['selected_metric'] is not None for r in rows),'plan_sha256':digest(root/'plan.json')}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    result=collect(ROOT);a.out.mkdir(mode=0o700,exist_ok=False)
    for name,rows in [('runs.csv',result['rows']),('comparisons.csv',result['comparisons'])]:
        with (a.out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (a.out/'summary.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','comparisons')},sort_keys=True))
