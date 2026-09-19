"""Exploratory readout of newly shared Qwen runs, not protected cohorts.

Select using recorded solver metric direction and buggy filtering. Official
grades are used only to evaluate that frozen choice, never to select it.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv,hashlib,json,math,os,statistics,tarfile
from pathlib import Path,PurePosixPath
from discover_comparison_20260919 import SECRET

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'comparison-quarantine-20260919-_tda9fh6'
LATEST='1b44e898bbae7ffc9098bbfa584ba842e0db2be5ae6bb8b5da0475d8ab34239f'
STRUCTURE_SHA='2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def number(x):
    if isinstance(x,bool) or x is None:return None
    try:y=float(x)
    except (TypeError,ValueError):return None
    return y if math.isfinite(y) else None

def solver_choice(nodes):
    pool=[n for n in nodes if not n.get('is_buggy') and number(n.get('metric')) is not None]
    if not pool:return None
    directions={n.get('metric_maximize') for n in pool}
    if len(directions)!=1 or not all(type(x) is bool for x in directions):
        raise ValueError('mixed or missing internal metric direction')
    direction=1 if next(iter(directions)) else -1
    return max(pool,key=lambda n:direction*float(n['metric']))

def plot_choice(nodes):
    pool=[n for n in nodes if number(n.get('metric')) is not None]
    def key(n):
        sign=-1 if (n.get('metric_info') or {}).get('is_lower_better') else 1
        return sign*float(n['metric'])
    return max(pool,key=key) if pool else None

def score(n):return number((n.get('metric_info') or {}).get('score')) if n else None
def stats(values):
    values=[x for x in values if x is not None]
    return dict(n=len(values),mean=statistics.mean(values) if values else None,
        median=statistics.median(values) if values else None,sd=statistics.stdev(values) if len(values)>1 else None)

def main():
    os.umask(0o077)
    raw=(ROOT/'structure.redacted.json').read_bytes()
    if digest(raw)!=STRUCTURE_SHA:raise ValueError('structure changed')
    state=BASE/'prospective_decision_v1'
    if (state/'LATEST').read_text().strip()!=LATEST:raise ValueError('LATEST changed')
    # Structural run identity/date only; no label or prediction file opened.
    protected_raw=(state/'snapshots'/LATEST/'accumulator/provisional_runs.jsonl').read_bytes()
    protected=[json.loads(l) for l in protected_raw.splitlines() if l]
    protected_hashes={r['source_sha256'] for r in protected}
    dates=[r['generation_started_at_utc'][:10] for r in protected]
    last_protected_date=max(dates)
    if last_protected_date>='2026-09-10':raise ValueError('date separation not established')
    data=json.loads(raw);records=[];node_exports=[];skipped=[];shapes=0
    for archive in data['archives']:
        configs={str(PurePosixPath(c['path']).parent):c for c in archive['configs']}
        allowed={k:v for k,v in configs.items() if v['fields'].get('solver.operators.draft.llm.client.model_id')=='qwen3.8-27b'
                 and v['fields'].get('metadata.launch_time','')[:10]>='2026-09-12'}
        skipped.extend(k for k in configs if k not in allowed)
        if not allowed:continue
        contents={k:{} for k in allowed}
        with tarfile.open(ROOT/'archives'/archive['archive'],'r|gz') as tf:
            for member in tf:
                p=PurePosixPath(member.name)
                if not member.isfile() or p.name not in ('journal.jsonl','journal_for_unselected.jsonl','state.json'):continue
                root=str(p.parent.parent)
                if root not in allowed or str(p.parent).split('/')[-1] not in ('checkpoint','json'):continue
                if member.size>256*1024**2:raise ValueError('member cap')
                payload=tf.extractfile(member).read()
                if digest(payload) in protected_hashes:raise ValueError('protected journal hash overlap')
                text=payload.decode();hits=len(SECRET.findall(text));shapes+=hits
                clean=SECRET.sub('[REDACTED_SECRET]',text)
                parsed=json.loads(clean) if p.name=='state.json' else [json.loads(l) for l in clean.splitlines() if l]
                contents[root][p.name]=(parsed,digest(payload),hits)
        print(json.dumps({'event':'ARCHIVE_PARSED','archive':archive['archive'],'allowed_runs':len(allowed)}),flush=True)
        for root,cfg in allowed.items():
            f=cfg['fields'];bucket=contents[root];run=digest(root.encode())[:16]
            nodes=bucket.get('journal.jsonl',([],None,0))[0]
            unselected=bucket.get('journal_for_unselected.jsonl',([],None,0))[0]
            selection=None;selection_status='NO_JOURNAL'
            if nodes:
                first=number(nodes[0].get('creation_time'))
                if first is None or datetime.fromtimestamp(first,timezone.utc).date().isoformat()<='2026-09-10':
                    raise ValueError('new run time not verified')
                try:selection=solver_choice(nodes);selection_status='OK' if selection else 'NO_ELIGIBLE_METRIC'
                except ValueError:selection_status='DIRECTION_UNKNOWN'
            chosen_plot=plot_choice(nodes)
            finite=[score(n) for n in nodes if score(n) is not None]
            dirs={bool(n.get('metric_info',{}).get('is_lower_better')) for n in nodes if score(n) is not None}
            if len(dirs)>1:raise ValueError('mixed official direction')
            lower=next(iter(dirs)) if dirs else None
            oracle=(min(finite) if lower else max(finite)) if finite else None
            actual=score(selection);plot=score(chosen_plot)
            st=bucket.get('state.json',({},None,0))[0]
            row=dict(run=run,stratum='/'.join(root.split('/')[:3]),arm=root.split('/')[3],seed=f.get('metadata.seed'),
                generator='qwen3.8-27b',commit=f.get('metadata.git_commit_id'),launch=f.get('metadata.launch_time'),
                search_budget=f.get('solver.time_limit_secs'),execution_timeout=f.get('solver.execution_timeout'),
                num_children=f.get('solver.num_children'),top_k=f.get('solver.critic_top_k'),
                journal_present=bool(nodes),nodes=len(nodes),unselected=len(unselected),selection_status=selection_status,
                selected_score=actual,plot_selected_all_score=plot,oracle_score=oracle,lower_better=lower,
                selection_changed=(selection.get('id')!=chosen_plot.get('id')) if selection and chosen_plot else None,
                selected_is_buggy=selection.get('is_buggy') if selection else None,
                plot_selected_is_buggy=chosen_plot.get('is_buggy') if chosen_plot else None,
                running_time=st.get('running_time'),current_step=st.get('current_step'),
                journal_sha256=bucket.get('journal.jsonl',([],None,0))[1],
                selection_regret=(actual-oracle if lower else oracle-actual) if actual is not None and oracle is not None else None)
            # Export no code, stdout, prompts or raw model responses.
            for group,items in [('executed',nodes),('unselected',unselected)]:
                for n in items:
                    node_exports.append(dict(run=run,group=group,id=n.get('id'),step=n.get('step'),parents=n.get('parents'),
                        creation_time=n.get('creation_time'),exec_time=number(n.get('exec_time')),metric=number(n.get('metric')),
                        metric_maximize=n.get('metric_maximize'),score=score(n),is_buggy=n.get('is_buggy'),
                        operators_used=n.get('operators_used'),code_sha256=digest((n.get('code') or '').encode()),
                        code_chars=len(n.get('code') or ''),field_names=sorted(n)))
            # Log-provided current_best_node can independently validate selection when schemas permit.
            logged=bucket.get('JOURNAL.jsonl',([],None,0))[0]
            row['event_schema']=sorted(logged[0]) if logged and isinstance(logged[0],dict) else []
            row['logged_best_steps']=sorted({str(n.get('current_best_node')) for n in logged if 'current_best_node' in n})
            records.append(row)
    if (state/'LATEST').read_text().strip()!=LATEST:raise ValueError('LATEST changed during analysis')
    out=ROOT/'qwen-readout-v1';out.mkdir()
    def dump(name,obj):
        encoded=json.dumps(obj,indent=2,allow_nan=False).encode()
        if SECRET.search(encoded.decode()):raise ValueError('unsafe export')
        (out/name).write_bytes(encoded)
    dump('runs.json',records);dump('nodes.json',node_exports)
    with (out/'runs.csv').open('x',newline='') as h:
        writer=csv.DictWriter(h,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    groups=defaultdict(list)
    for r in records:groups[(r['stratum'],r['arm'])].append(r)
    summaries=[]
    for (s,a),rs in sorted(groups.items()):
        summaries.append(dict(stratum=s,arm=a,runs=len(rs),with_journal=sum(r['journal_present'] for r in rs),
            selected=stats([r['selected_score'] for r in rs]),plot_selected_all=stats([r['plot_selected_all_score'] for r in rs]),
            oracle=stats([r['oracle_score'] for r in rs]),selection_changed=sum(r['selection_changed'] is True for r in rs),
            running_hours=stats([number(r['running_time'])/3600 if number(r['running_time']) is not None else None for r in rs]),
            unselected=sum(r['unselected'] for r in rs)))
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),scope='new local-Qwen comparison only; exploratory, not same-hardware causal effect',
        runs=len(records),skipped_configurations=len(skipped),protected_latest=LATEST,
        protected_identity_sha256=digest(protected_raw),protected_latest_start_date=last_protected_date,
        credential_shapes_redacted=shapes,groups=summaries,output=str(out),gpu_jobs=0,model_calls=0)
    dump('summary.json',summary)
    print(json.dumps(summary,allow_nan=False),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'READOUT_FAILED','error_type':type(exc).__name__,'reason':str(exc) if isinstance(exc,ValueError) else 'detail withheld'}),flush=True)
        raise SystemExit(2)
