"""Run the exact senior G0 launcher through argument construction with a fake accelerate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path('/research/d7/spc/yzyang4')
SOURCE_COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
LAUNCHER_REL = Path('src/mle_critic/scripts/train/pro6000/train_rm_confirmatory_one.sh')
LAUNCHER_SHA = '45c02f177b8760430fa712e76d918c110bd087cda61d1154ad072f319bfa1d7e'
INPUTS = {
    'train': (ROOT/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
              '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
    'dev': (ROOT/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl',
            '3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4'),
    'cards': (ROOT/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
              '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb'),
}
MODEL = ROOT/'cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1'
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def sha(path, scan=False):
    digest = hashlib.sha256()
    tail = b''
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4*1024**2), b''):
            digest.update(block)
            if scan and CREDENTIAL.search(tail+block):
                raise ValueError('credential_shape')
            tail = block[-1024:]
    return digest.hexdigest()


def flag_value(argv, flag):
    positions = [index for index, value in enumerate(argv) if value == flag]
    if len(positions) != 1 or positions[0]+1 >= len(argv):
        raise ValueError('argument_shape_'+flag.lstrip('-'))
    return argv[positions[0]+1]


def verify_argv(argv, output_dir):
    if not argv or argv[0] != 'launch' or any('test' in value.lower() for value in argv):
        raise ValueError('launcher_prefix_or_test_argument')
    expected = {
        '--num_processes': '2', '--max_len': '16384', '--task_cond': 'true',
        '--budget_cond': 'false', '--per_device_train_batch_size': '8',
        '--per_device_eval_batch_size': '8', '--gradient_accumulation_steps': '8',
        '--eval_steps': '10', '--learning_rate': '1e-5', '--num_train_epochs': '1',
        '--max_steps': '10', '--lr_scheduler_type': 'cosine', '--warmup_ratio': '0.03',
        '--output_dir': str(output_dir), '--seed': '6', '--report_to': 'none',
        '--dataloader_num_workers': '0', '--save_strategy': 'best',
        '--load_best_model_at_end': 'false', '--metric_for_best_model': 'eval_pair_accuracy',
        '--greater_is_better': 'true', '--train_pairs': str(INPUTS['train'][0]),
        '--dev_pairs': str(INPUTS['dev'][0]), '--cards': str(INPUTS['cards'][0]),
        '--model': str(MODEL),
    }
    observed = {flag: flag_value(argv, flag) for flag in expected}
    if observed != expected:
        raise ValueError('launcher_argument_mismatch')
    return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    args = parser.parse_args()
    source, scratch = args.source_root.resolve(strict=True), args.scratch_root.absolute()
    if scratch.exists() or source.stat().st_mode & (stat.S_IWUSR|stat.S_IWGRP|stat.S_IWOTH):
        raise ValueError('scratch_exists_or_source_writable')
    launcher = source/LAUNCHER_REL
    if launcher.is_symlink() or not launcher.is_file() or sha(launcher, scan=True) != LAUNCHER_SHA:
        raise ValueError('launcher_source_gate')
    before_commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    before_status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'], text=True).strip()
    if before_commit != SOURCE_COMMIT or before_status or (source/'outputs').exists():
        raise ValueError('source_git_gate')
    for path, expected in INPUTS.values():
        if path.is_symlink() or not path.is_file() or sha(path) != expected:
            raise ValueError('historical_input_gate')
    scratch.mkdir(parents=True, mode=0o700)
    fake_bin = scratch/'fake-bin'
    fake_bin.mkdir(mode=0o700)
    fake_args = scratch/'fake-accelerate-argv.json'
    fake = fake_bin/'accelerate'
    fake.write_text('#!/bin/bash\nprintf \'%s\\n\' "$@" > "$G0_FAKE_ARGS"\n')
    fake.chmod(0o700)
    output_dir, log_path = scratch/'output', scratch/'accelerate.log'
    shared_output, shared_logs = scratch/'shared-env-output', scratch/'shared-env-logs'
    environment = {**os.environ, 'PATH': f'{fake_bin}:/usr/local/bin:/usr/bin:/bin',
        'G0_FAKE_ARGS': str(fake_args), 'MLE_CRITIC_OUTPUT_DIR': str(shared_output),
        'MLE_CRITIC_LOG_DIR': str(shared_logs), 'CONFIRM_TRAIN_PAIRS': str(INPUTS['train'][0]),
        'CONFIRM_DEV_PAIRS': str(INPUTS['dev'][0]), 'CONFIRM_CARDS': str(INPUTS['cards'][0]),
        'CONFIRM_MODEL': str(MODEL), 'CONFIRM_OUTPUT_DIR': str(output_dir),
        'CONFIRM_LOG_PATH': str(log_path), 'CONFIRM_SEED': '6',
        'CONFIRM_PER_DEVICE_TRAIN_BATCH': '8', 'CONFIRM_PER_DEVICE_EVAL_BATCH': '8',
        'CONFIRM_GRAD_ACCUM': '8', 'CONFIRM_NUM_PROCESSES': '2', 'CONFIRM_MAX_LEN': '16384',
        'CONFIRM_EVAL_STEPS': '10', 'CONFIRM_EPOCHS': '1', 'CONFIRM_MAX_STEPS': '10',
        'CONFIRM_LEARNING_RATE': '1e-5', 'CONFIRM_EFFECTIVE_PAIR_BATCH': '128',
        'CONFIRM_LR_SCHEDULER_TYPE': 'cosine', 'CONFIRM_WARMUP_RATIO': '0.03',
        'CONFIRM_G0_FINAL_ONLY': '1', 'CONFIRM_EXPECTED_TRAIN_SHA256': INPUTS['train'][1],
        'CONFIRM_EXPECTED_DEV_SHA256': INPUTS['dev'][1], 'CONFIRM_EXPECTED_CARDS_SHA256': INPUTS['cards'][1],
        'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    completed = subprocess.run(['bash', str(launcher)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, timeout=180, check=False)
    if completed.returncode or completed.stderr or not fake_args.is_file():
        raise RuntimeError('launcher_dry_run_failed')
    argv = fake_args.read_text().splitlines()
    verify_argv(argv, output_dir)
    after_commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    after_status = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'], text=True).strip()
    if after_commit != before_commit or after_status != before_status or (source/'outputs').exists():
        raise ValueError('source_mutated')
    if not shared_output.is_dir() or output_dir.exists():
        raise ValueError('output_isolation_mismatch')
    return {'status': 'G0_EXACT_LAUNCHER_FAKE_ACCELERATE_PASS', 'source_commit': before_commit,
            'source_status_clean': True, 'launcher_sha256': LAUNCHER_SHA,
            'input_sha256': {name: digest for name, (_, digest) in INPUTS.items()},
            'argv_sha256': hashlib.sha256(fake_args.read_bytes()).hexdigest(),
            'stdout_sha256': hashlib.sha256(completed.stdout).hexdigest(), 'stderr_bytes': 0,
            'effective_pair_batch': 128, 'num_processes': 2, 'max_len': 16384,
            'max_steps': 10, 'shared_output_outside_source': True,
            'model_imported': False, 'gpu_jobs': 0, 'model_fits': 0, 'api_calls': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
