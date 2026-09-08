"""CPU preparation checks only; never invoke an actual GPU/model branch."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--entry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    ast.parse(args.entry.read_text())
    spec = importlib.util.spec_from_file_location('forets_gpu_preparation', args.entry)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = module.describe()
    assert plan['gpus'] == 1 and plan['gpu_hours_including_observed_KillWait'] == 25/60
    assert plan['process_seconds']+plan['process_kill_grace_seconds'] < plan['step_minutes']*60
    assert plan['step_minutes'] < plan['allocation_minutes']
    checks = ['stdlib_only_import_and_explicit_describe_matrix', 'nominal_and_KillWait_budget_separated']
    with tempfile.TemporaryDirectory(prefix='forets-8b-entry-check-', dir='/tmp') as tmp:
        root = Path(tmp)
        inputs = NS(execute_approved_gpu=False, source_root=root/'unread', checkpoint=root/'unread',
                    base_dir=root/'unread', output_dir=root/'never-created')
        try:
            module.run(inputs)
            raise AssertionError('missing execute flag accepted')
        except RuntimeError:
            pass
        assert not inputs.output_dir.exists()
        checks.append('missing_execution_flag_blocks_before_any_artifact_or_model_read')
        inputs.execute_approved_gpu = True
        with patch.dict(os.environ, {}, clear=True):
            try:
                module.run(inputs)
                raise AssertionError('missing Slurm context accepted')
            except RuntimeError:
                pass
        assert not inputs.output_dir.exists()
        checks.append('missing_Slurm_context_blocks_before_any_artifact_or_model_read')
        assert 'torch' not in sys.modules and 'transformers' not in sys.modules
    result = dict(status='PREPARATION_CHECKS_PASS_NOT_GPU_ACCEPTANCE', checks=checks, proposed_matrix=plan,
                  real_gpu_jobs=0, model_loads=0, external_api_requests=0, protected_data_read=False,
                  execution_branch_tested=False)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
