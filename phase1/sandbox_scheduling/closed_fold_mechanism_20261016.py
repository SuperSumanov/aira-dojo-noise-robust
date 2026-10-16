"""Post-hoc18819: verify realized fold/ensemble truncation, without new runs.

Reads ONLY sealed18819 approved DEV programs/logs and existing step receipts.
Never exports raw code/logs, CV metric values, input data or predictions.
The association does not establish that folds alone mediate the score change.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
from closed_clock_screen_20261016 import SECRET

ROOT=Path('/research/d7/spc/yzyang4/clock-rank-20261016-v1')
PIN='4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def parse_folds(text,epochs,steps):
    assert not SECRET.search(text),'credential-shape hit; withhold'
    starts=[tuple(map(int,m)) for m in re.findall(r'Fold\s+(\d+):\s+(\d+)\s+patches,\s+(\d+)\s+batches/epoch',text)]
    # Match only the prefix; neither readout nor output extracts CV scores.
    completed=list(map(int,re.findall(r'Fold\s+(\d+):\s+RMSE\s*=',text)))
    totals=list(map(int,re.findall(r'(\d+)-Fold\s+CV\s+RMSE:',text)))
    skipped=list(map(int,re.findall(r'Time guard:\s+skipping fold\s+(\d+)',text)))
    ids=[x[0] for x in starts]
    assert ids==list(range(1,len(ids)+1)) and 0<len(ids)<=5
    assert completed==ids and totals==[len(ids)]
    assert skipped==([] if len(ids)==5 else [len(ids)+1])
    expected=epochs*sum(x[2] for x in starts)
    assert expected==steps,'logged fold batches and optimizer receipts disagree'
    return dict(completed_folds=len(ids),batches_per_epoch=[x[2] for x in starts],
        time_guard_skipped_fold=skipped,expected_optimizer_steps=expected,observed_optimizer_steps=steps,
        completion_and_steps_match=True)

def source_contract(code):
    assert not SECRET.search(code),'credential-shape hit; withhold'
    tree=ast.parse(code)
    assignments={n.targets[0].id:n.value.value for n in tree.body if isinstance(n,ast.Assign)
        and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Constant)}
    assert assignments['EPOCHS']==12 and assignments['TIME_LIMIT']==280
    fold=next(n for n in tree.body if isinstance(n,ast.For) and ast.unparse(n.target)=='fold_idx')
    assert ast.unparse(fold.iter)=='range(5)'
    guard=fold.body[0]
    assert isinstance(guard,ast.If)
    assert ast.unparse(guard.test)=='fold_idx > 0 and time.time() - start_time > TIME_LIMIT * 0.72'
    assert any(isinstance(n,ast.Break) for n in guard.body)
    epoch=next(n for n in fold.body if isinstance(n,ast.For) and ast.unparse(n.target)=='epoch')
    assert ast.unparse(epoch.iter)=='range(EPOCHS)'
    assert not any(isinstance(n,(ast.Break,ast.Return)) for n in ast.walk(epoch))
    calls=[ast.unparse(n) for n in ast.walk(fold) if isinstance(n,ast.Call)]
    assert 'models_trained.append(model)' in calls
    prediction_loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and ast.unparse(n.iter)=='models_trained']
    assert len(prediction_loops)==1 and ast.unparse(prediction_loops[0].target)=='model'
    assert any(isinstance(n,ast.Assign) and ast.unparse(n.value)=='pred_sum / len(models_trained)' for n in ast.walk(tree))
    return dict(epochs_per_completed_fold=12,max_folds=5,batch_size=assignments['BATCH_SIZE'],
        fold_admission_deadline_seconds=280*.72,deadline_checked_before_new_fold=True,
        no_inner_epoch_break_or_return=True,completed_models_appended=True,
        predictions_average_completed_fold_models=True,
        boundary='Exact static syntax checks plus runtime completion receipts, not an arbitrary-program proof.')

def main():
    assert sha(ROOT/'plan.json')==PIN and (ROOT/'closed.json').exists()
    summary=read(ROOT/'readout-20261016-v1/summary.json')
    assert summary['complete']==16 and summary['valid']==16 and summary['structure']
    plan=read(ROOT/'plan.json');contracts={}
    for p in (2,3):contracts[p]=source_contract((ROOT/f'programs/{p}.private.py').read_text())
    rows=[]
    for s in plan['schedule']:
        if s['program'] not in contracts:continue
        ep=ROOT/f"episode-{s['index']}";log=ep/'worker.private.log'
        steps=read(ep/'gpu-training.json')['cuda_gradient_steps']
        rows.append(dict(index=s['index'],program=s['program'],mode=s['mode'],block=s['block'],
            source_sha256=sha(ROOT/f"programs/{s['program']}.private.py"),log_sha256=sha(log),
            **parse_folds(log.read_text(errors='replace'),12,steps)))
    assert len(rows)==8
    out=dict(posthoc=True,plan_sha256=PIN,analysis_sha256=sha(Path(__file__)),
        contracts=contracts,rows=rows,
        conclusion='For these two closed DEV programs sharing changes completed fold count and hence ensemble membership. Both restarts agree. Not a fold-only causal intervention, a general incidence estimate, an E2E gain or a new scheduling algorithm.')
    dest=ROOT/'fold-mechanism-20261016.safe.json'
    with dest.open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
    print(json.dumps(out))

if __name__=='__main__':main()
