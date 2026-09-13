"""Explicitly reuse frozen endpoint arithmetic, replacing only matrix/arm names."""
import argparse
from pathlib import Path
from forets_environment_build_20260912 import write,encode,sha
from forets_paid_patch_20260911 import once

def derive(output,parent_tree):
    output.mkdir(exist_ok=False);base=Path(__file__).resolve().parent;evidence={}
    def save(name,text,src,raw):
        compile(text,name,'exec');write(output/name,text.encode())
        evidence[name]=dict(base_file=src.relative_to(base).as_posix(),base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    def basic(text):
        for a,b in [('batch_four','no_memory'),('direct_two','execution_memory'),('(38,39)','(40,41)'),
            ('seeds38-39','seeds40-41'),('direct_oriented_gain','memory_oriented_gain'),
            ('direct_minus_batch_api_usd','memory_minus_control_api_usd'),('batch_valid','control_valid'),('direct_valid','memory_valid')]:text=text.replace(a,b)
        return text
    src=base/'releases/forets-width-tools-20260913/readout_width_core_20260913.py';raw=src.read_bytes();text=basic(raw.decode())
    text=text.replace('uniform proposal width two vs four','frozen error memory on vs off')
    save('readout_memory_core_20260913.py',text,src,raw)
    src=base/'readout_forets_width_control_20260913.py';raw=src.read_bytes();text=basic(raw.decode())
    text=text.replace('readout_forets_width_control_20260913','readout_forets_memory_control_20260913').replace('readout_width_core_20260913','readout_memory_core_20260913')
    text=text.replace("{'no_memory':4,'execution_memory':2}","{'no_memory':2,'execution_memory':2}")
    text=text.replace('width-summary.json','memory-summary.json').replace('width-runs.csv','memory-runs.csv')
    text=once(text,"role='proposal_width_two_vs_four_uniform_e2e_development'","role='prior_error_memory_uniform_e2e_development'")
    text=once(text,'Four fresh task-seed pairs; only proposal width differs. Actual token samples differ, no critic efficacy or new algorithm/scaling claim. Invalid/technical failures not imputed.',
        'Four fresh task-seed pairs; only fixed prior-error prompt differs. Both generate and execute two. Prompt length differs as part of the intervention, actual token samples differ. No critic efficacy/new algorithm/scaling claim; failures not imputed.')
    text=once(text,"from read_forets_action_delivery_20260913 import read_latest", "from read_forets_action_delivery_20260913 import read_latest\nfrom forets_execution_memory_20260913 import TEXT_SHA,OPERATORS,HEADER")
    text=once(text,"'verify_branching_selection_20260913.py')","'verify_branching_selection_20260913.py','forets_execution_memory_20260913.py')")
    text=once(text,"cp=Path(s['checkpoint_path'])", """memory=read(root/'frozen-memory.json')
        if sha(memory['text'].encode())!=TEXT_SHA:raise ValueError('memory text drift')
        for operator in OPERATORS:
            template=s['operators'][operator]['system_message_prompt_template']['template']
            if r['arm']=='execution_memory':
                if template.count(HEADER)!=1 or not template.endswith('\\n\\n'+memory['text']):raise ValueError('memory absent or modified')
            elif HEADER in template:raise ValueError('control contaminated')
        cp=Path(s['checkpoint_path'])""")
    save('readout_forets_memory_control_20260913.py',text,src,raw)
    src=base/'releases/forets-width-tools-20260913/verify_width_batch_20260913.py';raw=src.read_bytes();text=basic(raw.decode())
    text=text.replace('width-integration.json','memory-batch-integration.json').replace('WIDTH_CONTRAST','MEMORY_COMMON_BATCH')
    save('verify_memory_batch_20260913.py',text,src,raw)
    src=base/'releases/forets-width-tools-20260913/verify_width_action_hook_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,'f7a8b9e3c07b530467573315d55f62203cc67895',parent_tree)
    text=text.replace('verify_width_action_hook_20260913.py','verify_memory_action_hook_20260913.py')
    save('verify_memory_action_hook_20260913.py',text,src,raw)
    src=base/'releases/forets-width-tools-20260913/launch_width_control_20260913.py';raw=src.read_bytes();text=basic(raw.decode())
    text=text.replace('build_forets_width_control_20260913','build_forets_memory_control_20260913').replace('readout_forets_width_control_20260913','readout_forets_memory_control_20260913')
    text=text.replace('width-integration.json','memory-batch-integration.json').replace("{'no_memory':4,'execution_memory':2}","{'no_memory':2,'execution_memory':2}")
    text=once(text,'typed_fanout_only_pairs=4','typed_memory_only_pairs=4')
    text=once(text,"    action=read(root/'action-integration.json')", """    prompts=read(root/'memory-prompt-integration.json')
    if prompts['source_tree']!=build['source_tree'] or prompts['actual_operator_calls']!=24 or not prompts['only_frozen_memory_differs']:
        raise ValueError('actual generation prompt integration')
    action=read(root/'action-integration.json')""")
    save('launch_memory_control_20260913.py',text,src,raw)
    src=base/'monitor_width_control_20260913.py';raw=src.read_bytes();text=basic(raw.decode())
    save('monitor_memory_control_20260913.py',text,src,raw)
    write(output/'derivation.json',encode(evidence))
    print(encode(dict(files=len(evidence),parent_tree=parent_tree,derivation_sha256=sha((output/'derivation.json').read_bytes()))).decode())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--parent-tree',required=True);a=p.parse_args();derive(a.output,a.parent_tree)
