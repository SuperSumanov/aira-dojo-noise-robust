"""Mechanical adaptation of existing launcher and independent readers."""
import argparse
from pathlib import Path
from forets_environment_build_20260912 import write,encode,sha
from forets_paid_patch_20260911 import once
from build_forets_action_prospective_20260913 import replace_function

EFFECTS='''def effects(rows, seeds=(38,39)):
    if tuple(seeds)!=(38,39) or len(rows)!=8 or {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in TASKS for s in seeds for a in ARMS}:
        raise ValueError('eight exact width-control rows required')
    for r in rows:
        if r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score'])):raise ValueError('valid score absent')
        if not r['valid'] and r['score'] is not None:raise ValueError('no missing imputation')
    return {}
'''

def derive(output):
    output.mkdir(exist_ok=False);base=Path(__file__).resolve().parent;evidence={}
    def save(name,text,src,raw):
        compile(text,name,'exec');write(output/name,text.encode())
        evidence[name]=dict(base_file=src.relative_to(base).as_posix(),base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    src=base/'readout_forets_wallclock_20260912.py';raw=src.read_bytes();text=raw.decode()
    text=replace_function(text,'effects',EFFECTS)
    text=once(text,"ARMS=('uniform_random','critic_topk_random')","ARMS=('batch_four','direct_two')")
    text=once(text,"if (tuple(seeds),tuple(blocks)) not in (((22,23),(1,)),((24,25),(1,)),((26,27),(1,2)),((28,29),(1,2))):",
        "if (tuple(seeds),tuple(blocks)) != ((38,39),(1,2)):")
    text=once(text,"critic='qwen/qwen3-coder-plus' if planned['arm']==ARMS[1] else None","critic=None")
    text=once(text,"critic_ranking_votes=(1 if tuple(seeds) in ((26,27),(28,29)) else 2) if planned['arm']==ARMS[1] else 0,","critic_ranking_votes=0,")
    text=once(text,'worker_elapsed_seconds=None,technical_eligible=False','worker_elapsed_seconds=None,search_start_ns=None,technical_eligible=False')
    text=once(text,"row['worker_elapsed_seconds']=summary['elapsed_seconds']","row['worker_elapsed_seconds']=summary['elapsed_seconds']\n        row['search_start_ns']=summary['search_start_ns']")
    text=once(text,'Two tasks/two fresh seeds; cutoff includes online critic. Cleanup is extra and charged. No exact physical-cost equality or scaling claim.',
        'Two tasks/two new seeds, uniform proposal width two vs four. This file retains the secondary iteration endpoint. Cleanup charged, no exact physical-cost equality, critic efficacy or scaling claim.')
    save('readout_width_core_20260913.py',text,src,raw)
    src=base/'verify_forets_reference_integration_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,"for arm in ('uniform_random','critic_topk_random'):","for arm in ('batch_four','direct_two'):")
    text=once(text,'assert count==dict(generation=4,ranking=',"assert count==dict(generation=cfg['num_children'],ranking=")
    text=once(text,'dict(task=solver.task_name,arm=arm,seed=',"dict(task=solver.task_name,arm='uniform_random',seed=")
    text=once(text,"root/'reference-integration.json'","root/'width-integration.json'")
    text=text.replace('CPU_ACTUAL_REFERENCE_REQUEST_NOT_EFFICACY','CPU_ACTUAL_WIDTH_CONTRAST_NOT_EFFICACY')
    save('verify_width_batch_20260913.py',text,src,raw)
    src=base/'releases/forets-action-tools-20260913-v2/verify_deployed_action_hook_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,"ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-7wzrny21')","ROOT=Path(sys.argv[1]).resolve(strict=True)")
    text=once(text,"artifact['base_tree']!='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798'","artifact['base_tree']!='f7a8b9e3c07b530467573315d55f62203cc67895'")
    save('verify_width_action_hook_20260913.py',text,src,raw)
    src=base/'releases/forets-action-tools-20260913-v2/launch_action_prospective_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,'from build_forets_action_prospective_20260913 import order','from build_forets_width_control_20260913 import order')
    old="    branch=read(root/'uniform-integration.json')\n    if branch['source_tree']!=build['source_tree'] or len(branch['rows'])!=1 or branch['rows'][0]['counts']!=dict(generation=4,ranking=0,execution=3,reservation=0,settlement=0):raise ValueError('actual uniform integration')"
    new="""    branch=read(root/'width-integration.json')
    if branch['source_tree']!=build['source_tree'] or len(branch['rows'])!=2:raise ValueError('width integration inventory')
    for r in branch['rows']:
        width={'batch_four':4,'direct_two':2}[r['arm']]
        if r['counts']!=dict(generation=width,ranking=0,execution=3,reservation=0,settlement=0) or r['actual_siblings']!=2:raise ValueError('actual width integration')"""
    text=once(text,old,new)
    text=once(text,'typed_equal_arm_configs=0,paired_delivery_trajectories=8','typed_fanout_only_pairs=4,independent_searches=8')
    text=once(text,'from readout_action_prospective_20260913 import FILES','from readout_forets_width_control_20260913 import FILES')
    save('launch_width_control_20260913.py',text,src,raw)
    write(output/'derivation.json',encode(evidence))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();derive(a.output)
