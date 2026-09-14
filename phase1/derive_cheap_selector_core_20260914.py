"""Mechanical derivation before new execution; original reader unchanged."""
import argparse,re
from pathlib import Path
from forets_environment_build_20260912 import write,encode,sha
def main(out):
    p=Path(__file__).parent/'releases/forets-edit-scope-tools-20260914-v2/readout_edit_scope_core_20260914.py'
    text=p.read_text()
    for a,b in [("ARMS=('whole_program','model_module')","ARMS=('uniform','short_code','learned_validity')"),('(42,43,44,45)','(46,47)'),('len(rows)!=16','len(rows)!=12'),('sixteen exact edit-scope rows','twelve exact cheap-selector rows'),('selection_top_k=2','selection_top_k=1'),('Two tasks/four new seeds; edit scope comparison. Same refactored start.','Two tasks/two new seeds; three cheap selectors with one common fresh-container backend. Same refactored start.')]:
        if a not in text:raise ValueError('core anchor: '+a)
        text=text.replace(a,b)
    text=re.sub(r'\b1200\b','600',text)
    text=text.replace("                reason='api_admission_budget_expired'","                reason='api_admission_budget_expired'\n            elif tail.rstrip().endswith(b'RunBudgetError: run adapter-attempt budget exhausted'):\n                reason='adapter_attempt_budget_expired'")
    text=text.replace("('completed','timed_out','api_admission_budget_expired')","('completed','timed_out','api_admission_budget_expired','adapter_attempt_budget_expired')")
    compile(text,'<new frozen core>','exec');out.mkdir(exist_ok=False)
    h=write(out/'readout_cheap_selector_core_20260914.py',text.encode())
    print(encode(dict(source_sha256=sha(p.read_bytes()),derived_sha256=h)).decode())
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('output',type=Path);main(p.parse_args().output)
