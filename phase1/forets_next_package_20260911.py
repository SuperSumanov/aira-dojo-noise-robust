"""CPU-only real RunConfig preparation. Always NOT_READY, no launch commands.

Run in a fresh process on linux5, with the pinned source tar and budget JSON.
The original campaign package and remote production source are never modified.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import sys
import tarfile
import tempfile
from unittest.mock import patch

BASE = Path('/research/d7/spc/yzyang4')
TREE = '3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
UPSTREAM = '065b0fbaa89e0eb663f2834ec768081f5d56394d'
ARCHIVE_SHA = '6f37040627a7a4b0b83b2f2fa5419d4812d00d4e90c74f31e3e3340fbfdc49fd'
PLAN_SHA = '39ac7b7c185f052b4d82508a3c41a019789d54ca1327dff420e599c50b07b915'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
OPS = ('draft', 'improve', 'debug', 'analyze')
TASKS = ('leaf-classification', 'spaceship-titanic')
POLICIES = ('uniform_random', 'critic_topk_random')
PHASE = 'not_started'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    if SECRET.search(raw): raise ValueError('credential_shaped_artifact')
    with path.open('xb') as stream: stream.write(raw)
    return sha(raw)


def safe_cpu_guard():
    os.umask(0o077)
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHON_DOTENV_DISABLED='1',
                      LITELLM_LOCAL_MODEL_COST_MAP='True', HF_HUB_OFFLINE='1',
                      TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1', OMP_NUM_THREADS='1')
    for key in tuple(os.environ):
        if key.startswith('PRIMARY_KEY') or key in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(key)
    forbidden = [BASE/'mle-bench-data', BASE/'prospective_decision_v1',
                 BASE/'forets-critic-incoming-20260908-3lcjjcwq']
    def audit(event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.sendto', 'subprocess.Popen', 'os.system', 'os.posix_spawn'):
            raise RuntimeError('CPU_prepare_forbids_network_or_process_dispatch')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).absolute()
            if path.name == '.env' or path.name.startswith('.env.') or path.name == 'env_variables.json':
                raise RuntimeError('credential_file_open_forbidden')
            if any(path.is_relative_to(root) for root in forbidden):
                raise RuntimeError('data_model_or_protected_file_open_forbidden')
    sys.addaudithook(audit)
    class NoModelImports:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in ('torch', 'transformers', 'safetensors'):
                raise ImportError('model_framework_import_forbidden_during_config_prepare')
    sys.meta_path.insert(0, NoModelImports())
    def timeout(*_): raise TimeoutError('bounded_CPU_preparation')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(180)


def materialize(stage, output):
    raw = (stage/'source.tar').read_bytes()
    if sha(raw) != ARCHIVE_SHA: raise ValueError('source_archive_drift')
    files, total = {}, 0
    source = output/'source'; source.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            rel = PurePosixPath(member.name)
            if rel.is_absolute() or '..' in rel.parts or '\\' in member.name:
                raise ValueError('unsafe_source_path')
            if member.isdir(): continue
            if not member.isfile() or not any(rel.is_relative_to(p) for p in ('src/aira_core', 'src/dojo')):
                raise ValueError('source_member_outside_code_scope')
            if member.name in files or member.size > 2**20: raise ValueError('source_member_size_or_duplicate')
            total += member.size
            if total > 2**21: raise ValueError('source_total_size')
            with archive.extractfile(member) as stream: payload = stream.read()
            if SECRET.search(payload): raise ValueError('credential_shaped_source')
            dest = source/rel; dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open('xb') as stream: stream.write(payload)
            files[member.name] = sha(payload)
    if len(files) != 231 or total != 965902: raise ValueError('source_inventory_changed')
    return source, files


def overrides(row):
    from forets_pilot_plan import free_route_overrides, bounded_launcher_overrides
    task, seed, policy = row['task'], row['seed'], row['arm']
    if task not in TASKS or seed not in (8, 9) or policy not in POLICIES: raise ValueError('matrix_changed')
    values = ['+_exp=mlebench/aira_forets_dsf_mle', 'benchmark.tasks=['+task+']',
              'launcher=srun_pool', 'launcher.max_parallel=1', 'launcher.gpus_per_step=1',
              'launcher.cpus_per_step=6', 'launcher.debug=false', 'launcher.max_retries=0',
              'logger.use_wandb=false', 'solver.selection_policy='+policy,
              'solver.selector_seed='+str(seed), '++solver.selection_coupling=common_priority_v1',
              'solver.num_children=4', 'solver.critic_top_k=2', 'solver.num_children_to_choose=1',
              'solver.execution_timeout=300', 'solver.time_limit_secs=3600', 'solver.step_limit=6',
              'solver.max_debug_depth=1', 'solver.max_llm_call_retries=2', 'solver.critic_max_attempts=1',
              'metadata.git_issue_id=forets-next-config-draft-20260911', 'metadata.seed='+str(seed),
              'vars={metadata.seed:['+str(seed)+']}']
    values += bounded_launcher_overrides(max_api_attempts=100, max_output_tokens=8192,
                                         step_minutes=60, worker_wall_seconds=3540)
    values += free_route_overrides('litellm_nemotron-3-ultra')
    for op in OPS:
        prefix = '++solver.operators.'+op+'.llm.generation_kwargs.'
        values += [prefix+'max_tokens=8192', prefix+'bounded_request_timeout_seconds=120',
                   prefix+'bounded_max_attempts=3']
    return values


def prepare(stage):
    global PHASE
    PHASE = 'source_and_plan'
    plan_raw = (stage/'next-budget.json').read_bytes()
    if sha(plan_raw) != PLAN_SHA: raise ValueError('plan_drift')
    plan = json.loads(plan_raw)
    if plan['status'] != 'DRAFT_NOT_SUBMITTABLE' or len(plan['matrix']) != 8: raise ValueError('plan_scope')
    output = Path(tempfile.mkdtemp(prefix='forets-next-config-20260911-', dir=BASE))
    source, source_files = materialize(stage, output)
    data, images = BASE/'mle-bench-data', BASE/'aira-dojo/build/superimage'
    image = images/'superimage.root.2026-07-macos-v1.sif'
    if not image.is_file(): raise ValueError('original_image_missing')
    for task in TASKS:
        for split in ('public', 'private'):
            if not (data/task/'prepared'/split).is_dir(): raise ValueError('prepared_directory_missing')
    for name in ('configs', 'overrides', 'runs', 'launchers'): (output/name).mkdir()
    os.environ.update(LOGGING_DIR=str(output), MLE_BENCH_DATA_DIR=str(data), SUPERIMAGE_DIR=str(images),
                      DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(source/'src'))
    PHASE = 'import_config_classes'
    import dotenv
    with patch.object(dotenv, 'load_dotenv', return_value=False):
        from hydra import compose, initialize_config_dir
        from hydra.utils import instantiate
        from omegaconf import OmegaConf
        from dojo.config_dataclasses.run import RunConfig
        from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
        from forets_e2e_package import common_config
        register_new_resolvers()
        records, normalized, launchers = [], [], []
        for index, row in enumerate(plan['matrix']):
            PHASE = 'compose_config_'+str(index)
            run_id = f"{index:02d}-{row['task']}-s{row['seed']}-{row['arm']}"
            run_dir = output/'runs'/run_id
            ov = overrides(row) + ['++metadata.git_commit_id='+UPSTREAM,
                '++metadata.description=upstream-plus-patches-tree-'+TREE,
                '++metadata.launch_time=prepared-not-started', '++metadata.base_path='+str(source),
                '++metadata.user=yzyang4', '++logger.output_dir='+str(run_dir), 'logger.print_config=false',
                'interpreter.superimage_directory='+str(images), 'interpreter.superimage_version=2026-07-macos-v1']
            with initialize_config_dir(config_dir=str(source/'src/dojo/configs'), version_base=None):
                runner = instantiate(compose(config_name='default_runner', overrides=ov))
            tasks = runner.benchmark.to_cfg_list()
            if len(tasks) != 1 or tasks[0].name != row['task']: raise ValueError('unexpected_task')
            cfg = RunConfig(id=run_id, meta_id='forets-next-config-draft-20260911',
                logger=runner.logger, metadata=runner.metadata, task=tasks[0], solver=runner.solver,
                interpreter=runner.interpreter)
            resolved = OmegaConf.structured(cfg); OmegaConf.resolve(resolved); cfg = OmegaConf.to_object(resolved)
            cfg.validate(); typed = cfg.to_typed_dict()
            recovered = RunConfig.from_dict(typed); recovered.validate()
            if recovered.to_typed_dict() != typed: raise ValueError('roundtrip_changed_config')
            if cfg.solver.selection_coupling != 'common_priority_v1' or cfg.solver.step_limit != 6:
                raise ValueError('new_selector_or_budget_not_in_real_config')
            if cfg.logger.write_env_vars or cfg.logger.use_wandb or cfg.solver.use_test_score or cfg.solver.skip_redundant_critic:
                raise ValueError('forbidden_or_changed_settings')
            config_sha = write_new(output/'configs'/(run_id+'.json'), typed)
            write_new(output/'overrides'/(run_id+'.json'), ov)
            normalized.append(common_config(typed, run_id=run_id, run_dir=run_dir))
            launcher = OmegaConf.to_container(OmegaConf.structured(runner.launcher), resolve=True)
            launcher_obj = OmegaConf.to_object(OmegaConf.structured(runner.launcher)); launcher_obj.validate()
            launchers.append(launcher)
            records.append(dict(run_id=run_id, **row, config_sha256=config_sha,
                                roundtrip=True, concrete_solver_type=type(recovered.solver).__name__))
    PHASE = 'verify_and_write_draft'
    if any(normalized[i] != normalized[i+1] for i in range(0, 8, 2)):
        raise ValueError('pair_diff_beyond_selection_and_identity')
    if any(item != launchers[0] for item in launchers): raise ValueError('launcher_budget_differs')
    for block in (1, 2): write_new(output/'launchers'/f'block-{block}.json', launchers[0])
    # Deliberately incompatible with the old campaign's execution-role gate.
    manifest = dict(role='forets_e2e_config_draft_not_launchable', source_tree=TREE, runs=records)
    write_new(output/'manifest.json', manifest)
    write_new(output/'source-files.json', source_files)
    result = dict(status='ACTUAL_CONFIGS_VERIFIED_NOT_READY', output=str(output), source_tree=TREE,
        preparation_files_sha256={name:sha((Path(__file__).parent/name).read_bytes()) for name in
            ('forets_next_package_20260911.py', 'forets_pilot_plan.py', 'forets_e2e_package.py')},
        source_archive_sha256=ARCHIVE_SHA, plan_sha256=PLAN_SHA, run_count=len(records), paired_configs=4,
        selection_coupling='common_priority_v1', step_limit=6, blocks=2, nominal_gpu_hours=17.0,
        run_configs=records, paired_config_sha256=[sha(json.dumps(normalized[i], sort_keys=True).encode()) for i in range(0,8,2)],
        launcher=launchers[0], source_files=len(source_files), private_or_public_data_contents_read=False,
        model_framework_imports=0, model_loads=0, api_requests=0, slurm_dispatches=0,
        original_image_changed=False, launch_commands_written=False, source_production_changed=False,
        checkpoint_training_template='UNRESOLVED_NO_RENDERING_OVERRIDE', readiness=False,
        remaining=['supported OpenCL allocation isolation', 'checkpoint historical training template',
                   'new bounded campaign controller matched to this matrix', 'fresh fixed-route readiness within explicit budget'])
    write_new(output/'prepared.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--stage', type=Path, required=True)
    args = p.parse_args()
    safe_cpu_guard()
    try:
        value = prepare(args.stage)
        print(json.dumps(value, sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status':'CONFIG_PREPARE_FAILED_CLOSED', 'phase':PHASE,
                          'error_types':[type(exc).__name__, type(exc.__cause__).__name__] if exc.__cause__ else [type(exc).__name__]}))
        raise SystemExit(1)
