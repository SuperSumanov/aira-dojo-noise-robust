"""Source-bound CPU diagnostic only; neither imports the trainer nor calls train."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

path = Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective/lib/python3.11/site-packages/transformers/trainer.py')
source = path.read_bytes()
tree = ast.parse(source)
method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'create_accelerator_and_postprocess')
guards = [n for n in ast.walk(method) if isinstance(n, ast.If) and any(
    isinstance(c, ast.Constant) and isinstance(c.value, str)
    and "can't be used with `save_only_model` along with `load_best_model_at_end`" in c.value
    for child in n.body for c in ast.walk(child))]
assert len(guards) == 1
guard = guards[0]
expression = compile(ast.Expression(body=guard.test), str(path), 'eval')
cases = []
for deepspeed in (False, True):
    for model_only in (False, True):
        for load_best in (False, True):
            obj = SimpleNamespace(args=SimpleNamespace(save_only_model=model_only, load_best_model_at_end=load_best),
                                  is_deepspeed_enabled=deepspeed, is_fsdp_enabled=False)
            rejected = bool(eval(expression, {'__builtins__': {}}, {'self': obj}))
            assert rejected == (deepspeed and model_only and load_best)
            cases.append({'deepspeed': deepspeed, 'save_only_model': model_only,
                          'load_best_model_at_end': load_best, 'rejected_by_installed_guard': rejected})
no_reload_dependencies = {}
for name in ('_save_checkpoint', '_determine_best_metric'):
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    referenced = any(isinstance(n, ast.Attribute) and n.attr == 'load_best_model_at_end' for n in ast.walk(func))
    assert not referenced
    no_reload_dependencies[name] = not referenced
root = Path('/research/d7/spc/yzyang4/critic-component-g0/runs/job-12181')
worker = (root / 'worker.log').read_bytes()
assert hashlib.sha256(worker).hexdigest() == '28745e18359126e444ff49626d1fdce725bf6d18b0ab407e4a557bcfb8f71790'
assert b'[rm-timing]' not in worker
assert not list((root / 'output').glob('checkpoint-*'))
elapsed_seconds = 156
print(json.dumps({'job_id': 12181, 'status': 'FAILED_BEFORE_TRAIN_LOOP',
                  'framework_guard_reproduced_cpu_only': True, 'guard_line': guard.lineno,
                  'guard_expression': ast.unparse(guard.test),
                  'framework_trainer_sha256': hashlib.sha256(source).hexdigest(),
                  'truth_table_cases': cases, 'checkpoint_functions_do_not_depend_on_reload': no_reload_dependencies,
                  'proposal': 'G0-only load_best_model_at_end=false; keep save_strategy=best and save_only_model=true',
                  'proposal_applied': False, 'gpu_retry_authorized': False,
                  'checkpoint_count': 0, 'train_begin_marker_present': False,
                  'scheduler_elapsed_seconds': elapsed_seconds, 'allocated_gpus': 2,
                  'allocation_gpu_hours': elapsed_seconds * 2 / 3600,
                  'original_budget_gpu_hours': 4,
                  'maximum_additional_two_gpu_seconds_within_original_total': 7200 - elapsed_seconds,
                  'cpu_predicate_test_not_full_trainer_or_gpu_validation': True,
                  'new_gpu_jobs': 0, 'new_model_fits': 0}, indent=2, sort_keys=True))
