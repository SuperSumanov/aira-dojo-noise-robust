"""Explicit mechanical reader/fixture adaptation for the new uniform matrix."""
import argparse
from pathlib import Path
from forets_environment_build_20260912 import write,encode,sha
from forets_paid_patch_20260911 import once
from build_forets_action_prospective_20260913 import replace_function

EFFECTS='''def effects(rows, seeds=(34,35,36,37)):
    expected={(t,s,'uniform_random') for t in TASKS for s in seeds}
    if tuple(seeds)!=(34,35,36,37) or len(rows)!=8 or {(r['task'],r['seed'],r['arm']) for r in rows}!=expected:
        raise ValueError('all eight uniform trajectories required')
    groups=[]
    for task in TASKS:
        rs=[r for r in rows if r['task']==task]
        values=[r['score'] for r in rs if r['valid'] and r['technical_eligible']]
        groups.append(dict(task=task,runs=len(rs),qualified_valid=len(values),
            conditional_median_score=statistics.median(values) if values else None,
            conditional_sample_std_score=statistics.stdev(values) if len(values)>1 else None))
    return dict(groups=groups)
'''

def derive(output,root):
    output.mkdir(exist_ok=False);base=Path(__file__).resolve().parent;evidence={}
    src=base/'readout_forets_wallclock_20260912.py';raw=src.read_bytes();text=raw.decode()
    text=replace_function(text,'effects',EFFECTS)
    old="if (tuple(seeds),tuple(blocks)) not in (((22,23),(1,)),((24,25),(1,)),((26,27),(1,2)),((28,29),(1,2))):"
    text=once(text,old,"if (tuple(seeds),tuple(blocks)) != ((34,35,36,37),(1,2)):")
    text=once(text,'worker_elapsed_seconds=None,technical_eligible=False','worker_elapsed_seconds=None,search_start_ns=None,technical_eligible=False')
    text=once(text,"row['worker_elapsed_seconds']=summary['elapsed_seconds']",
        "row['worker_elapsed_seconds']=summary['elapsed_seconds']\n        row['search_start_ns']=summary['search_start_ns']")
    text=once(text,"Two tasks/two fresh seeds; cutoff includes online critic. Cleanup is extra and charged. No exact physical-cost equality or scaling claim.",
        "Two tasks/four fresh seeds, uniform selection. Paired delivery is on the same recorded trajectory, not independent searches or zero-overhead counterfactual. No critic efficacy/scaling claim.")
    name='readout_action_prospective_core_20260913.py';compile(text,name,'exec')
    write(output/name,text.encode());evidence[name]=dict(base_file=src.name,base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    # This exercises the class actually shipped, not an independently patched
    # in-memory stand-in. Fake execution and analysis boundaries remain explicit.
    src=base/'verify_forets_action_delivery_integration_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,"ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-5_czzimk')",'ROOT=Path('+repr(root.as_posix())+')')
    text=once(text,"if artifact['source_tree']!='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798':raise ValueError('exact source')",
        "if artifact['base_tree']!='f1cdee3a9e553e8efeedaa1a66a2c6bd778f9798':raise ValueError('exact source parent')")
    text=once(text,"modified=patch_sources(*[(ROOT/'source'/p).read_text() for p in paths])",
        "modified=[(ROOT/'source'/p).read_text() for p in paths]")
    start=text.index('    # Patch this process');end=text.index("    with tempfile.TemporaryDirectory",start)
    text=text[:start]+"    ns=dict(production.__dict__)\n"+text[end:]
    text=once(text,"out=Path(__file__).with_name('action-integration.json')","out=ROOT/'action-integration.json'")
    text=text.replace("'real_source_hooks_with_fake_execution_not_efficacy'","'deployed_source_hooks_with_fake_execution_not_efficacy'")
    name='verify_deployed_action_hook_20260913.py';compile(text,name,'exec');write(output/name,text.encode())
    evidence[name]=dict(base_file=src.name,base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    src=base/'verify_forets_reference_integration_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,"for arm in ('uniform_random','critic_topk_random'):","for arm in ('uniform_random',):")
    text=once(text,"root/'reference-integration.json'","root/'uniform-integration.json'")
    text=text.replace('CPU_ACTUAL_REFERENCE_REQUEST_NOT_EFFICACY','CPU_ACTUAL_UNIFORM_BATCH_NOT_EFFICACY')
    name='verify_uniform_delivery_batch_20260913.py';compile(text,name,'exec');write(output/name,text.encode())
    evidence[name]=dict(base_file=src.name,base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    src=base/'releases/forets-reference-tools-20260913/launch_forets_reference_20260913.py';raw=src.read_bytes();text=raw.decode()
    text=once(text,'from build_forets_reference_20260913 import order','from build_forets_action_prospective_20260913 import order')
    old="    branch=read(root/'reference-integration.json')\n    if branch['source_tree']!=build['source_tree'] or len(branch['rows'])!=2 or any(r['actual_siblings']!=2 for r in branch['rows']):raise ValueError('actual branching integration')"
    new="    branch=read(root/'uniform-integration.json')\n    if branch['source_tree']!=build['source_tree'] or len(branch['rows'])!=1 or branch['rows'][0]['counts']!=dict(generation=4,ranking=0,execution=3,reservation=0,settlement=0):raise ValueError('actual uniform integration')\n    action=read(root/'action-integration.json')\n    if action['source_tree']!=build['source_tree'] or not action['independent_reader_matches'] or action['parsed_actions']!=3:raise ValueError('deployed action hook')"
    text=once(text,old,new)
    text=once(text,'from readout_forets_reference_20260913 import FILES','from readout_action_prospective_20260913 import FILES')
    text=once(text,'typed_equal_arm_configs=4','typed_equal_arm_configs=0,paired_delivery_trajectories=8')
    text=once(text,'rank_votes=1','rank_votes=0')
    text=once(text,'references_search_visible_only=True','references_search_visible_only=True,action_delivery_search_visible_only=True')
    name='launch_action_prospective_20260913.py';compile(text,name,'exec');write(output/name,text.encode())
    evidence[name]=dict(base_file=str(src.relative_to(base)),base_sha256=sha(raw),derived_sha256=sha(text.encode()))
    write(output/'derivation.json',encode(evidence))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('root',type=Path);a=p.parse_args();derive(a.output,a.root)
