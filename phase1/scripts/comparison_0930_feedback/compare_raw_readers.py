"""Recheck the full field agreement of the two independent raw readers."""
import argparse,hashlib,json,math,platform,sys
from pathlib import Path

def check(old,new,sources):
    assert len(old)==len(new)==len(sources)==39
    a={r['run_digest']:r for r in old};b={r['run_digest']:r for r in new};c={r['run_digest']:r for r in sources}
    assert len(a)==len(b)==len(c)==39 and a.keys()==b.keys()==c.keys()
    fields=0
    for identity,row in a.items():
        for key,value in row.items():
            other=b[identity][key]
            if type(value) in (int,float) and type(other) in (int,float):
                assert math.isclose(value,other,rel_tol=1e-12,abs_tol=1e-8),(identity,key)
            else:assert type(value) is type(other) and value==other,(identity,key)
            fields+=1
        for key in ('producer_commit','archive_sha256','config_sha256','journal_sha256'):
            assert b[identity][key]==c[identity][key],(identity,key)
            fields+=1
    return fields

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args()
    names=['original_per_run.json','independent_raw_receipt.json','rows.json']
    raw={n:(a.input/n).read_bytes() for n in names};o,n,s=[json.loads(raw[name]) for name in names]
    fields=check(o,n['rows'],s)
    receipt={'status':'PASS','run_directories':len(o),'field_comparisons':fields,'events':sum(r['events'] for r in n['rows']),
      'segments':sum(r['restart_segments'] for r in n['rows']),'input_sha256':{name:hashlib.sha256(x).hexdigest() for name,x in raw.items()},
      'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'python':sys.version,'platform':platform.platform(),
      'boundary':'Two separate raw-archive extraction implementations agree; not new samples or efficacy evidence.'}
    if a.output:
        with a.output.open('x') as f:json.dump(receipt,f,indent=2,allow_nan=False)
    print(json.dumps(receipt))

if __name__=='__main__':main()
