"""Second raw-archive implementation; no imports from the original extraction.

All source archives are pinned. This reads the same authorized observational
cohort, not a new blind effect evaluation. No candidate text is exported.
"""
import argparse,csv,hashlib,json,math,os,re,signal,tarfile
from pathlib import Path,PurePosixPath
from collections import Counter,defaultdict

PIN={
 'google-quest-challenge.tar.gz':'56c43a1efb46eebfcb8ab36699f4bf90e0c590c63ae942bf13734038629c44a0',
 'petfinder-pawpularity-score.tar.gz':'204cd439641b12c0f253127410e3d1e1e9c860f6e95cfcb72dd64378822567aa'}
# Credential prefixes must begin a token ("task-long-identifier" contains "sk-").
# Assignment scanning below remains independent of this token boundary.
BAD=re.compile(rb'(?i)(?:(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})|first[-_]?960|target[-_]?(?:300|522)|private[-_]selection)')
KEY=re.compile(rb'(?i)["\x27](?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)["\x27]\s*:\s*["\x27](?!\s*["\x27])[^"\x27]{12,}["\x27]')
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def grade(n,task):
    v=n.get('metric_info/valid_submission')
    assert v is None or type(v) in (bool,int,float) and v in (0,1)
    if v!=1:return None
    lower=n['metric_info/is_lower_better'];assert lower in (0,1)
    assert bool(lower)==(task=='petfinder-pawpularity-score')
    x=n['metric_info/score'];assert type(x) in (int,float)
    return float(x) if math.isfinite(x) else None
def category(n):
    if n['step']==0:return 'root'
    assert isinstance(n['operators_used'],list)
    ops=set()
    for text in n['operators_used']:
        assert isinstance(text,str)
        words=set(re.findall('[a-z]+',text.lower()))
        ops.update(words.intersection({'draft','improve','debug'}))
    assert len(ops)==1
    return next(iter(ops))
def analyze(events,task):
    segments=[]
    for e in events:
        n=e['data']
        if n['step']==0:segments.append([])
        assert segments
        segments[-1].append(n)
    counts=Counter();full_time=[];debug_time=[];all_lineages=[];final=None;ancestor=None
    for nodes in segments:
        steps={n['step']:n for n in nodes}
        assert len(steps)==len(nodes)
        checked=[];last_pointer=0;lineages=defaultdict(list)
        for n in nodes:
            step=n['step'];op=category(n);g=grade(n,task)
            assert type(step) is int
            for p in n.get('parents',[]):assert type(p) is int and p<step and p in steps
            # Full history enumeration (not incremental state of the first reader).
            checked.append(n)
            eligible=[x for x in checked if not x['is_buggy'] and type(x['metric_maximize']) is bool]
            directions={x['metric_maximize'] for x in eligible if x['metric'] is not None};assert len(directions)<=1
            ranked=sorted(eligible,key=lambda x:(x['metric'] is not None,
                (x['metric'] if x['metric_maximize'] else -x['metric']) if x['metric'] is not None else 0),reverse=True)
            pointer=ranked[0]['step'] if ranked else 0
            assert pointer==n['current_best_node']
            if step>0 and pointer==step and pointer!=last_pointer:
                old=grade(steps[last_pointer],task)
                if old is not None and g is not None:
                    counts['measurable_replacements']+=1
                    sign=-1 if task=='petfinder-pawpularity-score' else 1
                    counts['external_regressions_on_replacement']+=int(sign*(g-old)<0)
            last_pointer=pointer
            if not step:continue
            seconds=n['exec_time'];assert type(seconds) in (int,float) and math.isfinite(seconds) and seconds>=0
            full_time.append(seconds)
            if op=='debug':
                counts['debug_actions']+=1;counts['debug_finite_grade']+=int(g is not None);debug_time.append(seconds)
            else:
                counts['original_actions']+=1;counts['original_finite_grade']+=int(g is not None)
            root=n
            # Walk explicit raw parents rather than using a cached ancestry map.
            while category(root)=='debug':
                assert len(root['parents'])==1
                root=steps[root['parents'][0]]
            assert category(root) in ('draft','improve')
            lineages[root['step']].append(n)
        for root,chain in lineages.items():
            assert chain[0]['step']==root
            counts['observed_chains_with_debug']+=int(len(chain)>1)
            counts['observed_chains_first_ungraded_later_graded']+=int(grade(chain[0],task) is None and any(grade(x,task) is not None for x in chain[1:]))
            counts['observed_chains_last_still_ungraded']+=int(grade(chain[-1],task) is None)
        all_lineages.extend(lineages.values())
        final=steps[nodes[-1]['current_best_node']]
        ancestor=final
        while category(ancestor)=='debug':ancestor=steps[ancestor['parents'][0]]
        chosen_chain=next((c for c in lineages.values() if any(x is final for x in c)),[])
    assert final is not None
    fields=['original_actions','original_finite_grade','debug_actions','debug_finite_grade','measurable_replacements',
      'external_regressions_on_replacement','observed_chains_with_debug','observed_chains_first_ungraded_later_graded','observed_chains_last_still_ungraded']
    result={k:counts[k] for k in fields}
    result.update(events=len(events),restart_segments=len(segments),last_chosen_operator=category(final),
      last_chosen_step=final['step'],last_chosen_score=grade(final,task),execution_seconds=math.fsum(full_time),
      debug_execution_seconds=math.fsum(debug_time),chosen_has_finite_grade=grade(final,task) is not None,
      chosen_source_original_had_grade=grade(ancestor,task) is not None if ancestor['step'] else None,
      chosen_source_original_buggy=ancestor['is_buggy'] if ancestor['step'] else None,chosen_lineage_actions=len(chosen_chain))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    os.umask(0o077)
    if hasattr(signal,'SIGALRM'):
        signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(600)
    assert not args.output.exists()
    all_rows=[];sources=[]
    for filename,pin in PIN.items():
        archive=args.source/filename;assert digest(archive)==pin
        configs={};journals={};seen=set();expanded=0
        with tarfile.open(archive,'r|gz') as tf:
            for member in tf:
                p=PurePosixPath(member.name);assert not p.is_absolute() and '..' not in p.parts
                assert member.name not in seen;seen.add(member.name);expanded+=member.size
                assert len(seen)<=100000 and expanded<=4*1024**3
                if not member.isfile():continue
                if p.name not in ('dojo_config.json','JOURNAL.jsonl'):continue
                assert member.size<=64*1024**2
                raw=tf.extractfile(member).read()
                if BAD.search(raw) or KEY.search(raw):
                    matches=KEY.findall(raw)
                    env_refs=sum(bool(re.search(rb'\$\{oc\.env:[A-Z_][A-Z0-9_]*\}',x)) for x in matches)
                    print(json.dumps({'status':'SECURITY_SCHEMA_REVIEW','member_kind':p.name,
                        'forbidden_shape_hits':len(BAD.findall(raw)), 'sensitive_assignment_hits':len(matches),
                        'environment_reference_assignments':env_refs}),flush=True)
                    raise ValueError('credential first review')
                if p.name=='dojo_config.json':
                    configs[p.parent]=(json.loads(raw),hashlib.sha256(raw).hexdigest())
                else:journals[p]=(raw,hashlib.sha256(raw).hexdigest())
        assert len(configs)==len(journals)
        roots_seen=set()
        for path,(raw,jsha) in journals.items():
            roots=[r for r in configs if r in path.parents];assert len(roots)==1
            root=roots[0];assert root not in roots_seen;roots_seen.add(root)
            config,csha=configs[root];identity=hashlib.sha256(str(root).encode()).hexdigest()
            task=config['task']['name'];arm=root.parts[3];seed=config['metadata']['seed']
            assert not config['solver']['use_test_score']
            ee=[json.loads(x) for x in raw.splitlines() if x.strip()]
            row={'run_digest':identity,'task':task,'arm':arm,'seed':seed,**analyze(ee,task)}
            row.update(producer_commit=config['metadata']['git_commit_id'],nominal_seconds=config['solver']['time_limit_secs'],
                candidate_timeout_seconds=config['solver']['execution_timeout'],archive_sha256=pin,config_sha256=csha,journal_sha256=jsha,
                endpoint='last_logged_native_choice_not_certified_final',seed_is_common_randomness_proof=False)
            all_rows.append(row);sources.append({'run_digest':identity,'journal_sha256':jsha,'config_sha256':csha})
    assert len(all_rows)==len({r['run_digest'] for r in all_rows})==39
    args.output.mkdir()
    with (args.output/'per_run.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(all_rows[0]));writer.writeheader();writer.writerows(all_rows)
    result={'status':'INDEPENDENT_RAW_EXTRACTION_COMPLETE_COMPARISON_PENDING','run_directories':len(all_rows),
        'segments':sum(r['restart_segments'] for r in all_rows),'events':sum(r['events'] for r in all_rows),
        'reader_sha256':digest(Path(__file__)),
        'rows':all_rows,'sources':sources,'limitations':['Same immutable observational cohort; not new efficacy evidence.',
            'Does not certify completion, physical independence across run directories, same hardware or same actual budget.']}
    (args.output/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','sources')}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        import traceback
        print(json.dumps({'status':'FAILED_CLOSED','type':type(exc).__name__,'frames':[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)]}))
        raise SystemExit(2)
