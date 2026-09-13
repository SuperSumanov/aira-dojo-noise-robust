"""Mechanically derive successor readout without touching active frozen readers."""
import argparse
from pathlib import Path
from forets_environment_build_20260912 import write,encode,sha
from forets_paid_patch_20260911 import once
from build_forets_action_prospective_20260913 import replace_function


def run(output):
    output.mkdir(exist_ok=False);base=Path(__file__).parent
    old=base/'releases/forets-edit-scope-tools-20260914';proof={}
    def save(name,text,path):
        compile(text,name,'exec');write(output/name,text.encode())
        proof[name]=dict(parent=str(path.relative_to(base)),parent_sha256=sha(path.read_bytes()),sha256=sha(text.encode()))
    def shared(text):
        for a,b in [(
            "ARMS=('whole_program','model_module')","ARMS=('whole_program','preserve_program','model_module')"),
            ('(42,43,44,45)','(46,47)'),('len(rows)!=16','len(rows)!=12'),
            ('sixteen exact edit-scope rows','twelve exact preservation rows'),
            ('readout_edit_scope_core_20260914','readout_scope_preservation_core_20260914'),
            ('readout_edit_scope_20260914','readout_scope_preservation_20260914'),
            ('edit-scope-summary.json','scope-preservation-summary.json'),
            ('edit-scope-runs.csv','scope-preservation-runs.csv')]:text=text.replace(a,b)
        return text
    path=old/'readout_edit_scope_core_20260914.py';text=shared(path.read_text())
    text=text.replace('Two tasks/four new seeds; edit scope comparison. Same refactored start.',
        'Two tasks/two fresh seeds, whole/preserve/module. Same refactored start.')
    save('readout_scope_preservation_core_20260914.py',text,path)
    path=old/'readout_edit_scope_20260914.py';text=shared(path.read_text())
    text=text.replace('Closed eight-run width comparison; action primary, iteration secondary.',
        'Conditional twelve-run preservation comparison; action primary, iteration secondary.')
    text=once(text,'def paired_effects(rows):','def paired_effects(rows):')
    text=replace_function(text,'paired_effects','def paired_effects(rows):\n    from scope_preservation_effects_20260914 import effects\n    return effects(rows)')
    text=once(text,"'forets_edit_scope_20260914.py')","'forets_edit_scope_20260914.py','scope_preservation_effects_20260914.py')")
    text=once(text,"width={'whole_program':2,'model_module':2}","width={'whole_program':2,'preserve_program':2,'model_module':2}")
    text=once(text,"if s['edit_scope'] != r['arm']:","if s['edit_scope'] != ('model_module' if r['arm']=='model_module' else 'whole_program'):")
    text=once(text,"role='edit_scope_uniform_1200_e2e_development'","role='preservation_strong_control_1200_e2e_development'")
    old_limit='Eight fresh task-seed pairs. Same refactored RF start and 1200s budget; full-program vs model-module output/edit scope. Prompt/format/available editable space differ as the defined intervention. Not a critic/scaling or novel algorithm claim. Technical missingness not imputed.'
    text=once(text,old_limit,'Four fresh task-seed triplets. Whole, preservation-prompt/full-output, and module-interface arms; all three pairwise contrasts and both endpoints retained. Same common start and resource caps, actual cost may differ. Exploratory only; no critic, scaling, novel algorithm, or task-population claim. Missingness not imputed.')
    save('readout_scope_preservation_20260914.py',text,path)
    path=base/'scope_preservation_effects_20260914.py';save(path.name,path.read_text(),path)
    write(output/'derivation.json',encode(proof));print(encode(dict(files=len(proof),derivation_sha256=sha((output/'derivation.json').read_bytes()))).decode())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
