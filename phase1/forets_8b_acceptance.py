"""Prepared, NOT executed: one-GPU offline 8B acceptance on artificial inputs.

--describe uses only the standard library. Execution needs an explicit flag AND
an approved Slurm allocation; the flag itself is not authorization. No training,
task execution, corpus access, or external API is part of this program.
"""
import argparse
import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import re
import socket
import statistics
import sys
import threading
import time
import types
from unittest.mock import patch

SOURCE_BLOBS = {
    'bradley_terry_evaluation.py': '14687d0596d529e6235ccddce08c671227a81feb',
    'bradley_terry_server.py': 'fca0f2e6d6bd6bc6e11cf32876f67f5dceacea7f',
}
BASE_FILES = {
    'config.json': '3bd01d7ad7a2e203ecbbe84e24087a51c6d2a108ee4bcc42d0016bf49564983a',
    'tokenizer_config.json': '3c04ed3ca964ea2f6b2b5faf0dc4d31aec1cb1e8b4bcf63f402d295046b422b5',
    'tokenizer.json': 'c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539',
}
WEIGHTS_SHA256 = 'bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74'
WEIGHTS_BYTES = 15136866890
EXPECTED_VERSIONS = dict(torch='2.11.0+cu128', transformers='4.57.1', accelerate='1.11.0', safetensors='0.5.3')


def describe():
    return dict(status='PLAN_ONLY_NOT_EXECUTED', requires_new_gpu_budget_approval=False,
        approval_scope='one allocation; memory declaration change confirmed 2026-09-09',
        node='projgpu39', gpus=1, cpus=6, host_memory_gib=None,
        slurm_memory_argument='--mem=0', scheduler_80gib_memory_limit=False, allocation_minutes=20,
        step_minutes=19, process_seconds=1050, process_kill_grace_seconds=10,
        process_cleanup_grace_each_seconds=5, expected_versions=EXPECTED_VERSIONS,
        observed_cluster_KillWait_seconds=300,
        nominal_gpu_hours=20/60, gpu_hours_including_observed_KillWait=25/60,
        absolute_failure_runtime_guaranteed=False, generator_api_requests=0,
        model='Qwen/Qwen3-8B-Base', context=16384, batch_size=1, seeds=[6,7],
        fixtures='fixed synthetic code, never executed', measurement_repetitions_per_seed=2,
        scope='load/forward/loopback service only, not accuracy/scaling/e2e utility')


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _write(path, payload):
    # Exclusive target prevents overwriting an earlier receipt.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
        json.dump(payload, file, indent=2, sort_keys=True, allow_nan=False)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())


def run(args):
    if not args.execute_approved_gpu:
        raise RuntimeError('GPU execution is not enabled')
    if not re.fullmatch(r'[0-9]+', os.environ.get('SLURM_JOB_ID','')) or not re.fullmatch(r'[0-9]+', os.environ.get('SLURM_STEP_ID','')):
        raise RuntimeError('run only inside an approved Slurm step')
    if os.environ.get('SLURMD_NODENAME') != 'projgpu39':
        raise RuntimeError('this acceptance matrix is frozen to projgpu39')
    # A persistent receipt directory is the one-attempt claim. Do not replay it.
    args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    receipt = dict(describe(), status='STARTED', source_blobs=SOURCE_BLOBS, entry_sha256=_hash(Path(__file__)),
        allocation_id=os.environ['SLURM_JOB_ID'], step_id=os.environ['SLURM_STEP_ID'],
        external_connections=0, blocked_external_connection_attempts=0,
        model_loaded=False, protected_data_read=False, observations=[])
    _write(args.output_dir/'started.json', receipt)
    try:
        versions = {p: importlib.metadata.version(p) for p in EXPECTED_VERSIONS}
        if versions != EXPECTED_VERSIONS:
            raise RuntimeError('GPU environment versions changed; re-review before loading')
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                          LITELLM_LOCAL_MODEL_COST_MAP='True', TOKENIZERS_PARALLELISM='false',
                          CUBLAS_WORKSPACE_CONFIG=':4096:8')
        # Source identity and fixed local base metadata, never evaluation/training state.
        for name, expected in SOURCE_BLOBS.items():
            content = (args.source_root/name).read_bytes()
            actual = hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
            if actual != expected:
                raise RuntimeError('critic source identity changed')
        for name, expected in BASE_FILES.items():
            if _hash(args.base_dir/name) != expected:
                raise RuntimeError('base metadata identity changed')
        if (args.checkpoint/'rm_meta.json').exists():
            raise RuntimeError('unexpected metadata sidecar; review before loading')
        weights = args.checkpoint/'model.safetensors'
        if weights.stat().st_size != WEIGHTS_BYTES or _hash(weights) != WEIGHTS_SHA256:
            raise RuntimeError('received checkpoint identity changed')
        receipt['weights_sha256'] = WEIGHTS_SHA256

        allowed_port = [None]
        original_connect = socket.socket.connect
        def guarded_connect(sock, address):
            if not (isinstance(address, tuple) and address[0] == '127.0.0.1' and address[1] == allowed_port[0]):
                receipt['blocked_external_connection_attempts'] += 1
                raise RuntimeError('network outside the local acceptance server is forbidden')
            return original_connect(sock, address)
        with patch.object(socket.socket, 'connect', guarded_connect):
            import torch
            import numpy as np
            if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
                raise RuntimeError('exactly one real visible CUDA GPU required; no CPU fallback')
            properties = torch.cuda.get_device_properties(0)
            if properties.total_memory < 80*1024**3:
                raise RuntimeError('frozen PRO6000 acceptance requires at least 80 GiB VRAM')
            torch.set_num_threads(6)
            package = types.ModuleType('forets_acceptance_source')
            package.__path__ = [str(args.source_root)]
            sys.modules[package.__name__] = package
            for name in ('bradley_terry_evaluation','bradley_terry_server'):
                spec = importlib.util.spec_from_file_location(package.__name__+'.'+name, args.source_root/(name+'.py'))
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
            server_module = sys.modules[package.__name__+'.bradley_terry_server']
            started = time.monotonic()
            scorer = server_module.RewardScorer(str(args.checkpoint), offline_base_dir=str(args.base_dir))
            torch.cuda.synchronize()
            receipt.update(model_loaded=True, load_seconds=time.monotonic()-started,
                gpu_name=properties.name, gpu_total_memory_bytes=properties.total_memory,
                runtime_meta=dict(max_len=scorer.max_len, head_frac=scorer.head_frac, task_cond=scorer.task_cond),
                attention_implementation=getattr(scorer.model.backbone.config, '_attn_implementation', None),
                versions=versions)
            if scorer.max_len != 16384 or scorer.model.training:
                raise RuntimeError('context or inference-mode mismatch')
            if any(p.device.type != 'cuda' or p.dtype != torch.bfloat16 for p in scorer.model.parameters()):
                raise RuntimeError('critic not wholly materialized as single-GPU BF16')
            fixtures = [('short','print(1)\n'), ('context_16k', 'x = 1\n'*20000)]
            token_lengths = {}
            for name, code in fixtures:
                encoded = len(scorer.encode('artificial-acceptance', code))
                token_lengths[name] = encoded
                if name == 'context_16k' and encoded != 16384:
                    raise RuntimeError('long fixture did not exercise full context')
            raw = []
            original_score = server_module._score_sequences
            def capture(*call_args, **kwargs):
                result = original_score(*call_args, **kwargs)
                raw[:] = result
                return result
            with patch.object(server_module, '_score_sequences', capture):
                for seed in (6,7):
                    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
                    for name, code in fixtures:
                        scorer.score_batch([('artificial-acceptance', code)])  # separated shape warmup
                        torch.cuda.synchronize()
                        for repetition in range(2):
                            torch.cuda.reset_peak_memory_stats()
                            started = time.monotonic()
                            scores = scorer.score_batch([('artificial-acceptance', code)])
                            torch.cuda.synchronize()
                            elapsed = time.monotonic()-started
                            if len(scores) != 1 or len(raw) != 1 or not all(math.isfinite(v) for v in raw+scores):
                                raise RuntimeError('nonfinite or malformed model output')
                            receipt['observations'].append(dict(seed=seed, fixture=name, repetition=repetition,
                                encoded_tokens=token_lengths[name],
                                seconds=elapsed, sigmoid_saturated=scores[0] in (0.,1.),
                                peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                peak_reserved_bytes=torch.cuda.max_memory_reserved()))
                # Exercise the actual queue and HTTP handler without another model load.
                queue = server_module.BatchScoringQueue(scorer, batch_size=1)
                listener = server_module.ThreadingHTTPServer(('127.0.0.1',0), server_module.make_handler(queue))
                allowed_port[0] = listener.server_port
                thread = threading.Thread(target=listener.serve_forever, daemon=True)
                thread.start()
                try:
                    for name, code in fixtures:
                        connection = http.client.HTTPConnection('127.0.0.1', allowed_port[0], timeout=120)
                        try:
                            connection.request('POST','/score', body=json.dumps(dict(task='artificial-acceptance',code=code)),
                                               headers={'Content-Type':'application/json'})
                            response = connection.getresponse()
                            payload = json.loads(response.read())
                            if response.status != 200 or not math.isfinite(payload['score']):
                                raise RuntimeError('local HTTP scoring failed')
                        finally:
                            connection.close()
                finally:
                    listener.shutdown(); listener.server_close(); thread.join(timeout=5)
            receipt['local_http_requests'] = 2
            receipt['median_seconds_by_fixture'] = {name: statistics.median(
                row['seconds'] for row in receipt['observations'] if row['fixture']==name) for name,_ in fixtures}
            receipt['sample_stdev_seconds_by_fixture'] = {name: statistics.stdev(
                row['seconds'] for row in receipt['observations'] if row['fixture']==name) for name,_ in fixtures}
            receipt['status'] = 'PASS'
    except BaseException as exc:
        receipt.update(status='FAIL', error_type=type(exc).__name__)
        _write(args.output_dir/'finished.json', receipt)
        raise
    _write(args.output_dir/'finished.json', receipt)
    print(json.dumps(dict(status='PASS', model_loaded=True, observations=len(receipt['observations']),
                         scientific_benefit_claim=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--execute-approved-gpu', action='store_true')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--checkpoint', type=Path)
    parser.add_argument('--base-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.describe:
        if args.execute_approved_gpu:
            parser.error('describe and execute are mutually exclusive')
        print(json.dumps(describe(), indent=2))
        return
    if not all((args.source_root,args.checkpoint,args.base_dir,args.output_dir)):
        parser.error('explicit source, checkpoint, base, and output paths required')
    run(args)


if __name__ == '__main__':
    main()
