"""Reuse the executed nine-program-compatible adapter; preserve all attempted code."""
import hashlib
import json
from pathlib import Path
import sys
from derive_branching_completion_20260913 import once


def derive(output):
    base=Path(__file__).parent
    original=(base/'releases/forets-branching-completion-tools-20260913/forets_pool_completion_20260912.py').read_text()
    text=original
    changes=[
      ("PARENT=BASE/'forets-wallclock-20260912-y_p2tlmi'","PARENT=BASE/'forets-wallclock-20260912-5_czzimk'"),
      ("TREE='35321718fef54f1907b469ab44334a30fe66b6cd'","TREE='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'"),
      ("SUMMARY='59d9463c127aa0c9fc10d1ab95a09af287e6650c708078330e20edc69f60c2d1'","SUMMARY='4d89d47dd47877c04ceebeb24adc6a7773f13cfbe3bdc65517eef878b933d11e'"),
      ("if set(old)!=set(selected) or len(old)!=2:","if len(selected)!=2 or not set(old).issubset(selected) or len(old) not in (1,2):"),
      ("summary['seeds']!=[30,31]","summary['seeds']!=[32,33]"),
      ("for s in (30,31)","for s in (32,33)"),
      ("done['observed_task_outcomes'] is not False","done['observed_candidate_outcomes'] is not False"),
      ("if set(omitted)!=set(d['selected']) or len(omitted)!=2:","if not set(omitted).issubset(d['selected']) or len(omitted) not in (1,2):"),
      ("if len(rows)!=8:raise ValueError('fixed eight unattempted codes')","if len(rows)!=9:raise ValueError('fixed nine unattempted codes')"),
      ("len(p['rows'])!=8","len(p['rows'])!=9"),
      ("for i in range(8)","for i in range(9)"),
      ("planned=8,completed=len(done)","planned=9,completed=len(done)"),
      ("complete=len(done)==8","complete=len(done)==9"),
      ("FORETS_BRANCHING_COMPLETION_PLAN_20260913.md","FORETS_REFERENCE_COMPLETION_PLAN_20260913.md")]
    for old,new in changes:text=once(text,old,new)
    reader=(base/'readout_branching_completion_20260913.py').read_text()
    reader=once(reader,"PARENT=BASE/'forets-wallclock-20260912-y_p2tlmi'","PARENT=BASE/'forets-wallclock-20260912-5_czzimk'")
    reader=once(reader,"done['planned']!=8","done['planned']!=9")
    reader=once(reader,"planned=8,attempted=done['completed']","planned=9,attempted=done['completed']")
    launcher=(base/'releases/forets-branching-completion-tools-20260913/forets_pool_completion_20260912.sbatch').read_text()
    launcher=once(launcher,'--job-name=forets-branching-completion','--job-name=forets-reference-completion')
    compile(text,'reference_completion_worker','exec');compile(reader,'reference_completion_reader','exec')
    output.mkdir(exist_ok=False)
    for name,data in [('forets_pool_completion_20260912.py',text),('readout_reference_completion_20260913.py',reader),
                      ('forets_pool_completion_20260912.sbatch',launcher)]:
        (output/name).write_text(data,encoding='utf-8',newline='\n')
    proof=dict(base_sha256=hashlib.sha256(original.encode()).hexdigest(),changes=changes,
        files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()})
    (output/'derivation.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(proof['files']))


if __name__=='__main__':derive(Path(sys.argv[1]))
