"""Counterexamples through pinned native SFT exporter, synthetic data only."""
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
import subprocess

COMMIT = 'b8e75052a9f69e19436f12bc5a36a0ca26a69a57'
REPO = '/research/d7/spc/yzyang4/aira-dojo'

def git(*args):
    result = subprocess.run(['git', '-C', REPO, *args], capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('source_read_failed')
    return result.stdout

def write_jsonl(path, rows):
    with path.open('x') as f:
        for row in rows:f.write(json.dumps(row)+'\n')

def main():
    source=git('show',COMMIT+':src/mle_policy/src/data/to_sft.py')
    expected='a617554af4d3722873e9699c4861c6f5adffe4fceb235943ebb34fcf08981e87'
    if hashlib.sha256(source).hexdigest()!=expected:raise ValueError('source_drift')
    archive=git('archive',COMMIT,'src/mle_policy/src','src/dojo/configs/solver/operators/mlebench')
    with tempfile.TemporaryDirectory(prefix='policy9b-sft-semantics-') as tmp:
        root=Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(root,filter='data')
        sys.path.insert(0,str(root/'src/mle_policy'))
        native=importlib.import_module('src.data.to_sft')
        data=root/'fixture';data.mkdir()
        samples=[];groups=[]
        def episode(group,eid,root_operator,reward,operations):
            ids=[]
            for index,(operator,runnable,completion) in enumerate(operations):
                sid=eid+'-'+str(index);ids.append(sid)
                samples.append({'sample_id':sid,'group_id':group,'task':'SYNTHETIC_NO_TASK_DATA',
                    'operator':operator,'batch':'fixture','node_step':index,'node_is_buggy':not runnable,
                    'node_has_result':runnable,'node_reward':reward if runnable else None,'episode_reward':reward,
                    'prompt':[{'role':'system','content':'fixture operator '+operator},{'role':'user','content':'fixture state '+group}],
                    'completion':completion})
            return {'sample_id':ids[0],'root_sample_id':ids[0],'sample_ids':ids,'episode_id':eid,
                    'operator':root_operator,'node_step':0,'episode_reward':reward,'episode_resolved':True}
        groups.append({'group_id':'repair','members':[
            episode('repair','winner','draft',1.0,[('draft',False,'deliberately failing proposal'),('analysis',False,'deliberately incorrect diagnostic claim'),('debug',True,'valid repaired solution'),('analysis',True,'terminal analysis')]),
            episode('repair','runnerup','draft',0.9,[('draft',True,'valid one-step solution'),('analysis',True,'analysis')])]})
        groups.append({'group_id':'regression','members':[
            episode('regression','best-child','improve',0.7,[('improve',True,'valid but lower quality than parent'),('analysis',True,'analysis')]),
            episode('regression','other-child','improve',0.6,[('improve',True,'another lower quality child'),('analysis',True,'analysis')])]})
        groups.append({'group_id':'short','members':[episode('short','short-path','draft',1.0,[('draft',True,'valid'),('analysis',True,'analysis')])]})
        groups.append({'group_id':'long','members':[episode('long','long-path','draft',1.0,[('draft',False,'failed'),('analysis',False,'analysis'),('debug',False,'still failed'),('analysis',False,'analysis'),('debug',True,'valid'),('analysis',True,'analysis')])]})
        write_jsonl(data/'samples.jsonl',samples);write_jsonl(data/'groups.jsonl',groups)
        write_jsonl(data/'splits.jsonl',[{'group_id':g['group_id'],'split':'train'} for g in groups])
        (data/'manifest.json').write_text(json.dumps({'normalize_packages':False}))
        native.to_sft(data,root/'all',verbose=False)
        native.to_sft(data,root/'improve_only',operators={'improve'},verbose=False)
        rows=[json.loads(x) for x in (root/'all/sft.jsonl').read_text().splitlines()]
        selected=[json.loads(x) for x in (root/'improve_only/sft.jsonl').read_text().splitlines()]
        counts={g:sum(r['group_id']==g for r in rows) for g in ('repair','regression','short','long')}
        repair=[r for r in rows if r['group_id']=='repair']
        fail_target=any(r['messages'][-1]['content']=='deliberately failing proposal' for r in repair)
        wrong_analysis=any(r['messages'][-1]['content']=='deliberately incorrect diagnostic claim' for r in repair)
        selected_reward=next(r['episode_reward'] for r in rows if r['group_id']=='regression')
        parent_reward=0.8
        assert native.SFT_SCHEMA.names == ['messages']
        assert counts=={'repair':4,'regression':2,'short':2,'long':6}
        assert fail_target and wrong_analysis and selected_reward<parent_reward
        assert [r['operator'] for r in selected]==['improve','analysis']
        report={'utc':datetime.now(timezone.utc).isoformat(),'status':'NATIVE_EXPORT_COUNTEREXAMPLES_CONFIRMED',
            'commit':COMMIT,'native_exporter_sha256':expected,'synthetic_inputs_only':True,'real_training_rows_read':0,
            'model_training':False,'gpu_jobs':0,'cases':{
              'winning_episode_exports_failed_root':fail_target,
              'winning_episode_exports_unverified_analysis':wrong_analysis,
              'best_child_can_be_below_parent':{'parent_reward':parent_reward,'selected_child_reward':selected_reward,'gain':selected_reward-parent_reward},
              'same_endpoint_different_export_mass':{'short_episode_rows':counts['short'],'long_episode_rows':counts['long']},
              'operators_flag_is_root_filter_not_row_filter':{'requested':['improve'],'exported':[r['operator'] for r in selected]}},
            'total_exported_rows':len(rows),'parquet_columns':native.SFT_SCHEMA.names,'limits':['These are intentional-rule counterexamples, not estimates of prevalence in the actual training set.',
              'Full-episode imitation may be useful; the test does not establish its net effect or the cause of mentor model performance.',
              'Exported row counts are not measured optimizer loss or gradient weights.',
              'No model update or real ML score comparison was performed.']}
        print(json.dumps(report))

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'status':'FAILED_CLOSED','error_type':type(exc).__name__}));raise SystemExit(2)
