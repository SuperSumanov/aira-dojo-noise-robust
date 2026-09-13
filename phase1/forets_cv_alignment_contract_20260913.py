"""Measurement-only diagnostic instrumentation plus an explicit replay seed."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

CODE='ac6c125b38d2851dd3602eeea5fb7f140ec4c6b12468f5714069a637cbc27987'


def instrument(code):
    original_ast=ast.parse(code)
    changes=[
      ('import numpy as np','import numpy as np\nimport random\nrandom.seed(20260913)\nnp.random.seed(20260913)'),
      ('study = optuna.create_study(direction="maximize")','study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=20260913))'),
      ('predictions = []\n','predictions = []\ndiag_oof = np.empty(len(y), dtype=int)\ndiag_seen = np.zeros(len(y), dtype=int)\ndiag_order = []\n'),
      ('    predictions.extend(pred_labels)','    predictions.extend(pred_labels)\n    diag_oof[val_idx] = pred_labels\n    diag_seen[val_idx] += 1\n    diag_order.extend(val_idx)'),
      ('cv_score = accuracy_score(y, predictions)','cv_score = accuracy_score(y, predictions)\nassert np.all(diag_seen == 1)\nassert np.array_equal(np.sort(diag_order), np.arange(len(y)))\nassert np.array_equal(np.asarray(predictions), diag_oof[np.asarray(diag_order)])\ndiag_aligned_score = accuracy_score(y, diag_oof)\nnp.savez("cv_alignment_private.npz", y=y.to_numpy(), concatenated=np.asarray(predictions), aligned=diag_oof, order=np.asarray(diag_order), counts=diag_seen)\nprint("FORETS_CV_ALIGNMENT_DIAGNOSTIC " + __import__("json").dumps(dict(original_concatenated_accuracy=float(cv_score), aligned_accuracy=float(diag_aligned_score), rows=len(y), seed=20260913)))')]
    for before,after in changes:
        # Do not confuse predictions=[] with final_predictions=[].
        if before=='predictions = []\n':before='\n'+before;after='\n'+after
        if code.count(before)!=1:raise ValueError('exact diagnostic anchor')
        code=code.replace(before,after,1)
    changed_ast=ast.parse(code)
    def training_calls(tree):
        return [ast.dump(n,include_attributes=False) for n in ast.walk(tree) if isinstance(n,ast.Call)
                and isinstance(n.func,ast.Attribute) and n.func.attr in ('train','predict','optimize','suggest_int','suggest_float')]
    if training_calls(original_ast)!=training_calls(changed_ast):raise ValueError('training/prediction call changed')
    return code,changes


def prepare(commit,ns):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact commit')
    ns['source_check']();parent=ns['PARENT'];sha=ns['sha'];safe=ns['safe_bytes'];write=ns['write']
    finish=json.loads(safe(parent/'readout-finished.json',parent))
    if finish['status']!='verified':raise ValueError('parent closure')
    jp=parent/'runs/02-spaceship-titanic-s32-critic_topk_random/checkpoint/journal.jsonl'
    original=safe(jp,parent);nodes=[json.loads(x) for x in original.splitlines()]
    candidates=[n for n in nodes if n['step']==4 and sha(n['code'].encode())==CODE]
    if len(candidates)!=1:raise ValueError('observed source identity')
    code,changes=instrument(candidates[0]['code'])
    if ns['SECRET'].search(code.encode()):raise ValueError('credential in diagnostic')
    root=Path(tempfile.mkdtemp(prefix='forets-pool-completion-20260912-',dir=ns['BASE']));os.chmod(root,0o700)
    (root/'codes').mkdir();(root/'codes/0.py').write_text(code,encoding='utf-8',newline='\n')
    donor=json.loads((ns['ADAPTER']/'submit-intent.json').read_bytes())
    for name in ns['HELPERS']:
        raw=safe(ns['ADAPTER']/name,ns['ADAPTER'])
        if sha(raw)!=donor['code_sha256'][name]:raise ValueError('adapter drift')
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ns['ADAPTER']/name,dest)
    stage=Path(ns['__file__']).parent
    for name in ('forets_pool_completion_20260912.py','forets_pool_completion_20260912.sbatch','forets_closed_pool_20260911.py',
                 'FORETS_CV_ALIGNMENT_DIAGNOSTIC_PLAN_20260913.md','forets_cv_alignment_contract_20260913.py'):
        shutil.copy2(stage/name,root/name)
    (root/'forets_current_pool_20260912.py').write_text('from forets_pool_completion_20260912 import binding_context\n')
    (root/'opencl-vendors').mkdir();(root/'opencl-vendors/nvidia.icd').write_text('libnvidia-opencl.so.1\n')
    write(root/'measurement-instrumentation.json',dict(original_code_sha256=CODE,changes=changes,seed=20260913,
        original_optuna_seed_was_unspecified=True,not_historical_model_replay=True,one_fit_shared_predictions=True))
    files={str(p.relative_to(root)):sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    write(root/'prepared.json',dict(root=str(root),commit=commit,utc=ns['now'](),source_tree=ns['TREE'],
        rows=[dict(index=0,task='spaceship-titanic',seed=20260913,code_sha256=sha((root/'codes/0.py').read_bytes()))],
        parent_evidence={str(jp.relative_to(parent)):sha(original),'readout-finished.json':sha((parent/'readout-finished.json').read_bytes())},
        files=files,maximum_allocation_gpu_hours=.25,fixed_program_timeout_seconds=300,handshake_timeout_seconds=120,
        api_calls=0,role='same_fit_cv_index_diagnostic_not_e2e',seed=20260913))
    readers=('readout_cv_alignment_20260913.py','readout_forets_generation_capacity_20260912.py')
    write(root/'cv-readout-plan.json',dict(root=str(root),utc=ns['now'](),
        readers={n:sha((stage/n).read_bytes()) for n in readers},
        prepared_sha256=sha((root/'prepared.json').read_bytes()),original_training_predict_calls_unchanged=True))
    print(json.dumps(dict(root=str(root),prepared_sha256=sha((root/'prepared.json').read_bytes()),programs=1)))
