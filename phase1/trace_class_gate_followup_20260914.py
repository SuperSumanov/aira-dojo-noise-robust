"""Post-readout call lineage and rejected-action shape, not causal mediation."""
import hashlib, importlib.util, json, re, sqlite3, sys
from contextlib import closing
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-9uosb6me')
EXPECTED='aa9c4610c0c6bc91011fca4e0edc8a6f6a8f7459351978bc73298d1a70258609'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p,h=None):
    b=p.read_bytes()
    if p.is_symlink() or SECRET.search(b) or (h and sha(b)!=h):raise ValueError('hash/security')
    return json.loads(b)

def main():
    s=read(ROOT/'cheap-selector-summary.json',EXPECTED);f=read(ROOT/'readout-finished.json')
    if f['summary_sha256']!=EXPECTED:raise ValueError('full readout')
    artifact=read(ROOT/'artifact.json')
    for name,h in artifact['source_files'].items():
        p=ROOT/'source'/name
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT/'source') or sha(p.read_bytes())!=h:raise ValueError('source drift')
    sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    spec=importlib.util.spec_from_file_location('closed_witness',ROOT/'source/src/dojo/solvers/fore_ts/execution_witness.py')
    witness=importlib.util.module_from_spec(spec);spec.loader.exec_module(witness)
    rows=[]
    for r in s['rows']:
        cp=Path(read(ROOT/'configs'/(r['run_id']+'.json'))['solver']['checkpoint_path'])
        if not cp.resolve().is_relative_to(ROOT/'runs'):raise ValueError('private scope')
        hits=[];pending=[];pool_stats=[]
        proofs=[q for q in s['selection_replays'] if q['run_id']==r['run_id']]
        for q in proofs:
            p=cp/'forets-candidates-private'/q['pool']
            if p.is_symlink() or sha(p.read_bytes())!=q['sha256']:raise ValueError('pool before')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=h or SECRET.search(raw.encode()) or sha(p.read_bytes())!=q['sha256']:raise ValueError('payload/security')
            v=json.loads(raw);bootstrap=bool(v['binding'].get('common_start'));calls=v['task_calls']
            for c in calls:
                if c['intent']['code_sha256']==r['action_code_sha256']:
                    hits.append({'pool':q['pool'],'role':'bootstrap' if bootstrap else c['intent']['role'],'state':c['state']})
            if bootstrap:continue
            selected=v['selected'][0];raw_code=v['candidates'][selected]['node']['code'];action=extract_code(raw_code)
            candidates=[c for c in calls if c['intent']['role']=='candidate']
            if not candidates:
                pending.append(dict(pool=q['pool'],raw_is_string=isinstance(raw_code,str),raw_chars=len(raw_code),delivered_is_string=isinstance(action,str),delivered_chars=len(action),delivered_nonempty=bool(action.strip()),legacy_witness_secret_hit=bool(witness.SECRET.search(action)),strict_credential_shape_hit=bool(SECRET.search(action.encode())),raw_sha256=sha(raw_code.encode()),delivered_sha256=sha(action.encode())))
            receipt_path=cp/'forets-cheap-ranker-private'/f"batch-{v['binding']['step']}.json"
            row=dict(pool=q['pool'],selected=selected,code_lengths=[len(c['node']['code'][:30000]) for c in v['candidates']],candidate_calls=len(candidates),debug_calls=sum(c['intent']['role']=='debug' for c in calls))
            if receipt_path.exists():
                receipt=read(receipt_path);row['scores']=receipt['scores']
                if 'raw_probabilities' in receipt:row['raw_probabilities']=receipt['raw_probabilities']
            pool_stats.append(row)
        roles=sorted({c['role'] for c in hits})
        rows.append(dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],technical_eligible=r['technical_eligible'],final_action_origin=roles[0] if len(roles)==1 else 'ambiguous' if roles else 'unresolved',matching_calls=hits,selected_not_dispatched=pending,pools=pool_stats))
    out=dict(role='posthoc_closed_seed48_lineage_and_rejected_action_shape',summary_sha256=EXPECTED,rows=rows,api_calls=0,gpu_jobs=0,models_fit=0,qualification_changed=False,script_sha256=sha(Path(__file__).read_bytes()),limitation='Code hashes identify observed call roles, not causal repairability. A malformed candidate is not an infrastructure diagnosis; original frozen qualification remains unchanged.')
    raw=(json.dumps(out,sort_keys=True)+'\n').encode()
    if SECRET.search(raw):raise ValueError('export gate')
    with (ROOT/'followup-trace.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**out)))
if __name__=='__main__':main()
