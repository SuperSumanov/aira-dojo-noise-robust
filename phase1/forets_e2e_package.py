"""Prepare the actual eight RunConfigs, not just RunnerConfig overrides.

No model, credential, API, task execution or Slurm dispatch. The package does not
authorize its commands. Run-side resource/service readiness remains necessary.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from forets_pilot_plan import (OPERATORS, FREE_CLIENTS, run_order, overrides,
                              free_route_overrides, bounded_launcher_overrides)

SOURCE_TREE = '2ff5277ba17327c6c03326a018b59f704402af6b'
UPSTREAM_COMMIT = '065b0fbaa89e0eb663f2834ec768081f5d56394d'
SOURCE = Path('/research/d7/spc/yzyang4/forets-nonpruning-20260909-Wmfn3x/source-v5')
DATA = Path('/research/d7/spc/yzyang4/mle-bench-data')
IMAGES = Path('/research/d7/spc/yzyang4/aira-dojo/build/superimage')
PYTHON = '/research/d7/spc/yzyang4/venvs/aira/bin/python'
IMAGE_VERSION = '2026-07-macos-v1'
CLIENT = 'litellm_nemotron-3-ultra'


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode()


def write_new(path, value):
    payload = encode(value)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
        f.write(payload)
    return hashlib.sha256(payload).hexdigest()


def common_config(value, *, run_id, run_dir):
    """Only selection_policy and mechanical run identity/path may differ."""
    value = copy.deepcopy(value)
    value.pop('id')
    value['solver'].pop('selection_policy')
    if value['solver']['exp_name'] != run_id:
        raise ValueError('unexpected experiment identity')
    value['solver']['exp_name'] = '<RUN_ID>'
    def normalise(item):
        if isinstance(item, dict):
            return {k: normalise(v) for k, v in item.items()}
        if isinstance(item, list):
            return [normalise(v) for v in item]
        if isinstance(item, str):
            # These are fixed generated paths/IDs, not arbitrary differing knobs.
            return item.replace(str(run_dir), '<RUN_DIR>')
        return item
    return normalise(value)


def prepare(output, *, source=SOURCE, data=DATA, images=IMAGES):
    import dotenv
    output = output.resolve()
    source, data, images = source.resolve(strict=True), data.resolve(strict=True), images.resolve(strict=True)
    image = images / ('superimage.root.' + IMAGE_VERSION + '.sif')
    if not image.is_file():
        raise FileNotFoundError('configured container image is missing')
    # No fallback to a different task, split, image or provider.
    from forets_pilot_plan import TASKS
    for task in TASKS:
        for visibility in ('public', 'private'):
            if not (data/task/'prepared'/visibility).is_dir():
                raise FileNotFoundError('prepared task directory is missing')
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for directory in ('configs', 'overrides', 'identities', 'runs'):
        (output/directory).mkdir(mode=0o700)
    # Deliberately do not read .env. Prevent imports from auto-loading one.
    os.environ.update(LOGGING_DIR=str(output), MLE_BENCH_DATA_DIR=str(data),
                      SUPERIMAGE_DIR=str(images), DEFAULT_SLURM_PARTITION='gpu_24h',
                      DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
                      PYTHON_DOTENV_DISABLED='1', LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path.insert(0, str(source/'src'))
    with patch.object(dotenv, 'load_dotenv', return_value=False):
        from hydra import compose, initialize_config_dir
        from hydra.utils import instantiate
        from omegaconf import OmegaConf
        from dojo.config_dataclasses.run import RunConfig
        from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
        register_new_resolvers()
        manifest = dict(schema=1, role='forets_e2e_development', source_tree=SOURCE_TREE, runs=[])
        rows, canonical, commands = [], [], []
        for index, (task, seed, policy) in enumerate(run_order()):
            run_id = f'{index:02d}-{task}-s{seed}-{policy}'
            run_dir = output/'runs'/run_id
            ov = overrides(task, seed, policy, max_output_tokens=8192, request_timeout_seconds=120)
            ov += bounded_launcher_overrides(max_api_attempts=40, max_output_tokens=8192)
            ov += free_route_overrides(CLIENT)
            ov += ['metadata.git_issue_id=forets-e2e-development-20260910',
                   '++metadata.git_commit_id=' + UPSTREAM_COMMIT,
                   '++metadata.description=upstream-plus-patches-tree-' + SOURCE_TREE,
                   '++metadata.launch_time=prepared-not-started',
                   '++metadata.base_path=' + str(source), '++metadata.user=yzyang4',
                   '++logger.output_dir=' + str(run_dir), 'logger.print_config=false',
                   'interpreter.superimage_directory=' + str(images),
                   'interpreter.superimage_version=' + IMAGE_VERSION]
            with initialize_config_dir(config_dir=str(source/'src/dojo/configs'), version_base=None):
                runner = instantiate(compose(config_name='default_runner', overrides=ov))
            tasks = runner.benchmark.to_cfg_list()
            if len(tasks) != 1 or tasks[0].name != task:
                raise ValueError('resolved benchmark is not the fixed task')
            config = RunConfig(id=run_id, meta_id='forets-e2e-development-20260910',
                logger=runner.logger, metadata=runner.metadata, task=tasks[0],
                solver=runner.solver, interpreter=runner.interpreter)
            resolved = OmegaConf.structured(config)
            OmegaConf.resolve(resolved)
            config = OmegaConf.to_object(resolved)
            config.validate()
            typed = config.to_typed_dict()
            roundtrip = RunConfig.from_dict(typed)
            roundtrip.validate()
            if roundtrip.to_typed_dict() != typed:
                raise ValueError('worker config round-trip changed values')
            if config.logger.write_env_vars or config.logger.use_wandb:
                raise ValueError('private local-only logging required')
            if config.solver.use_test_score or config.solver.skip_redundant_critic:
                raise ValueError('frozen solver settings changed')
            for op in OPERATORS:
                actual = getattr(config.solver.operators, op) if not isinstance(config.solver.operators, dict) else config.solver.operators[op]
                llm = actual.llm
                if llm.client.model_id != FREE_CLIENTS[CLIENT]:
                    raise ValueError('generator route changed')
            config_path = output/'configs'/(run_id+'.json')
            sha = write_new(config_path, typed)
            write_new(output/'overrides'/(run_id+'.json'), ov)
            canonical.append(common_config(typed, run_id=run_id, run_dir=run_dir))
            identity = output/'identities'/(run_id+'.json')
            manifest['runs'].append(dict(run_id=run_id, task=task, seed=seed, policy=policy,
                run_dir=str(run_dir.relative_to(output)), config_sha256=sha,
                process_summary=str((identity.with_suffix('.bounded')/'execution/summary.json').relative_to(output))))
            rows.append(dict(run_id=run_id, config_sha256=sha, roundtrip=True,
                data_dir=config.task.data_dir, image=str(image),
                generator=FREE_CLIENTS[CLIENT], selection_policy=policy,
                selector_seed=config.solver.selector_seed, max_steps=config.solver.step_limit))
            commands.append(dict(run_id=run_id, cwd=str(source),
                argv=['srun', '--jobid=<APPROVED_ALLOCATION>', '--exclusive', '--nodes=1',
                      '--ntasks=1', '--cpus-per-task=6', '--gres=gpu:1', '--time=30',
                      '--kill-on-bad-exit=1', PYTHON, '-m', 'dojo.main_bounded_srun_worker',
                      str(config_path), str(identity), '--run-id', run_id, '--attempt', '1',
                      '--wall-seconds', '1740', '--max-api-attempts', '40', '--max-output-tokens', '8192']))
        pair_hashes = []
        for i in range(0, len(canonical), 2):
            if canonical[i] != canonical[i+1]:
                raise ValueError('paired actual RunConfigs differ beyond selector and identity')
            pair_hashes.append(hashlib.sha256(encode(canonical[i])).hexdigest())
        write_new(output/'manifest.json', manifest)
        write_new(output/'commands.NOT_EXECUTED.json', commands)
        write_new(output/'runtime.NOT_CREDENTIALS.json', dict(
            PYTHONPATH=str(source/'src') + ':' + str(source/'src/dojo/tasks/mlebench/mle-bench'),
            PYTHON_DOTENV_DISABLED='1', LOGGING_DIR=str(output),
            MLE_BENCH_DATA_DIR=str(data), SUPERIMAGE_DIR=str(images),
            SLURM_CONF='/opt1/slurm/gpu-slurm.conf', NO_PROXY='127.0.0.1,localhost',
            LITELLM_LOCAL_MODEL_COST_MAP='True', OMP_NUM_THREADS='6',
            credential_instruction='Inject remote OPENROUTER_API_KEY as PRIMARY_KEY in worker environment only.'))
        result = dict(status='ACTUAL_RUN_CONFIGS_PREPARED_NOT_EXECUTED',
            declared_source_tree=SOURCE_TREE, upstream_commit=UPSTREAM_COMMIT,
            source_full_tree_rehashed=False, actual_run_configs=rows,
            paired_config_sha256=pair_hashes, run_count=len(rows),
            private_data_contents_read=False, model_loads=0, task_executions=0,
            external_api_calls=0, slurm_dispatches=0,
            remaining=['remote credential installation', 'public-input live endpoint readiness',
                       'bounded critic-service plus worker coordination',
                       'approved two-GPU allocation and actual runtime cost accounting'])
        write_new(output/'prepared.json', result)
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = prepare(args.output)
    print(json.dumps({k: result[k] for k in ('status', 'run_count', 'model_loads',
                                          'task_executions', 'external_api_calls', 'slurm_dispatches')}))


if __name__ == '__main__':
    main()
