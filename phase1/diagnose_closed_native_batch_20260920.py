"""Closed action metadata only; no reply text or counterfactual external grading."""
import argparse,json
from pathlib import Path
import local_generator_runtime_20260914 as rt
root=rt.BASE/'comparison-native-batch-order-20260919-hz3c589n'
if not (root/'summary.json').exists():raise ValueError('primary reader has not closed')
keys=('kind','depth','status','exit_code','timed_out','submission_sha256','native_accepted','completed_seconds','internal_metric','analysis_status','error_type','started_seconds')
rows=[]
for index in range(4):
    ep=root/f'episode-{index}'
    for path in sorted(ep.glob('action-*.json')):
        raw=path.read_bytes()
        if rt.SHAPES.search(raw):raise ValueError('credential shape withheld')
        value=json.loads(raw)
        analysis=ep/f"analysis-{value.get('depth')}.private.json"
        parsed=None
        if analysis.exists():
            content=analysis.read_bytes()
            if rt.SHAPES.search(content):raise ValueError('private reply credential shape; withheld')
            response=json.loads(content).get('response')
            parsed=dict(type=type(response).__name__)
            if isinstance(response,dict):
                parsed['fields']={k:type(v).__name__ for k,v in response.items()}
                parsed['nontext_scalars']={k:v for k,v in response.items() if v is None or type(v) in (bool,int,float)}
        rows.append(dict(episode=index,action=path.name,metadata={key:value[key] for key in keys if key in value},parsed_analysis_structure=parsed))
output=dict(role='posthoc_closed_action_metadata_no_grading',summary_sha256=rt.sha(root/'summary.json'),rows=rows)
parser=argparse.ArgumentParser();parser.add_argument('--save',action='store_true');args=parser.parse_args()
if args.save:rt.write(root/'closed-action-diagnostic.json',output)
print(json.dumps(output,allow_nan=False))
