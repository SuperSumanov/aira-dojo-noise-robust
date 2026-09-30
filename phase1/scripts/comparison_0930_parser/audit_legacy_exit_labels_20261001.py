"""One read-only label-provenance audit on 25 already-deprotected old runs.

This does not resume training or compare prediction values. It checks only if
the newly identified pre-interpreter rejection/default-exit-zero signature is
present in the EXACT journals previously used by the 9/28 execution-risk study.
"""
import argparse,collections,hashlib,json,math,re,signal,tarfile
from pathlib import Path,PurePosixPath

ROOT=Path('/research/d7/spc/yzyang4/comparison-quarantine-20260919-_tda9fh6')
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
KEY=re.compile(rb'(?i)(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|password|credential|secret)\s*[=:]\s*["\x27]?[A-Za-z0-9_.:/+=-]{12,}')
PROTECTED=re.compile(rb'(?i)(first[-_ ]?960|target[-_ ]?(?:300|522)|private[_ -]?selection)')

PINS={'runs.json':'040c4463a967a34667dd1943735e923d0193a4f50c4c5eae24e9ada3a2da68c8',
      'structure.redacted.json':'2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94'}
GENERIC='Invalid solution: Solution is not valid python code.'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def pinned(path,expected):
    raw=path.read_bytes();assert sha(raw)==expected
    return json.loads(raw)


def facts(n):
    rc=n.get('exit_code');duration=n.get('exec_time')
    assert type(rc) is int
    numeric=type(duration) in (int,float) and math.isfinite(duration) and duration>=0
    value=n.get('term_out')
    if isinstance(value,list) and all(isinstance(x,str) for x in value):value='\n'.join(value)
    known_terminal=isinstance(value,str)
    generic=known_terminal and value.strip()==GENERIC
    return {'exit_zero':rc==0,'duration_known_nonnegative':numeric,
            'zero_duration':numeric and duration==0,'positive_duration':numeric and duration>0,
            'terminal_known':known_terminal,'generic_parser_rejection':generic,
            'default_zero_signature':numeric and duration==0 and rc==0,
            'generic_rejection_labeled_positive':generic and rc==0}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(300)
    runs=pinned(ROOT/'qwen-readout-v1/runs.json',PINS['runs.json'])
    wanted={r['run']:r for r in runs if r['arm'].startswith('forets') and r['journal_present']}
    assert len(wanted)==25
    manifest=pinned(ROOT/'structure.redacted.json',PINS['structure.redacted.json'])
    seen=set();rows=[];sources=[]
    for rec in manifest['archives']:
        p=ROOT/'archives'/rec['archive'];assert p.parent==ROOT/'archives'
        with tarfile.open(p,'r|gz') as tf:
            for member in tf:
                name=PurePosixPath(member.name)
                if not member.isfile() or name.name!='journal.jsonl' or name.parent.name!='checkpoint':continue
                run=sha(str(name.parent.parent).encode())[:16]
                if run not in wanted:continue
                assert run not in seen and member.size<=64*1024**2
                raw=tf.extractfile(member).read();assert sha(raw)==wanted[run]['journal_sha256']
                assert not any(x.search(raw) for x in (SECRET,KEY,PROTECTED))
                nodes=[json.loads(x) for x in raw.splitlines() if x.strip()]
                assert len(nodes)==wanted[run]['nodes']
                for n in nodes:
                    operator=(n.get('operators_used') or ['root'])[0]
                    if operator not in ('draft','improve','debug'):continue
                    assert type(n.get('exit_code')) is int
                    rows.append({'row_digest':sha((run+':'+n['id']).encode()),'run_digest':run,
                                 'task':wanted[run]['stratum'].split('/')[0], 'operator':operator,**facts(n)})
                sources.append({'run_digest':run,'journal_sha256':sha(raw)});seen.add(run)
    assert seen==set(wanted) and len(rows)==547 and len({r['row_digest'] for r in rows})==547
    keys=list(facts({'exit_code':0,'exec_time':0,'term_out':GENERIC}))
    totals={k:sum(r[k] for r in rows) for k in keys}
    groups=[]
    for task in sorted({r['task'] for r in rows}):
        for role in ('original','debug'):
            selected=[r for r in rows if r['task']==task and (r['operator']=='debug')==(role=='debug')]
            groups.append({'task':task,'role':role,'rows':len(selected),**{k:sum(r[k] for r in selected) for k in keys}})
    perrun=[]
    for run in sorted(seen):
        selected=[r for r in rows if r['run_digest']==run]
        original=[r for r in selected if r['operator']!='debug']
        perrun.append({'run_digest':run,'task':selected[0]['task'],'rows':len(selected),
                       'original_rows':len(original),'original_exit_zero':sum(r['exit_zero'] for r in original),
                       **{k:sum(r[k] for r in selected) for k in keys}})
    result={'status':'READ_ONLY_LABEL_PROVENANCE_AUDIT','runs':len(seen),'rows':len(rows),
            'original_rows':sum(r['operator']!='debug' for r in rows),'totals':totals,'by_task_role':groups,
            'per_run':perrun,'row_flags':rows,'sources':sources,'source_pins':PINS,
            'script_sha256':sha(Path(__file__).read_bytes()),'gpu_jobs':0,'api_calls':0,'model_fits':0,
            'boundary':'Only presence/absence of the identified parser-default signature is audited. Positive duration is not proof of valid submission or quality. No prediction or grade values used; no old metrics reselected.'}
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:result[k] for k in ('status','runs','rows','original_rows','totals','by_task_role','script_sha256')}))


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__}));raise SystemExit(2)
