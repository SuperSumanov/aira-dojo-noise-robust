"""Read-only diagnosis of a closed readout failure; never mutate its claim."""
import argparse, hashlib, inspect, json, os, sys
from pathlib import Path
import local_generator_runtime_20260914 as rt
from readout_comparison_pizza_online_20260919 import numerical

ROOT=rt.BASE/'comparison-pizza-full-deadline-20260919-yaywhbo1'
assert json.loads((ROOT/'closed.json').read_bytes())['status']=='all_four_episodes_closed'
assert not (ROOT/'summary.json').exists()
os.environ.update(PYTHON_DOTENV_DISABLED='1',MLE_BENCH_DATA_DIR=str(rt.BASE/'mle-bench-data'))
sys.path.insert(0,str(rt.ASSETS/'source/src'))
from dojo.tasks.mlebench.evaluate import evaluate_submission
from mlebench.registry import registry
import pandas as pd
comp=registry.set_data_dir(rt.BASE/'mle-bench-data').get_competition('random-acts-of-pizza')
sources={}
for name,fn in [('evaluate_submission',evaluate_submission),('grader_call',type(comp.grader).__call__),('read_csv',evaluate_submission.__globals__['read_csv']),('load_answers',evaluate_submission.__globals__['load_answers']),('prepare_for_auroc_metric',comp.grader.grade_fn.__globals__['prepare_for_auroc_metric'])]:
    value=inspect.getsource(fn)
    if rt.SHAPES.search(value.encode()):raise ValueError('source security')
    sources[name]=dict(sha256=hashlib.sha256(value.encode()).hexdigest(),source=value)
rows=[]
for i in range(4):
    ep=ROOT/f'episode-{i}';inc=ep/'incumbent.json'
    if not inc.exists():
        rows.append(dict(index=i,incumbent=False));continue
    saved=json.loads(inc.read_bytes());path=ep/f"work-{saved['action_index']}/submission.csv"
    if rt.sha(path)!=saved['submission_sha256']:raise ValueError('submission drift')
    frame=pd.read_csv(path);truth=pd.read_csv(comp.answers)
    rank=numerical('random-acts-of-pizza',frame,truth)
    direct=float(comp.grader.grade_fn(frame,truth))
    official_frame=evaluate_submission.__globals__['read_csv'](path)
    official_truth=evaluate_submission.__globals__['load_answers'](comp.answers)
    official_input_rank=numerical('random-acts-of-pizza',official_frame,official_truth)
    official_input_direct=float(comp.grader.grade_fn(official_frame,official_truth))
    target='requester_received_pizza'
    grade_files=[]
    for file in (ep/'closed-grade').rglob('*.json'):
        raw=file.read_bytes()
        if rt.SHAPES.search(raw):raise ValueError('grade security')
        value=json.loads(raw)
        # Do not emit arbitrary nested payloads or labels.
        safe={k:v for k,v in value.items() if k in {'score','valid_submission','is_lower_better'} and isinstance(v,(int,float,bool,type(None)))} if isinstance(value,dict) else {}
        grade_files.append(dict(relative=str(file.relative_to(ep)),sha256=hashlib.sha256(raw).hexdigest(),safe_fields=safe))
    rows.append(dict(index=i,incumbent=True,rank_auc=rank,official_direct=direct,difference=direct-rank,rounded_rank=round(rank,5),official_input_rank=official_input_rank,official_input_direct=official_input_direct,official_input_wrapped=float(comp.grader(official_frame,official_truth)),pd_dtype=str(frame[target].dtype),official_dtype=str(official_frame[target].dtype),max_prediction_read_difference=float((frame[target]-official_frame[target]).abs().max()),accepted_seconds=saved['accepted_seconds'],grade_files=grade_files))
output=dict(role='read_only_failed_readout_diagnostic',rows=rows,sources=sources,
    original_readout_claim_sha256=rt.sha(ROOT/'readout-claim.json'),utc=rt.utc())
parser=argparse.ArgumentParser();parser.add_argument('--save',action='store_true');args=parser.parse_args()
if args.save:rt.write(ROOT/'csv-precision-diagnostic.json',output)
print(json.dumps(output,indent=2))
