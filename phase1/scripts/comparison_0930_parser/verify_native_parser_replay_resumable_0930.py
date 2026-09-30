"""Actual pinned old/new extraction + independent inline-shielding verification.

No model call, no execution of candidate programs, no score fields read.
The independent route temporarily shields inline Markdown fence tokens, uses
the original native regex extractor, then restores tokens before AST comparison.
Only hashes/counters leave the process; source and response remain remote.
"""
import argparse,ast,collections,hashlib,importlib.util,json,re,signal,sys,tarfile,time
from pathlib import Path,PurePosixPath
from independent_raw_comparison_0930 import PIN,BAD,KEY,digest
from compiler_feedback_census_0930 import terminal,GENERIC

ROOT=Path('/tmp/mle-progress-20260930-NRPr0f')
PKG=ROOT/'parser-fix-e385-20261001'
DATA=ROOT/'comparison-0930'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

def canonical(s):return ast.dump(ast.parse(s),include_attributes=False)

def main():
    global ROOT, PKG, DATA
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT)
    ap.add_argument('--bundle',type=Path);ap.add_argument('--source',type=Path)
    a=ap.parse_args();ROOT=a.root;PKG=a.bundle or ROOT/'parser-fix-e385-20261001';DATA=a.source or ROOT/'comparison-0930'
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(1800)
    helper=load('dojo.utils.python_code_blocks',PKG/'candidate/src/dojo/utils/python_code_blocks.py')
    old_op=load('old_operator_parser',PKG/'baseline/src/dojo/core/solvers/utils/response.py')
    old_task=load('old_task_parser',PKG/'baseline/src/dojo/utils/code_parsing.py')
    new_op=load('new_operator_parser',PKG/'candidate/src/dojo/core/solvers/utils/response.py')
    new_task=load('new_task_parser',PKG/'candidate/src/dojo/utils/code_parsing.py')
    import black
    sentinel='__INLINE_FENCE_SHIELD_20261001__';rows=[];counts=collections.Counter();sources=[]
    output_dir=DATA/'fence-native-resumable-v2';output_dir.mkdir(exist_ok=True)
    identity={'verifier_sha256':digest(Path(__file__)),
              'package_file_sha256':{str(p.relative_to(PKG)):digest(p) for p in PKG.rglob('*.py')},
              'python':sys.version,'black':black.__version__,'archives':PIN}
    identity_path=output_dir/'identity.json'
    if identity_path.exists():assert json.loads(identity_path.read_text())==identity
    else:
        with identity_path.open('x') as f:json.dump(identity,f,indent=2)
    progress=output_dir/'rows.jsonl';done={}
    if progress.exists():
        for line in progress.read_text().splitlines():
            r=json.loads(line);key=(r['run_digest'],r['segment'],r['step']);assert key not in done;done[key]=r
    started=time.monotonic()
    for name,pin in PIN.items():
        p=DATA/name;assert digest(p)==pin
        configs={};journals={}
        with tarfile.open(p,'r|gz') as tf:
            for m in tf:
                path=PurePosixPath(m.name)
                if not m.isfile() or path.name not in ('dojo_config.json','JOURNAL.jsonl'):continue
                assert m.size<64*1024**2
                raw=tf.extractfile(m).read();assert not BAD.search(raw) and not KEY.search(raw)
                if path.name=='dojo_config.json':configs[path.parent]=json.loads(raw)
                else:journals[path]=(raw,hashlib.sha256(raw).hexdigest())
        for path,(raw,jsha) in journals.items():
            roots=[r for r in configs if r in path.parents];assert len(roots)==1
            root=roots[0];cfg=configs[root];rd=hashlib.sha256(str(root).encode()).hexdigest();segment=0
            for line in raw.splitlines():
                n=json.loads(line)['data']
                if not n['step']:segment+=1;continue
                text=n['code'];generic=terminal(n)==GENERIC
                key=(rd,segment,n['step'])
                if key in done:
                    rows.append(done[key]);continue
                op_before=old_op.extract_code(text)
                try:task_before=old_task.extract_code(text);old_admitted=True
                except Exception as e:
                    assert str(e)=='Solution is not valid python code.'
                    task_before=None;old_admitted=False
                assert old_admitted!=generic
                op_after=new_op.extract_code(text);task_after=new_task.extract_code(op_after)
                assert op_after.strip() and canonical(op_after)==canonical(task_after)
                row={'run_digest':rd,'task':cfg['task']['name'],'arm':root.parts[3],'seed':cfg['metadata']['seed'],
                     'segment':segment,'step':n['step'],'old_admitted':old_admitted,
                     'new_admitted':True,'operator_task_ast_same':True}
                if old_admitted:
                    assert canonical(task_before)==canonical(task_after)==canonical(text)
                    counts['previously_admitted_ast_preserved']+=1
                    row['independent_mode']='native_old_and_raw_ast'
                else:
                    assert not op_before.strip() and sentinel not in text
                    protected=[];replacements=0
                    for source_line in text.splitlines(keepends=True):
                        if re.fullmatch(r'[ \t]*`{3,}(?:python)?[ \t]*(?:\r?\n)?',source_line):
                            protected.append(source_line)
                        else:
                            replacements+=source_line.count('```');protected.append(source_line.replace('```',sentinel))
                    assert replacements>0
                    shielded_result=old_op.extract_code(''.join(protected))
                    restored=shielded_result.replace(sentinel,'```')
                    assert restored.strip() and canonical(restored)==canonical(task_after)
                    counts['rejected_recovered_without_program_edit']+=1
                    counts['independent_shield_restore_ast_matches']+=1
                    row['independent_mode']='old_regex_shield_restore'
                    row['inline_fence_tokens_shielded']=replacements
                row['accepted_ast_sha256']=hashlib.sha256(canonical(task_after).encode()).hexdigest()
                rows.append(row);counts['actions']+=1
                with progress.open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
                if len(rows)%25==0:print(json.dumps({'verified_rows':len(rows),'elapsed_seconds':time.monotonic()-started}),flush=True)
            sources.append({'run_digest':rd,'archive_sha256':pin,'journal_sha256':jsha})
    assert len(rows)==983 and len({(r['run_digest'],r['segment'],r['step']) for r in rows})==983
    assert len(done)<=len(rows)
    counts=collections.Counter(actions=len(rows),
      previously_admitted_ast_preserved=sum(r['old_admitted'] for r in rows),
      rejected_recovered_without_program_edit=sum(not r['old_admitted'] for r in rows),
      independent_shield_restore_ast_matches=sum(r['independent_mode']=='old_regex_shield_restore' for r in rows))
    files={str(p.relative_to(PKG)):digest(p) for p in PKG.rglob('*.py')}
    result={'status':'PASS','counts':dict(counts),'rows':rows,'sources':sources,
       'source_reference_commit':'e385f863cb531904e611e987f7f71606796db656','package_file_sha256':files,
       'verifier_sha256':digest(Path(__file__)),'python':sys.version,'black':black.__version__,
       'verification_elapsed_seconds_not_runtime_benchmark':time.monotonic()-started,
       'boundary':'Parser admission and exact AST equivalence only. No new runtime/grade/E2E measurement.'}
    output=output_dir/'native_independent.json'
    with output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'status':result['status'],'counts':result['counts'],'sha256':digest(output)}))

if __name__=='__main__':
    try:main()
    except Exception as e:
        import traceback
        print(json.dumps({'status':'FAILED_CLOSED','type':type(e).__name__,
         'frames':[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(e.__traceback__)]}))
        raise SystemExit(2)
