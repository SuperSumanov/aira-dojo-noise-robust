"""Independent stdlib-only verification of the non-launchable real config draft."""
import argparse
import ast
import copy
import datetime as dt
import hashlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

TREE = '3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'
ARCHIVE_SHA = '6f37040627a7a4b0b83b2f2fa5419d4812d00d4e90c74f31e3e3340fbfdc49fd'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def h(raw): return hashlib.sha256(raw).hexdigest()


def load(path):
    raw = path.read_bytes()
    if len(raw) > 2**21 or SECRET.search(raw): raise ValueError('unsafe_config_or_receipt')
    return json.loads(raw), h(raw)


def get(cfg, path):
    for key in path: cfg = cfg[key]
    return cfg


def differences(a, b, path=()):
    if type(a) != type(b): return [path]
    if isinstance(a, dict):
        if set(a) != set(b): return [path + ('<keys>',)]
        return sum((differences(a[k], b[k], path+(k,)) for k in sorted(a)), [])
    if isinstance(a, list):
        if len(a) != len(b): return [path + ('<length>',)]
        return sum((differences(x, y, path+(str(i),)) for i, (x,y) in enumerate(zip(a,b))), [])
    return [] if a == b else [path]


def verify_config(cfg, row, root):
    wanted = {('id',):row['run_id'], ('metadata','seed'):row['seed'], ('task','name'):row['task'],
        ('solver','selector_seed'):row['seed'], ('solver','selection_policy'):row['arm'],
        ('solver','selection_coupling'):'common_priority_v1', ('solver','num_children'):4,
        ('solver','critic_top_k'):2, ('solver','num_children_to_choose'):1, ('solver','step_limit'):6,
        ('solver','execution_timeout'):300, ('solver','time_limit_secs'):3600,
        ('solver','max_debug_depth'):1, ('solver','max_llm_call_retries'):2, ('solver','critic_max_attempts'):1,
        ('solver','skip_redundant_critic'):False, ('solver','use_test_score'):False,
        ('logger','write_env_vars'):False, ('logger','use_wandb'):False,
        ('metadata','launch_time'):'prepared-not-started'}
    for path, expected in wanted.items():
        value=get(cfg,path)
        if type(value) != type(expected) or value != expected: raise ValueError('explicit_setting_mismatch')
    if cfg['solver']['_dojo_dataclass_type'] != 'dojo.config_dataclasses.solver.fore_ts:ForeTSSolverConfig':
        raise ValueError('concrete_solver_type_lost')
    for op in ('draft','improve','debug','analyze'):
        llm=cfg['solver']['operators'][op]['llm']; kw=llm['generation_kwargs']
        if llm['client']['model_id'] != 'nvidia/nemotron-3-ultra-550b-a55b:free': raise ValueError('model_changed')
        expected={'max_tokens':8192,'bounded_request_timeout_seconds':120,'bounded_max_attempts':3,
                  'bounded_transport':True,'bounded_run_budget_required':True,'structured_output_retries':0}
        for k,v in expected.items():
            if type(kw[k]) != type(v) or kw[k] != v: raise ValueError('request_budget_changed')
        if kw['extra_body']['provider'] != {'allow_fallbacks':False,'require_parameters':True,
                                          'max_price':{'prompt':0,'completion':0,'request':0}}:
            raise ValueError('provider_constraint_changed')
    run=root/'runs'/row['run_id']
    if cfg['logger']['output_dir'] != str(run) or cfg['solver']['exp_name'] != row['run_id']:
        raise ValueError('run_identity_path_changed')
    for path in (('solver','checkpoint_path'),('interpreter','working_dir'),('task','results_output_dir')):
        if not Path(get(cfg,path)).is_relative_to(run): raise ValueError('mechanical_path_outside_run')
    if cfg['interpreter']['superimage_version'] != '2026-07-macos-v1': raise ValueError('image_changed')


def verify(root, stage):
    prepared, prepared_sha=load(root/'prepared.json'); manifest, manifest_sha=load(root/'manifest.json')
    if prepared['readiness'] is not False or manifest['role'] != 'forets_e2e_config_draft_not_launchable':
        raise ValueError('draft_readiness_changed')
    if prepared['source_tree'] != TREE or manifest['source_tree'] != TREE: raise ValueError('source_declaration')
    raw=(stage/'source.tar').read_bytes()
    if h(raw) != ARCHIVE_SHA: raise ValueError('archive_changed')
    code_files=0
    with tarfile.open(stage/'source.tar') as archive:
        for member in archive:
            if not member.isfile(): continue
            rel=PurePosixPath(member.name)
            if rel.is_absolute() or '..' in rel.parts: raise ValueError('source_member')
            with archive.extractfile(member) as f: expected=f.read()
            if (root/'source'/rel).read_bytes() != expected: raise ValueError('materialized_source_changed')
            code_files+=1
    if code_files != 231: raise ValueError('source_inventory')
    expected_rows=[]
    for block,seed in enumerate((8,9),1):
        for task_index,task in enumerate(('leaf-classification','spaceship-titanic')):
            arms=['uniform_random','critic_topk_random']
            if (block-1+task_index)%2: arms.reverse()
            for arm in arms: expected_rows.append((block,task,seed,arm))
    rows=manifest['runs']
    if [(r['block'],r['task'],r['seed'],r['arm']) for r in rows] != expected_rows: raise ValueError('matrix_changed')
    configs=[]
    for i,row in enumerate(rows):
        if row['run_id'] != f"{i:02d}-{row['task']}-s{row['seed']}-{row['arm']}": raise ValueError('run_id_changed')
        cfg,digest=load(root/'configs'/(row['run_id']+'.json'))
        if digest != row['config_sha256']: raise ValueError('config_hash_drift')
        verify_config(cfg,row,root); configs.append(cfg)
    allowed={('id',),('interpreter','working_dir'),('logger','output_dir'),('solver','checkpoint_path'),
             ('solver','exp_name'),('solver','selection_policy'),('task','results_output_dir')}
    observed=[]
    for i in range(0,8,2):
        diff=differences(configs[i],configs[i+1])
        if set(diff) != allowed: raise ValueError('pair_has_unexpected_difference')
        # Differences at mechanical paths must be exactly the declared identity replacement.
        for path in allowed-{('solver','selection_policy')}:
            if get(configs[i],path).replace(rows[i]['run_id'],rows[i+1]['run_id']) != get(configs[i+1],path):
                raise ValueError('nonmechanical_path_difference')
        observed.append(['.'.join(p) for p in sorted(diff)])
    launchers=[]
    for block in (1,2):
        cfg,_=load(root/'launchers'/f'block-{block}.json')
        for k,v in {'step_time_limit_minutes':60,'worker_wall_seconds':3540,'forets_max_api_attempts':100,
                    'forets_max_output_tokens':8192,'max_parallel':1,'gpus_per_step':1,'cpus_per_step':6,
                    'max_retries':0,'min_remaining_seconds_to_launch':3930}.items():
            if type(cfg[k]) != type(v) or cfg[k] != v: raise ValueError('launcher_cap_changed')
        launchers.append(cfg)
    if launchers[0] != launchers[1]: raise ValueError('different_block_budgets')
    # Load only the old validation function, never execute()/credential installation.
    source=(stage/'forets_e2e_campaign.py').read_bytes()
    if SECRET.search(source): raise ValueError('unsafe_old_validator_source')
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='validate_inputs')
    env=dict(json=json, SOURCE_TREE='bbd22e323d6321925a145c12bdc02445c1ad80f4')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<old-validator-only>','exec'),env)
    try: env['validate_inputs'](root)
    except ValueError as e:
        if str(e) != 'not the prepared development package': raise
    else: raise ValueError('old_campaign_did_not_reject_new_draft')
    negative_cases=[]
    for path,value in [(('metadata','seed'),123),(('solver','step_limit'),8),
                       (('solver','selection_coupling'),'independent_subset_v2'),
                       (('solver','operators','draft','llm','generation_kwargs','max_tokens'),9000)]:
        changed=copy.deepcopy(configs[0]); get(changed,path[:-1])[path[-1]]=value
        try: verify_config(changed,rows[0],root)
        except ValueError: negative_cases.append('.'.join(path))
        else: raise ValueError('negative_control_not_rejected')
    result=dict(status='INDEPENDENT_CONFIG_CHECK_PASSED_NOT_READY',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        package=str(root),source_tree=TREE,prepared_sha256=prepared_sha,manifest_sha256=manifest_sha,
        source_files_compared=code_files,run_configs_checked=len(configs),paired_configs_checked=len(observed),
        pair_difference_paths=observed,old_campaign_validator_rejected=True,negative_controls_rejected=negative_cases,
        verifier_sha256=h(Path(__file__).read_bytes()),model_loads=0,api_requests=0,slurm_dispatches=0,
        readiness=False,python=sys.version.split()[0],
        package_versions={k:importlib.metadata.version(k) for k in ('hydra-core','omegaconf','python-dotenv')})
    raw=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
    if SECRET.search(raw): raise ValueError('unsafe_public_receipt')
    with (root/'independent-verification.json').open('xb') as f: f.write(raw)
    print(raw.decode())


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--stage',type=Path,required=True)
    args=p.parse_args()
    try: verify(args.root,args.stage)
    except Exception as exc:
        print(json.dumps({'status':'INDEPENDENT_CONFIG_CHECK_FAILED_CLOSED','error_type':type(exc).__name__}))
        raise SystemExit(1)
