"""Mechanical derivation of the previously executed native completion adapter."""
import hashlib
import json
from pathlib import Path
import sys

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('exact completion derivation anchor: '+old[:70])
    return text.replace(old,new,1)

def derive(output):
    output.mkdir(exist_ok=False)
    original=Path(__file__).with_name('forets_pool_completion_20260912.py').read_text()
    text=original
    pairs=[
      ("PARENT=BASE/'forets-wallclock-20260912-cxb9p0og'","PARENT=BASE/'forets-wallclock-20260912-y_p2tlmi'"),
      ("TREE='e07cb8c61bca347c61bb8253c84eda826b1add6a'","TREE='35321718fef54f1907b469ab44334a30fe66b6cd'"),
      ("SUMMARY='a127831408688b545e3d666b790fe1f75b65e82f9324d21c8c4cfc0243d39e90'","SUMMARY='59d9463c127aa0c9fc10d1ab95a09af287e6650c708078330e20edc69f60c2d1'"),
      ("if old!=selected or len(old)!=1:","if set(old)!=set(selected) or len(old)!=2:"),
      ("PARENT/'recovery-readout-finished.json'","PARENT/'readout-finished.json'"),
      ("receipt['summary_sha256']!=SUMMARY","receipt['files']['wallclock-summary.json']!=SUMMARY"),
      ("if len(summary['rows'])!=8 or summary['job']!='13156':","if len(summary['rows'])!=8 or summary['seeds']!=[30,31]:"),
      ("path.name=='batch-1.sqlite'","path.name=='batch-2.sqlite'"),
      ("for s in (24,25)","for s in (30,31)"),
      ("rankdir=cp/'forets-contextual-judge-private/batch-1'","rankdir=cp/'forets-contextual-judge-private/batch-2'"),
      ("d['binding']['step']!=1","d['binding']['step']!=2"),
      ("('input.json','finished.json','rank-0.json','rank-1.json','response-0.json','response-1.json','request-0.json','request-1.json')",
       "('input.json','finished.json','rank-0.json','response-0.json','request-0.json')"),
      ("if omitted!=d['selected'] or len(omitted)!=1:","if set(omitted)!=set(d['selected']) or len(omitted)!=2:"),
      ("if len(rows)!=12:raise ValueError('fixed twelve unattempted codes')","if len(rows)!=8:raise ValueError('fixed eight unattempted codes')"),
      ("or len(p['rows'])!=12:","or len(p['rows'])!=8:"),
      ("for i in range(12)","for i in range(8)"),
      ("planned=12,completed=len(done)","planned=8,completed=len(done)"),
      ("complete=len(done)==12", "complete=len(done)==8"),
      ("FORETS_POOL_COMPLETION_PLAN_20260912.md","FORETS_BRANCHING_COMPLETION_PLAN_20260913.md")]
    for old,new in pairs:text=once(text,old,new)
    compile(text,'derived_completion','exec')
    (output/'forets_pool_completion_20260912.py').write_text(text,encoding='utf-8',newline='\n')
    launcher=Path(__file__).with_name('forets_pool_completion_20260912.sbatch').read_text()
    launcher=once(launcher,'#SBATCH --job-name=forets-pool-completion','#SBATCH --job-name=forets-branching-completion')
    (output/'forets_pool_completion_20260912.sbatch').write_text(launcher,encoding='utf-8',newline='\n')
    proof=dict(base_sha256=hashlib.sha256(original.encode()).hexdigest(),
        derived_sha256=hashlib.sha256(text.encode()).hexdigest(),changes=pairs,
        role='same native execution adapter; eight unattempted first post-baseline candidates from all four closed critic pools')
    (output/'derivation.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in proof.items() if k!='changes'}))

if __name__=='__main__':derive(Path(sys.argv[1]))
