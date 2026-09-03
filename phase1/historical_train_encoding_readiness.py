"""Offline, train-only encoding check; never constructs or fits a model.

The released grouped Cards JSON must be parsed, but only the approved train
endpoints' code/task fields are retained. No dev/test/vault file is opened.
Output contains aggregates and anonymous length records, not programs or labels.
This is an input-interface test, not a new scientific training protocol.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time

BASE = Path('/research/d7/spc/yzyang4')
TRAIN = BASE / 'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl'
CARDS = BASE / 'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json'
SOURCE = BASE / 'worktrees/critic-g0-final-only-20260903-b/src/mle_critic/src/train/dataset/pairs.py'
CONFIG = BASE / 'critic-component-g0/recovery-20260903-r2/cpu_regression/resolved_cli.json'
MODEL = BASE / 'cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1'
TRANSFORMERS_PACKAGE = BASE / 'venvs/critic-blackwell-g0-20260903-selective/lib/python3.11/site-packages/transformers'
EXPECTED = {
    TRAIN: '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e',
    CARDS: '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb',
    SOURCE: '3e1969499405199a187c12106d9f4d4a5542b4a1ecf094e0bd9f7c71514b4643',
    CONFIG: 'ec0ed931e9ace64925451a4792922110253f642462a0f3d732063c07d8af0475',
    MODEL / 'tokenizer.json': 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539',
    MODEL / 'tokenizer_config.json': '3c04ed3ca964ea2f6b2b5faf0dc4d31aec1cb1e8b4bcf63f402d295046b422b5',
    MODEL / 'vocab.json': 'ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910',
    MODEL / 'merges.txt': '8831e4f1a044471340f7c0a83d7bd71306a5b867e95fd870f74d0c5308a904d5',
    MODEL / 'config.json': '1bb33a92c3548fbc68b889b490e810440435253598835bd71dff0396060c12db',
}
ENCODER_CONFIG = dict(max_len=16384, head_frac=0.25, task_cond=True,
                      budget_cond=False, budget_pos='head')
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})(?![A-Za-z0-9])')


def checked_digest(path, expected=None, scan=False):
    h, tail, hit = hashlib.sha256(), b'', False
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
            if scan:
                hit |= CREDENTIAL.search(tail + block) is not None
                tail = block[-1024:]
    if hit:
        raise ValueError('credential_shape_hit_no_content_disclosed')
    if expected is not None and h.hexdigest() != expected:
        raise ValueError('immutable_asset_hash_mismatch')
    return h.hexdigest()


def independent_encode(code, task, tokenizer, *, max_len=16384, head_frac=0.25):
    """Independent fixed-G0 reference, not a general replacement serializer."""
    if not isinstance(task, str) or not task or not isinstance(code, str):
        raise ValueError('invalid_encoder_input')
    if type(max_len) is not int or max_len < 2 or not 0 < head_frac < 1:
        raise ValueError('invalid_truncation_contract')
    raw = list(tokenizer('# MLE-bench task: ' + task + '\n' + code,
                         add_special_tokens=False)['input_ids'])
    if not raw:
        raise ValueError('empty_encoding')
    prefix = int(max_len * head_frac)
    encoded = raw if len(raw) <= max_len else raw[:prefix] + raw[len(raw) - (max_len - prefix):]
    return tuple(encoded), len(raw)


def train_rows(path):
    rows, seen = [], set()
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                raise ValueError('blank_train_row')
            x = json.loads(line)
            if x.get('intask_split') != 'train':
                raise ValueError('non_train_row')
            a, b = x['better'], x['worse']
            if not all(isinstance(v, str) and v for v in (a, b)) or a == b:
                raise ValueError('invalid_train_endpoints')
            # Budget is identity metadata even though this G0 does not encode it.
            budget = x.get('budget')
            if budget is not None and (type(budget) is not int or budget < 0):
                raise ValueError('invalid_budget')
            key = (*sorted((a, b)), budget)
            if key in seen:
                raise ValueError('duplicate_train_pair')
            seen.add(key)
            rows.append((a, b, budget))
    if not rows:
        raise ValueError('empty_train_pool')
    return rows


def extract_train_inputs(grouped, needed):
    if not isinstance(grouped, dict):
        raise ValueError('invalid_grouped_cards')
    code, task, runs, seen = {}, {}, {}, set()
    for run, cards in grouped.items():
        if not isinstance(run, str) or not run or not isinstance(cards, list):
            raise ValueError('invalid_cards_run')
        for card in cards:
            cid = card['id']
            if not isinstance(cid, str) or not cid or cid in seen:
                raise ValueError('invalid_or_duplicate_card_identity')
            seen.add(cid)
            if cid not in needed:
                continue
            c, t = card['code'], card['task']['name']
            if not isinstance(c, str) or not isinstance(t, str) or not t:
                raise ValueError('invalid_train_card_fields')
            code[cid], task[cid], runs[cid] = c, t, run
    if set(code) != needed:
        raise ValueError('missing_train_endpoint')
    return code, task, runs, len(seen)


def install_access_guard(output):
    """Python audit hook; not an OS sandbox or proof about native syscalls."""
    allowed = {p.resolve() for p in EXPECTED}
    library_root = TRANSFORMERS_PACKAGE.resolve()
    opens, denied = Counter(), Counter()
    protected = ('prospective', 'first-960', 'first960', 'target-300', 'target300',
                 'target-522', 'target522', 'vault', 'escrow')
    def hook(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            denied['network_or_subprocess'] += 1
            raise PermissionError('offline_no_subprocess_contract')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).absolute()
        low = str(p).lower()
        if p.is_relative_to(output):
            return
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            denied['write_outside_output'] += 1
            raise PermissionError('write_outside_output')
        # Transformers scans Python modules named vaultgemma during lazy-import
        # setup. Library source is not a data vault; permit this exact package's
        # read-only Python files, requiring both lexical and resolved containment.
        if (p.is_relative_to(TRANSFORMERS_PACKAGE) and p.resolve().is_relative_to(library_root)
                and p.suffix in ('.py', '.pyc')):
            return
        if (any(s in low for s in protected) or p.name in ('dev.jsonl', 'test.jsonl')
                or p.suffix in ('.safetensors', '.pt', '.bin')):
            denied['forbidden_data_or_weights'] += 1
            raise PermissionError('forbidden_data_or_weights')
        resolved = p.resolve()
        if resolved in allowed:
            opens[str(p)] += 1
        elif (('/worktrees/' in low and '/data/' in low) or 'component-prep/' in low) and str(BASE) in low:
            denied['unlisted_research_data'] += 1
            raise PermissionError('unlisted_research_data')
    sys.addaudithook(hook)
    return opens, denied


def run(output, limit_seconds):
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '' or os.environ.get('HF_HUB_OFFLINE') != '1':
        raise ValueError('offline_cpu_environment_required')
    if output.exists() or not output.is_relative_to(Path('/tmp')):
        raise ValueError('new_tmp_output_required')
    output.mkdir(mode=0o700)
    os.environ['TMPDIR'] = str(output)
    started = time.monotonic()
    opens, denied = install_access_guard(output)
    def stage(name):
        (output / 'stage.json').write_text(json.dumps({'stage': name}))
    stage('asset_hash_and_credential_gate')
    assets = {str(p): checked_digest(p, sha, scan=p in (TRAIN, CARDS)) for p, sha in EXPECTED.items()}
    cfg = json.loads(CONFIG.read_text())
    if any(cfg[k] != v for k, v in ENCODER_CONFIG.items()):
        raise ValueError('encoder_config_drift')
    stage('historical_train_input_extraction')
    rows = train_rows(TRAIN)
    if len(rows) != 4689:
        raise ValueError('unexpected_train_rows')
    needed = {c for a, b, _ in rows for c in (a, b)}
    code, tasks, runs, n_all = extract_train_inputs(json.loads(CARDS.read_text()), needed)
    stage('offline_runtime_import')
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise ValueError('cuda_context_forbidden')
    stage('offline_tokenizer_load')
    tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True, trust_remote_code=False)
    tok.model_max_length = 10**9  # silence warning, no token truncation requested
    spec = importlib.util.spec_from_file_location('bound_historical_pairs', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    encoder = module.CardEncoder(code, tasks, tok, **ENCODER_CONFIG)
    stage('real_train_encoding')
    encoded, records = {}, []
    for index, cid in enumerate(sorted(needed)):
        if time.monotonic() - started > limit_seconds:
            raise TimeoutError('bounded_input_check_expired')
        expected, raw_n = independent_encode(code[cid], tasks[cid], tok)
        actual = tuple(encoder(cid))
        if actual != expected or tuple(encoder(cid, 19)) != actual:
            raise ValueError('source_reference_or_disabled_budget_mismatch')
        encoded[cid] = actual
        digest = hashlib.sha256(json.dumps(actual, separators=(',', ':')).encode()).hexdigest()
        records.append((index, raw_n, len(actual), digest))
        if index % 250 == 0:
            (output / 'progress.json').write_text(json.dumps({'endpoints_done': index + 1,
                'endpoints_total': len(needed), 'elapsed_seconds': time.monotonic() - started}))
    # Actual source collator vs independently constructed canonical A/B inputs.
    # Read-order preserved only for this packing test, NOT a proposed training order.
    stage('actual_collator_comparison')
    total_valid, total_padded, batches, flipped = 0, 0, 0, 0
    for offset in range(0, len(rows), 8):
        part = rows[offset:offset + 8]
        old = module.pair_collate([{'b': list(encoded[a]), 'w': list(encoded[b])}
                                  for a, b, _ in part], tok.pad_token_id)
        n = len(part)
        canonical = [sorted((a, b)) for a, b, _ in part]
        width = max(len(encoded[c]) for pair in canonical for c in pair)
        values = [encoded[pair[side]] for side in (0, 1) for pair in canonical]
        new_ids = torch.tensor([v + (tok.pad_token_id,) * (width - len(v)) for v in values])
        new_mask = torch.tensor([(1,) * len(v) + (0,) * (width - len(v)) for v in values])
        permutation = []
        for side in (0, 1):
            for j, (a, b, _) in enumerate(part):
                permutation.append(j if canonical[j][side] == a else n + j)
        if not torch.equal(old['input_ids'][permutation], new_ids) or not torch.equal(old['attention_mask'][permutation], new_mask):
            raise ValueError('actual_collator_canonical_mismatch')
        total_valid += int(new_mask.sum())
        total_padded += new_ids.numel()
        batches += 1
        flipped += sum(a > b for a, b, _ in part)
    with (output / 'endpoint_lengths.csv').open('x', newline='') as f:
        w = csv.writer(f); w.writerow(('ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256')); w.writerows(records)
    raw_lengths, lengths = [r[1] for r in records], [r[2] for r in records]
    shapes = []
    for world, per_rank, acc in ((2, 8, 8), (4, 8, 4)):
        effective = world * per_rank * acc
        q, rem = divmod(len(rows), effective)
        shapes.append({'world_size': world, 'pairs_per_rank': per_rank, 'accumulation': acc,
            'effective_pairs': effective, 'complete_steps': q, 'remaining_pairs': rem,
            'strict_once_through_plan_admissible': rem == 0})
    if torch.cuda.is_initialized() or denied:
        raise ValueError('scope_violation')
    result = {'status': 'PASS_INPUT_EQUIVALENCE_NOT_TRAINING_READY',
        'source_commit': '5f3bc362db922c8edee2ef134656dfdb9a2b74fb',
        'assets': assets, 'script_sha256': checked_digest(__file__), 'encoder_config': ENCODER_CONFIG,
        'train_pairs': len(rows), 'train_endpoints': len(needed), 'released_cards_parsed': n_all,
        'train_physical_runs': len(set(runs.values())), 'train_tasks': len(set(tasks.values())),
        'truncated_unique_endpoints': sum(n > 16384 for n in raw_lengths),
        'raw_length_min': min(raw_lengths), 'raw_length_median': statistics.median(raw_lengths), 'raw_length_max': max(raw_lengths),
        'encoded_unique_valid_tokens': sum(lengths), 'encoded_pair_visit_valid_tokens': total_valid,
        'file_order_microbatches': batches, 'file_order_padded_slots': total_padded,
        'canonical_flipped_pairs': flipped, 'packing_microbatch_pairs': 8,
        'source_reference_comparisons': len(needed), 'source_collator_comparisons': batches,
        'candidate_shapes_not_authorized': shapes,
        'endpoint_length_sha256': checked_digest(output / 'endpoint_lengths.csv'),
        'read_scope': 'historical released grouped Cards parsed; only train endpoint code/task/run retained; train orientation only for packing equivalence',
        'data_open_counts': dict(opens), 'denied_attempts': dict(denied),
        'audit_hook_is_not_os_sandbox': True, 'gpu_context_created': False, 'model_weights_loaded': 0,
        'model_fits': 0, 'api_calls': 0, 'dev_test_vault_files_opened': 0,
        'torch_version': torch.__version__, 'tokenizer_class': type(tok).__name__,
        'wall_seconds_not_throughput_benchmark': time.monotonic() - started}
    # Recheck immutable inputs after use (hash only; no second content parsing).
    for p, sha in EXPECTED.items():
        checked_digest(p, sha)
    (output / 'summary.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    stage('completed')
    print(json.dumps({k: result[k] for k in ('status', 'train_pairs', 'train_endpoints', 'truncated_unique_endpoints', 'candidate_shapes_not_authorized')}, sort_keys=True))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--limit-seconds', type=int, default=1200)
    args = p.parse_args()
    if not 1 <= args.limit_seconds <= 1200:
        raise ValueError('bounded_runtime_required')
    try:
        run(args.output_root.resolve(), args.limit_seconds)
    except Exception as exc:
        # Neither exception strings nor traceback can disclose dataset values.
        safe_reasons = {'offline_no_subprocess_contract', 'forbidden_data_or_weights',
                        'unlisted_research_data', 'write_outside_output',
                        'immutable_asset_hash_mismatch', 'credential_shape_hit_no_content_disclosed'}
        reason = str(exc) if str(exc) in safe_reasons else 'details_withheld'
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__,
                          'safe_reason': reason}), flush=True)
        raise SystemExit(1)
