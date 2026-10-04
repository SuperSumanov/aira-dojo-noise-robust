"""Pre-submit token sizing on the actual local tokenizer; no generation."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

B = Path('/research/d7/spc/yzyang4')
R = B/'diagnostic-information-20261004-v1'
D = B/'executable-evidence-20261004-v1'
sys.path.insert(0, str(R))
import task_feedback_real_20261001 as x
m = x.m
m.check()
m.setup()
entry = (R/'service_entry.py').read_text()
assert not m.SECRET.search(entry.encode())
limits = []
for node in ast.walk(ast.parse(entry)):
    if not isinstance(node, (ast.List, ast.Tuple)):
        continue
    for i, element in enumerate(node.elts[:-1]):
        if isinstance(element, ast.Constant) and element.value == '--max-model-len':
            limits.append(int(ast.literal_eval(node.elts[i+1])))
assert len(limits) == 1
limit = limits[0]
from transformers import AutoTokenizer
from dojo.config_dataclasses.run import RunConfig
from dojo.tasks.mlebench.task import MLEBenchTask
tokenizer = AutoTokenizer.from_pretrained(m.ASSETS/'model', local_files_only=True, trust_remote_code=False)
records = []
for s in x.schedule():
    cfg = RunConfig.load_from_json(R/'configs'/f"{s['index']}.json")
    task = MLEBenchTask(cfg.task)
    parent = m.read(R/'starts'/f"{s['start']}.private.json")['code']
    old_path = D/f"episode-{(0,15)[s['start']]}/action-0/node.private.json"
    raw = old_path.read_bytes()
    assert not m.SECRET.search(raw)
    old = json.loads(raw)
    assert parent == old['code']
    history = 'ACTION0 SOLUTION\n'+old['terminal'][-12000:]+'\nExternal development score: <measured at run time>\n'
    prompt = x.prompt(task.task_description, s, 1, [parent], history, 500)
    ids = tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=True,
        add_generation_prompt=True, enable_thinking=False)
    records.append(dict(index=s['index'], task=s['task'], arm=s['arm'], prompt_tokens=len(ids),
        output_reserve=4096, limit=limit, first_call_fits=len(ids)+4096<=limit))
assert len(records) == 12 and all(r['first_call_fits'] for r in records)
result = dict(status='PASS', plan_sha256=m.sha(R/'plan.json'), script_sha256=m.sha(Path(__file__)),
    max_model_len=limit, max_first_prompt_tokens=max(r['prompt_tokens'] for r in records), records=records,
    boundary='Token estimate uses exact parent/report and historic initial stdout, not new output or grade. Later prompts depend on generated code/outputs; no truncation or guarantee is added. Any context/transport failure remains in denominator.',
    generator_calls=0, gpu_hours=0)
with (R/'context-preflight.json').open('x') as f:
    json.dump(result, f, sort_keys=True, indent=2)
print(json.dumps({k: v for k, v in result.items() if k != 'records'}))
