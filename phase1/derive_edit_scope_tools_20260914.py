"""Mechanical derivation of frozen readers/checks; no experiment execution."""
import argparse
import re
from pathlib import Path
from forets_environment_build_20260912 import write, encode, sha
from forets_paid_patch_20260911 import once


def run(output):
    output.mkdir(exist_ok=False);base=Path(__file__).parent;old=base/'releases/forets-memory-tools-20260913'
    receipts={}
    def save(name,text,path):
        compile(text,name,'exec');write(output/name,text.encode())
        receipts[name]=dict(source=str(path.relative_to(base)),source_sha256=sha(path.read_bytes()),derived_sha256=sha(text.encode()))
    def common(text):
        for a,b in [('no_memory','whole_program'),('execution_memory','model_module'),('(40,41)','(42,43,44,45)'),
            ('len(rows)!=8','len(rows)!=16'),('planned_pairs=2','planned_pairs=4'),
            ('readout_memory_core_20260913','readout_edit_scope_core_20260914'),
            ('readout_forets_memory_control_20260913','readout_edit_scope_20260914'),
            ('memory_oriented_gain','module_oriented_gain'),('memory_minus_control_api_usd','module_minus_control_api_usd'),
            ('memory-summary.json','edit-scope-summary.json'),('memory-runs.csv','edit-scope-runs.csv')]:text=text.replace(a,b)
        return re.sub(r'\b600\b', '1200', text)
    path=old/'readout_memory_core_20260913.py';text=common(path.read_text())
    text=text.replace('eight exact width-control rows','sixteen exact edit-scope rows')
    text=text.replace('Two tasks/two new seeds, frozen error memory on vs off.', 'Two tasks/four new seeds; edit scope comparison. Same refactored start.')
    save('readout_edit_scope_core_20260914.py',text,path)
    path=old/'readout_forets_memory_control_20260913.py';text=common(path.read_text())
    # Remove the old memory-specific checks, not the underlying source/config/grade checks.
    text=text.replace('from forets_model_module_20260913 import TEXT_SHA,OPERATORS,HEADER\n','')
    text=text.replace(",'forets_model_module_20260913.py'", ",'forets_edit_scope_20260914.py'")
    start=text.index("        memory=read(root/'frozen-memory.json')")
    stop=text.index("        cp=Path(s['checkpoint_path'])",start)
    text=text[:start]+"        if s['edit_scope'] != r['arm']:raise ValueError('actual edit scope')\n"+text[stop:]
    text=text.replace("role='prior_error_memory_uniform_e2e_development'","role='edit_scope_uniform_1200_e2e_development'")
    text=text.replace('Four fresh task-seed pairs; only fixed prior-error prompt differs. Both generate and execute two. Prompt length differs as part of the intervention, actual token samples differ. No critic efficacy/new algorithm/scaling claim; failures not imputed.',
        'Eight fresh task-seed pairs. Same refactored RF start and 1200s budget; full-program vs model-module output/edit scope. Prompt/format/available editable space differ as the defined intervention. Not a critic/scaling or novel algorithm claim. Technical missingness not imputed.')
    text=text.replace('all eight distinct planned searches','all sixteen distinct planned searches')
    save('readout_edit_scope_20260914.py',text,path)
    path=base/'verify_forets_wallclock_20260912.py';text=path.read_text()
    text=once(text,'def run(root, blocks=(1,)):','def run(root, blocks=(1,2)):')
    for a,b in [('len(configs)!=8','len(configs)!=16'),("spec.launcher['worker_wall_seconds']!=600","spec.launcher['worker_wall_seconds']!=1200"),
        ("cfg['solver']['time_limit_secs']!=600","cfg['solver']['time_limit_secs']!=1200"),('actual_typed_configs=8','actual_typed_configs=16')]:text=once(text,a,b)
    save('verify_edit_scope_cutoff_20260914.py',text,path)
    path=old/'verify_memory_batch_20260913.py';text=common(path.read_text())
    text=text.replace('memory-batch-integration.json','edit-scope-batch-integration.json')
    save('verify_edit_scope_batch_20260914.py',text,path)
    path=old/'verify_memory_action_hook_20260913.py';text=path.read_text()
    text=once(text,'cda5e378046811fa20eadc7bc9a0d2343e69ddca','746d97a67922896b7d1581c4689f8b5f85204d30')
    save('verify_edit_scope_action_hook_20260914.py',text,path)
    write(output/'derivation.json',encode(receipts));print(encode(dict(files=len(receipts),sha256=sha((output/'derivation.json').read_bytes()))).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
