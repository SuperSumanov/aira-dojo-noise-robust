"""Independent streaming ID-to-pixel verifier, run only after frozen readout.

No task runtime or production scorer imports; no candidate execution or fitting.
The underlying task/data are the same, so this is not independent replication.
"""
import argparse,csv,hashlib,json,math,time
from pathlib import Path
import numpy as np
from PIL import Image

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read(p):return json.loads(Path(p).read_text())

def independent_score(view,submission):
    m=read(view/'manifest.json');reference={};seen={};total=0
    for name in m['query_ids']:
        p=view/'search-reference'/name
        assert digest(p)==m['search_reference_files'][name]
        a=np.array(Image.open(p).convert('L'),dtype=np.uint8)
        key=str(int(Path(name).stem));assert key not in reference
        reference[key]=a;seen[key]=np.zeros(a.shape,dtype=bool);total+=a.size
    chunks=[];partial=[];rows=0
    with submission.open(newline='') as f:
        r=csv.reader(f);assert next(r)==['id','value']
        for row in r:
            assert len(row)==2
            image,y,x=row[0].split('_');y,x=int(y)-1,int(x)-1
            a=reference[image];assert 0<=y<a.shape[0] and 0<=x<a.shape[1]
            assert not seen[image][y,x];seen[image][y,x]=True
            value=float(row[1]);assert math.isfinite(value) and 0<=value<=1
            d=float(a[y,x])/255-value;partial.append(d*d);rows+=1
            if len(partial)==65536:chunks.append(math.fsum(partial));partial=[]
    if partial:chunks.append(math.fsum(partial))
    assert rows==total and all(a.all() for a in seen.values())
    return math.sqrt(math.fsum(chunks)/total),rows

def verify(root,readout,out):
    start=time.monotonic();root,readout,out=map(Path,(root,readout,out))
    assert not out.exists()
    p,closed,rows,summary=[read(q) for q in (root/'plan.json',root/'closed.json',readout/'runs.json',readout/'summary.json')]
    assert len(rows)==len(p['schedule'])==16
    assert summary['plan_sha256']==digest(root/'plan.json')
    assert summary['source_commit']==p['source_commit']
    assert all(all(r[k]==s[k] for k in ('index','mode','fold','seed','program')) for r,s in zip(rows,p['schedule']))
    differences=[];counts=[]
    for row in rows:
        if row['score'] is None:continue
        pred=root/f"episode-{row['index']}/prediction.private.csv"
        assert digest(pred)==row['prediction_sha256']
        val,n=independent_score(Path(p['views'][row['fold']]['view']),pred)
        differences.append(abs(val-row['score']));counts.append(n)
        assert abs(val-row['score'])<1e-12
    cells=[]
    for fold in (0,1):
        for seed in (5221,5222):
            cell=[r for r in rows if r['fold']==fold and r['seed']==seed]
            ready=len(cell)==4 and len({r['mode'] for r in cell})==4 and all(r['qualified'] for r in cell)
            v={r['mode']:r['score'] for r in cell} if ready else {}
            passed=bool(ready and min(v[k]-v['multiscale'] for k in ('cnn0','cnn1','patch'))>=.001)
            cells.append(dict(fold=fold,seed=seed,qualified=ready,pass_gate=passed))
    structure=bool(not closed['error'] and closed['cleanup_verified'] and len(closed['records'])==16 and all(r['qualified'] for r in rows))
    assert structure==summary['structure']
    assert bool(structure and all(c['pass_gate'] for c in cells))==summary['opportunity_gate']
    assert summary['complete']==sum(r['complete'] for r in rows)
    assert summary['qualified']==sum(r['qualified'] for r in rows)
    assert math.isclose(summary['gpu_hours'],summary['gpu_seconds']/3600,abs_tol=1e-12)
    result=dict(independent_streaming_score_verified=True,planned=16,recomputed=len(differences),
        maximum_score_difference=max(differences,default=None),pixel_counts=counts,
        cells=cells,opportunity_gate=summary['opportunity_gate'],
        summary_sha256=digest(readout/'summary.json'),runs_sha256=digest(readout/'runs.json'),
        verifier_sha256=digest(__file__),seconds=time.monotonic()-start,
        limit='Independent ID/pixel/SSE implementation and arithmetic, not independent data or repetitions; runtime qualification rests on recorded receipts.')
    with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))

def selftest():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='page-score-test-') as directory:
        root=Path(directory);(root/'search-reference').mkdir()
        Image.fromarray(np.array([[0,255],[128,64]],dtype=np.uint8)).save(root/'search-reference/1.png')
        (root/'manifest.json').write_text(json.dumps(dict(query_ids=['1.png'],search_reference_files={'1.png':digest(root/'search-reference/1.png')})))
        pred=root/'prediction.csv'
        good=[['1_2_2',64/255],['1_1_1',0],['1_2_1',128/255],['1_1_2',1]]
        def save(rows):
            with pred.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['id','value']);w.writerows(rows)
        save(good);assert independent_score(root,pred)==(0.,4)
        rejected=0
        for bad in (good[:-1],good+[good[0]],good[:-1]+[['1_1_2',float('nan')]],good[:-1]+[['1_3_2',1]]):
            save(bad)
            try:independent_score(root,pred)
            except (AssertionError,KeyError):rejected+=1
        assert rejected==4
    print(json.dumps(dict(shuffled_ids_supported=True,synthetic_exact_score=0,invalid_cases_rejected=4)))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root',nargs='?');a.add_argument('readout',nargs='?');a.add_argument('out',nargs='?');a.add_argument('--selftest',action='store_true');x=a.parse_args()
    if x.selftest:selftest()
    else:verify(x.root,x.readout,x.out)
