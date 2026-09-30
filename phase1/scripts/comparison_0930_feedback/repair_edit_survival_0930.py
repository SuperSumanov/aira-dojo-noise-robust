"""Fixed exploratory syntax-survival census. NOT a goal-fulfilment detector.

Unit: each recorded Improve origin followed by one or more Debug nodes.
An endpoint is first observed finite-grade repair and last logged repair.
No grade values are used/exported, no method selection, no candidate execution.
"""
import argparse,ast,collections,hashlib,json,math,os,signal,tarfile
from pathlib import Path,PurePosixPath
from independent_raw_comparison_0930 import BAD,KEY,PIN,category,digest

def finite_grade(n):
    return n.get('metric_info/valid_submission')==1 and type(n.get('metric_info/score')) in (int,float) and math.isfinite(n['metric_info/score'])

def fingerprint(code):
    tree=ast.parse(code)
    # Ignore locations and comments; retain names, literal values, all statements.
    normalized=ast.dump(tree,include_attributes=False)
    call_targets={ast.dump(n.func,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    # Complete Call expressions include parameters: descriptive, not semantic equivalence.
    calls={ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call)}
    imports=set()
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):imports.add(ast.dump(n,include_attributes=False))
    return {'normalized':normalized,'call_targets':call_targets,'calls':calls,'imports':imports}

def comparison(parent,original,repaired):
    row={'exact_ast_revert_to_parent':repaired['normalized']==parent['normalized'],
         'exact_ast_unchanged_from_origin':repaired['normalized']==original['normalized']}
    for field in ('call_targets','calls','imports'):
        novel=original[field]-parent[field]
        row['novel_'+field]=len(novel)
        row['retained_'+field]=len(novel & repaired[field])
        row['new_repair_'+field]=len(repaired[field]-original[field]-parent[field])
    return row

def analyze(nodes,run_digest,task,arm,seed):
    segments=[]
    for n in nodes:
        if n['step']==0:segments.append([])
        assert segments
        segments[-1].append(n)
    output=[];parse_failures=0;parsed=0;origins=0
    for segment,ns in enumerate(segments,1):
        index={n['step']:n for n in ns};fps={};chains=collections.defaultdict(list)
        assert len(index)==len(ns)
        for n in ns:
            if not n['step']:continue
            try:fps[n['step']]=fingerprint(n['code']);parsed+=1
            except SyntaxError:parse_failures+=1
            root=n
            while category(root)=='debug':
                assert len(root['parents'])==1 and root['parents'][0]<root['step']
                root=index[root['parents'][0]]
            assert category(root) in ('draft','improve')
            chains[root['step']].append(n)
        for root_step,chain in chains.items():
            root=index[root_step]
            if category(root)!='improve' or len(chain)<=1:continue
            origins+=1
            assert len(root['parents'])==1
            parent_step=root['parents'][0]
            assert parent_step<root_step and parent_step in index
            endpoints={'last_logged_debug':chain[-1]}
            first=next((n for n in chain[1:] if finite_grade(n)),None)
            if first is not None:endpoints['first_finite_grade_debug']=first
            for endpoint,n in endpoints.items():
                base={'run_digest':run_digest,'task':task,'arm':arm,'seed':seed,'segment':segment,
                   'origin_step':root_step,'parent_step':parent_step,'endpoint_step':n['step'],
                   'endpoint':endpoint,'origin_finite_grade':finite_grade(root),
                   'endpoint_finite_grade':finite_grade(n),'chain_debug_actions':len(chain)-1,
                   'usable_ast':all(s in fps for s in (parent_step,root_step,n['step']))}
                if base['usable_ast']:base.update(comparison(fps[parent_step],fps[root_step],fps[n['step']]))
                output.append(base)
    return output,{'parsed':parsed,'parse_failures':parse_failures,'improve_debug_origins':origins}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()));signal.alarm(600)
    assert not a.output.exists();rows=[];stats=collections.Counter();provenance=[]
    for archive,pin in PIN.items():
        p=a.source/archive;assert digest(p)==pin
        configs={};journals={};seen=set();expanded=0
        with tarfile.open(p,'r|gz') as tf:
            for m in tf:
                path=PurePosixPath(m.name)
                assert not path.is_absolute() and '..' not in path.parts and m.name not in seen
                seen.add(m.name);expanded+=m.size;assert len(seen)<=100000 and expanded<=4*1024**3
                if not m.isfile() or path.name not in ('dojo_config.json','JOURNAL.jsonl'):continue
                assert m.size<=64*1024**2
                raw=tf.extractfile(m).read();assert not BAD.search(raw) and not KEY.search(raw)
                if path.name=='dojo_config.json':configs[path.parent]=(json.loads(raw),hashlib.sha256(raw).hexdigest())
                else:journals[path]=(raw,hashlib.sha256(raw).hexdigest())
        assert len(configs)==len(journals)
        for path,(raw,jsha) in journals.items():
            roots=[r for r in configs if r in path.parents];assert len(roots)==1
            root=roots[0];cfg,csha=configs[root];rd=hashlib.sha256(str(root).encode()).hexdigest()
            rr,ss=analyze([json.loads(x)['data'] for x in raw.splitlines() if x.strip()],rd,cfg['task']['name'],root.parts[3],cfg['metadata']['seed'])
            rows.extend(rr);stats.update(ss);stats['run_directories']+=1
            provenance.append({'run_digest':rd,'archive_sha256':pin,'config_sha256':csha,'journal_sha256':jsha})
    a.output.mkdir()
    result={'status':'EXPLORATORY_SYNTAX_CENSUS','statistics':dict(stats),'rows':rows,'sources':provenance,
       'script_sha256':digest(Path(__file__)),'not_claimed':['Semantic goal loss','Repair causal effect','Budget savings','New independent evidence of model benefit']}
    (a.output/'syntax_survival.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({'status':result['status'],'statistics':result['statistics'],'endpoint_rows':len(rows)}))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        import traceback
        print(json.dumps({'status':'FAILED_CLOSED','type':type(exc).__name__,'frames':[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)]}))
        raise SystemExit(2)
