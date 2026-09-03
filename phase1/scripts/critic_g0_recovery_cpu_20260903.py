"""CPU-only resolved-argv and real checkpoint-save regression. Never calls train.

Exact launcher argv is captured with an inert accelerate executable. Hardware-only
overrides for the CPU Trainer construction are explicitly reported, not hidden.
The actual distributed training/save path must still pass in the authorized job.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--output-root', type=Path, required=True)
    args = p.parse_args()
    root = args.output_root.resolve()
    root.mkdir(mode=0o700, exist_ok=False)
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert os.environ.get('PYTHONDONTWRITEBYTECODE') == '1'
    source = args.source_root.resolve(strict=True)
    launcher = source / 'src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh'
    bindir = root / 'bin'
    bindir.mkdir()
    fake = bindir / 'accelerate'
    fake.write_text('#!' + sys.executable + '\nimport json,os,sys\n'
                    'with open(os.environ["G0_CAPTURE_ARGV"],"x") as f: json.dump(sys.argv[1:],f)\n')
    fake.chmod(0o700)
    env = dict(os.environ)
    env.update(PATH=str(bindir) + ':' + env['PATH'], MLE_CRITIC_OUTPUT_DIR=str(root / 'unused'),
               CONFIRM_TRAIN_PAIRS='/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
               CONFIRM_DEV_PAIRS='/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl',
               CONFIRM_CARDS='/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
               CONFIRM_MODEL='/research/d7/spc/yzyang4/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1',
               CONFIRM_SEED='6', CONFIRM_PER_DEVICE_TRAIN_BATCH='8', CONFIRM_PER_DEVICE_EVAL_BATCH='8',
               CONFIRM_GRAD_ACCUM='8', CONFIRM_NUM_PROCESSES='2', CONFIRM_MAX_LEN='16384',
               CONFIRM_EVAL_STEPS='10', CONFIRM_EPOCHS='1', CONFIRM_MAX_STEPS='10',
               CONFIRM_LEARNING_RATE='1e-5', CONFIRM_EFFECTIVE_PAIR_BATCH='128',
               CONFIRM_LR_SCHEDULER_TYPE='cosine', CONFIRM_WARMUP_RATIO='0.03',
               CONFIRM_EXPECTED_TRAIN_SHA256='0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e',
               CONFIRM_EXPECTED_DEV_SHA256='3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4',
               CONFIRM_EXPECTED_CARDS_SHA256='5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb')
    cases = []
    for name, mode, steps, eval_steps, expected_rc in (
        ('original', '0', '10', '10', 0), ('recovery', '1', '10', '10', 0),
        ('invalid_steps', '1', '11', '10', 2), ('invalid_eval', '1', '10', '5', 2),
        ('invalid_mode', 'yes', '10', '10', 2),
    ):
        capture = root / (name + '.argv.json')
        runenv = dict(env, CONFIRM_G0_FINAL_ONLY=mode, CONFIRM_MAX_STEPS=steps, CONFIRM_EVAL_STEPS=eval_steps,
                      CONFIRM_OUTPUT_DIR=str(root / (name + '.output')),
                      CONFIRM_LOG_PATH=str(root / (name + '.launcher.log')), G0_CAPTURE_ARGV=str(capture))
        run = subprocess.run(['bash', str(launcher)], env=runenv, capture_output=True, text=True)
        (root / (name + '.stdout')).write_text(run.stdout)
        (root / (name + '.stderr')).write_text(run.stderr)
        assert run.returncode == expected_rc, (name, run.returncode)
        assert capture.exists() == (expected_rc == 0)
        cases.append({'case': name, 'rc': run.returncode})
    original = json.loads((root / 'original.argv.json').read_text())
    recovery = json.loads((root / 'recovery.argv.json').read_text())
    # Paths are the only non-scientific differences besides the explicit reload flag.
    for argv in (original, recovery):
        argv[argv.index('--output_dir') + 1] = 'OUTPUT'
    diffs = [(i, a, b) for i, (a, b) in enumerate(zip(original, recovery)) if a != b]
    assert len(original) == len(recovery) and len(diffs) == 1
    i, old, new = diffs[0]
    assert recovery[i - 1] == '--load_best_model_at_end' and (old, new) == ('true', 'false')
    recovery[recovery.index('--output_dir') + 1] = str(root / 'save_regression')
    trainer_arg_start = recovery.index('--train_pairs')
    sys.path.insert(0, str(source))
    import torch
    from transformers import HfArgumentParser, Trainer
    from src.mle_critic.src.train.config import BradleyTerryConfig
    from src.mle_critic.src.train.bradley_terry import BradleyTerryTrainer, write_checkpoint_metadata
    assert not torch.cuda.is_initialized()
    parser = HfArgumentParser(BradleyTerryConfig)
    parsed = vars(parser.parse_args(recovery[trainer_arg_start:]))
    assert parsed['load_best_model_at_end'] is False and parsed['save_only_model'] is True
    assert parsed['save_strategy'] == 'best' and parsed['max_steps'] == parsed['eval_steps'] == 10
    (root / 'resolved_cli.json').write_text(json.dumps(parsed, sort_keys=True, indent=2, default=str) + '\n')
    # Run the exact installed DeepSpeed/save guard on the complete parsed config.
    framework_path = Path(sys.modules[Trainer.__module__].__file__)
    tree = ast.parse(framework_path.read_text())
    func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'create_accelerator_and_postprocess')
    guards = [n for n in ast.walk(func) if isinstance(n, ast.If) and any(
        isinstance(x, ast.Constant) and isinstance(x.value, str)
        and "can't be used with `save_only_model` along with `load_best_model_at_end`" in x.value
        for child in n.body for x in ast.walk(child))]
    assert len(guards) == 1
    check = compile(ast.Expression(guards[0].test), str(framework_path), 'eval')
    obj = SimpleNamespace(args=SimpleNamespace(**parsed), is_deepspeed_enabled=True, is_fsdp_enabled=False)
    assert not eval(check, {'__builtins__': {}}, {'self': obj})
    obj.args.load_best_model_at_end = True
    assert eval(check, {'__builtins__': {}}, {'self': obj})
    # Actual Trainer init/save/reload with tiny random CPU weights, no data reads/fit.
    cpu_overrides = {'bf16': False, 'use_cpu': True}
    config = BradleyTerryConfig(**dict(parsed, **cpu_overrides))
    model = torch.nn.Linear(2, 1)
    trainer = BradleyTerryTrainer(model=model, args=config, train_dataset=[0], eval_dataset=[0])
    trainer.state.global_step = 10
    trainer.state.max_steps = 10
    improved = trainer._determine_best_metric({'eval_pair_accuracy': 0.5}, None)
    assert improved and trainer.state.best_global_step == 10
    trainer._save_checkpoint(model, None)
    checkpoint = root / 'save_regression/checkpoint-10'
    assert Path(trainer.state.best_model_checkpoint) == checkpoint
    state = json.loads((checkpoint / 'trainer_state.json').read_text())
    assert state['global_step'] == 10 and Path(state['best_model_checkpoint']) == checkpoint
    assert not list(checkpoint.glob('*optim*')) and not list(checkpoint.glob('*scheduler*'))
    from safetensors.torch import load_file
    restored = load_file(checkpoint / 'model.safetensors')
    assert all(torch.equal(restored[k], v) for k, v in model.state_dict().items())
    metadata = {'protocol': 'synthetic-g0-save-regression-only', 'step': 10, 'no_fit': True}
    write_checkpoint_metadata(checkpoint, metadata)
    write_checkpoint_metadata(checkpoint, metadata)
    try:
        write_checkpoint_metadata(checkpoint, dict(metadata, step=11))
    except FileExistsError:
        pass
    else:
        raise AssertionError('metadata overwrite accepted')
    assert not torch.cuda.is_initialized()
    receipt = {'status': 'RESOLVED_ARGV_AND_CPU_CHECKPOINT_REGRESSION_PASS', 'cases': cases,
               'only_scientific_cli_change': {'load_best_model_at_end': [True, False]},
               'cpu_hardware_overrides': cpu_overrides, 'deepspeed_guard_checked': True,
               'distributed_save_validated': False, 'new_model_fits': 0, 'gpu_context_created': False,
               'source_commit': subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
               'launcher_sha256': digest(launcher), 'framework_sha256': digest(framework_path),
               'resolved_cli_sha256': digest(root / 'resolved_cli.json'),
               'checkpoint_roundtrip_equal': True, 'metadata_overwrite_rejected': True}
    (root / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
