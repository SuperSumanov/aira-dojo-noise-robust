from pathlib import Path

import pytest

from phase1.g0_launcher_fake_accelerate_smoke import (
    INPUTS, MODEL, flag_value, normalized_argv_digest, verify_argv,
)


def valid_argv(output):
    pairs = {
        '--num_processes': '2', '--max_len': '16384', '--task_cond': 'true',
        '--budget_cond': 'false', '--per_device_train_batch_size': '8',
        '--per_device_eval_batch_size': '8', '--gradient_accumulation_steps': '8',
        '--eval_steps': '10', '--learning_rate': '1e-5', '--num_train_epochs': '1',
        '--max_steps': '10', '--lr_scheduler_type': 'cosine', '--warmup_ratio': '0.03',
        '--output_dir': str(output), '--seed': '6', '--report_to': 'none',
        '--dataloader_num_workers': '0', '--save_strategy': 'best',
        '--load_best_model_at_end': 'false', '--metric_for_best_model': 'eval_pair_accuracy',
        '--greater_is_better': 'true', '--train_pairs': str(INPUTS['train'][0]),
        '--dev_pairs': str(INPUTS['dev'][0]), '--cards': str(INPUTS['cards'][0]),
        '--model': str(MODEL)}
    argv = ['launch']
    for key, value in pairs.items():
        argv.extend([key, value])
    return argv


def test_exact_argument_contract():
    output = Path('/tmp/example/output')
    result = verify_argv(valid_argv(output), output)
    assert result['--num_processes'] == '2' and result['--max_len'] == '16384'


def test_duplicate_missing_and_test_arguments_fail():
    output = Path('/tmp/example/output')
    argv = valid_argv(output)
    with pytest.raises(ValueError):
        flag_value(argv+['--seed', '7'], '--seed')
    missing = argv.copy()
    index = missing.index('--max_steps')
    del missing[index:index+2]
    with pytest.raises(ValueError):
        verify_argv(missing, output)
    with pytest.raises(ValueError):
        verify_argv(argv+['--test_pairs', '/tmp/heldout.jsonl'], output)


def test_normalized_hash_ignores_only_scratch_prefix():
    left = ['launch', '--output_dir', '/tmp/a/output', '--seed', '6']
    right = ['launch', '--output_dir', '/tmp/b/output', '--seed', '6']
    assert normalized_argv_digest(left, '/tmp/a') == normalized_argv_digest(right, '/tmp/b')
    changed = ['launch', '--output_dir', '/tmp/b/output', '--seed', '7']
    assert normalized_argv_digest(left, '/tmp/a') != normalized_argv_digest(changed, '/tmp/b')
