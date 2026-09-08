"""Bounded CPU diagnostic on the already projected 84 historical runs only."""
import collections, datetime, hashlib, itertools, json, os, re, signal, subprocess, sys, time
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
C = '5d9feb7435cc3bc9d4765b1d4f67d49337e7a303'
O = B/'historical-input-observability-5d9feb7-r2-20260908'
P = B/'historical-program-pack-f702ba2-r2-20260907'
MANIFEST = '0912a2e6cf8342fe6c209645d2d1b56c142f91a066197fcd5e37d07f8c0955e7'
MODEL = B/'cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1'
FILES = {'config.json': '1bb33a92c3548fbc68b889b490e810440435253598835bd71dff0396060c12db',
 'merges.txt': '8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5',
 'tokenizer.json': 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539',
 'tokenizer_config.json': '3c04ed3ca964ea2f6b2b5faf0dc4d31aec1cb1e8b4bcf63f402d295046b422b5',
 'vocab.json': 'ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910'}
NAMES = ['phase1/historical_encoding_observability.py', 'phase1/tests/test_historical_encoding_observability.py',
         'phase1/g_reuse_endpoint_inference.py']
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name, value):
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()
    assert not SECRET.search(raw)
    p = O/name
    with p.open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    p.chmod(0o400)


def read(p, digest, cap):
    assert p.is_absolute() and '..' not in p.parts and p.resolve()==p and p.is_file() and not p.is_symlink()
    s=p.stat(); assert s.st_size<=cap and not s.st_mode&0o222 and s.st_uid==os.getuid() and s.st_nlink==1
    raw=p.read_bytes(); z=p.stat()
    assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns)
    assert hashlib.sha256(raw).hexdigest()==digest and not SECRET.search(raw)
    return raw


def main():
    signal.alarm(1200); start=time.monotonic(); os.umask(0o077)
    assert not O.exists(); O.mkdir(); source=O/'source'; source.mkdir()
    os.environ.update(PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false',
                      USE_TORCH='0', USE_TF='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    hashes={}
    for name in NAMES:
        raw=subprocess.check_output(['git','-C',str(B/'aira-dojo'),'show',C+':'+name],timeout=30)
        p=source/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(raw); hashes[name]=sha(p)
    env=dict(os.environ,PYTHONPATH=str(source))
    test=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',NAMES[1]],
        cwd=source,env=env,capture_output=True,timeout=90)
    assert not SECRET.search(test.stdout+test.stderr)
    (O/'tests.log').write_bytes(test.stdout+test.stderr)
    assert test.returncode==0 and b'13 passed' in test.stdout
    save('INTENT.json',dict(source_commit=C,source_hashes=hashes,manifest_sha256=MANIFEST,
         tokenizer_hashes=FILES,scope_runs=84,limits=[2048,8192,16384],cpu_timeout_seconds=1200,
         protected_reads=False,labels_read=False,model_weights_loaded=False,helper_sha256=sha(Path(__file__))))
    # The pre-existing private manifest is 0600, while program files are 0400.
    # Preserve it; pin a new immutable copy instead of changing its permissions.
    original_manifest=P/'A-pack.private.json'
    assert original_manifest.resolve()==original_manifest and not original_manifest.is_symlink()
    s=original_manifest.stat()
    assert original_manifest.is_file() and s.st_mode&0o777==0o600 and s.st_uid==os.getuid() and s.st_nlink==1 and s.st_size<16*2**20
    raw_manifest=original_manifest.read_bytes(); z=original_manifest.stat()
    assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns)
    assert hashlib.sha256(raw_manifest).hexdigest()==MANIFEST and not SECRET.search(raw_manifest)
    copy=O/'pack.private.json'
    with copy.open('xb') as f: f.write(raw_manifest); f.flush(); os.fsync(f.fileno())
    copy.chmod(0o400)
    pack=json.loads(read(copy,MANIFEST,16*2**20))
    assert len(pack)==84
    for name,h in FILES.items(): assert sha(MODEL/name)==h
    sys.path.insert(0,str(source))
    from phase1.historical_encoding_observability import summarize,truncate
    from phase1.g_reuse_endpoint_inference import encode_endpoints
    from transformers import AutoTokenizer
    import tokenizers,transformers
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=False,use_fast=True)
    assert tokenizer.is_fast
    runs=[]; code_bytes=0; parity_checks=0; verified_files={}
    for rid, r in sorted(pack.items()):
        nodes=[]
        assert r['source_admitted'] is False
        for n in r['nodes']:
            if not n['nonempty_code']: continue
            rel=Path(n['relative_code_path']); assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[0]=='programs'
            p=P/rel
            raw=read(p,n['code_sha256'],4*2**20); code_bytes+=len(raw); assert code_bytes<=128*2**20
            assert len(raw)==n['code_bytes']; code=raw.decode('utf-8'); verified_files[p]=n['code_sha256']
            text=f"# MLE-bench task: {r['task']}\n"+code
            ids=tuple(tokenizer(text,add_special_tokens=False)['input_ids'])
            actual=encode_endpoints([dict(endpoint_id='diagnostic',task_name=r['task'],code=code)],tokenizer,max_len=16384)[0].input_ids
            assert actual==truncate(ids,16384); parity_checks+=1
            nodes.append(dict(step=n['step'],parents=n['parents'],code_sha=n['code_sha256'],tokens=ids))
        runs.append(dict(task=r['task'],component=r['component_sha256'],nodes=nodes))
    result=summarize(runs)
    assert result['programs']==3447 and result['byte_distinct_sibling_pairs']==1579
    # Independent aggregation: group by parent set, position-mask truncation,
    # compare direct token arrays, not producer truncation or pair-selection loop.
    independent_checks=0
    for row in result['contexts']:
        lim=row['max_len']; bytask=collections.defaultdict(list); families=[]
        for r in runs:
            bytask[r['task']].extend(r['nodes']); grouped=collections.defaultdict(list)
            for n in r['nodes']:
                if n['parents']: grouped[tuple(sorted(n['parents']))].append(n)
            for group in grouped.values():
                families.extend((r['task'],a,b) for a,b in itertools.combinations(group,2) if a['code_sha']!=b['code_sha'])
        def masked(ids):
            return tuple(x for i,x in enumerate(ids) if len(ids)<=lim or i<lim//4 or i>=len(ids)-(lim-lim//4))
        aggregate=[]
        for task,nodes in sorted(bytask.items()):
            pairs=[(a,b) for t,a,b in families if t==task]
            lens=[len(n['tokens']) for n in nodes]
            q=dict(task=task,programs=len(nodes),truncated_programs=sum(x>lim for x in lens),full_tokens=sum(lens),
                   retained_tokens=sum(min(x,lim) for x in lens),byte_distinct_sibling_pairs=len(pairs),
                   encoded_equal_sibling_pairs=sum(masked(a['tokens'])==masked(b['tokens']) for a,b in pairs),
                   truncation_induced_equal_pairs=sum(a['tokens']!=b['tokens'] and masked(a['tokens'])==masked(b['tokens']) for a,b in pairs))
            q['truncated_program_fraction']=q['truncated_programs']/q['programs']
            q['retained_token_fraction']=q['retained_tokens']/q['full_tokens']
            aggregate.append(q)
        assert aggregate==row['task_counts']; independent_checks+=1
        for key in ('programs','truncated_programs','full_tokens','retained_tokens','byte_distinct_sibling_pairs','encoded_equal_sibling_pairs','truncation_induced_equal_pairs'):
            assert sum(t[key] for t in aggregate)==row[key]
    assert all(sha(p)==h for p,h in verified_files.items()) and sha(P/'A-pack.private.json')==MANIFEST
    assert all(sha(MODEL/name)==h for name,h in FILES.items()) and all(sha(source/n)==h for n,h in hashes.items())
    result.update(source_commit=C,source_manifest_sha256=MANIFEST,tokenizer_hashes=FILES,
                  existing_encoder_parity_checks=parity_checks,independent_context_recomputations=independent_checks,
                  code_bytes_read=code_bytes,cpu_tests_passed=13,versions=dict(transformers=transformers.__version__,tokenizers=tokenizers.__version__),
                  helper_sha256=sha(Path(__file__)),seconds=time.monotonic()-start,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    save('SUMMARY.json',result)
    save('VERIFIED.json',dict(summary_sha256=sha(O/'SUMMARY.json'),intent_sha256=sha(O/'INTENT.json'),
         all_code_hashes_rechecked=True,source_and_tokenizer_rechecked=True,independent_contexts=independent_checks))
    print(json.dumps(dict(status='HISTORICAL_OBSERVABILITY_COMPLETE',summary_sha256=sha(O/'SUMMARY.json'),
           programs=result['programs'],runs=result['runs'],contexts=[{k:v for k,v in x.items() if k!='task_counts'} for x in result['contexts']],
           seconds=result['seconds']),sort_keys=True))


try: main()
except Exception as exc:
    import traceback
    locations=[dict(file=Path(t.filename).name,line=t.lineno) for t in traceback.extract_tb(exc.__traceback__)]
    if O.is_dir() and not (O/'FAILED.json').exists():
        save('FAILED.json',dict(error_type=type(exc).__name__,detail_sha256=hashlib.sha256(str(exc).encode()).hexdigest(),
             locations=locations,labels_read=False,model_fit_started=False))
    print(json.dumps(dict(status='HISTORICAL_DIAGNOSTIC_FAILED_CLOSED',error_type=type(exc).__name__,locations=locations)))
    raise SystemExit(1)
