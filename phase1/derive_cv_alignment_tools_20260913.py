"""One-program measurement diagnostic using the already executed native adapter."""
import json
from pathlib import Path
import sys
from derive_branching_completion_20260913 import once


def main(output):
    base=Path(__file__).parent/'releases/forets-reference-completion-tools-20260913-v2'
    source=(base/'forets_pool_completion_20260912.py').read_text()
    a=source.index('def prepare(commit):');b=source.index('\n\ndef checked(root):',a)
    source=source[:a]+"def prepare(commit):\n    from forets_cv_alignment_contract_20260913 import prepare as diagnostic_prepare\n    diagnostic_prepare(commit,globals())\n"+source[b:]
    for old,new in [("len(p['rows'])!=9","len(p['rows'])!=1"),('range(9)','range(1)'),
                    ('planned=9,completed=len(done)','planned=1,completed=len(done)'),('complete=len(done)==9','complete=len(done)==1'),
                    ("device_label='original_unedited_candidate_choice'","device_label='same_fit_cv_alignment_diagnostic'")]:source=once(source,old,new)
    source=source[source.index('import argparse'):]
    launcher=(base/'forets_pool_completion_20260912.sbatch').read_text()
    for old,new in [('forets-reference-completion','forets-cv-alignment'),('01:30:00','00:15:00'),('01:28:00','00:13:00'),('5200s','700s')]:launcher=once(launcher,old,new)
    compile(source,'cv_native_worker','exec');output.mkdir(exist_ok=False)
    (output/'forets_pool_completion_20260912.py').write_text(source,encoding='utf-8',newline='\n')
    (output/'forets_pool_completion_20260912.sbatch').write_text(launcher,encoding='utf-8',newline='\n')
    print(json.dumps(dict(programs=1,maximum_gpu_hours=.25,output=str(output))))


if __name__=='__main__':main(Path(sys.argv[1]))
