"""Load once for search; optionally check full context on a replacement GPU."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import types

SOURCE = Path('/research/d7/spc/yzyang4/forets-e2e-dev-20260908-IMuJx6/critic-offline-v1/src/mle_critic/src/evaluation')
INCOMING = Path('/research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ready', type=Path, required=True)
    p.add_argument('--verify-3090-context', action='store_true')
    args = p.parse_args()
    if not os.environ.get('SLURM_STEP_ID', '').isdigit() or args.ready.exists():
        raise RuntimeError('requires a new service inside an approved Slurm step')
    # Service needs no generator credentials; never copy environment into artifacts.
    for name in tuple(os.environ):
        if name.startswith('PRIMARY_KEY') or name in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
            os.environ.pop(name)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                      PYTHON_DOTENV_DISABLED='1', OMP_NUM_THREADS='6', TOKENIZERS_PARALLELISM='false')
    package = types.ModuleType('forets_live_service_source')
    package.__path__ = [str(SOURCE)]
    sys.modules[package.__name__] = package
    started = time.monotonic()
    for name in ('bradley_terry_evaluation', 'bradley_terry_server'):
        spec = importlib.util.spec_from_file_location(package.__name__+'.'+name, SOURCE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    service = sys.modules[package.__name__+'.bradley_terry_server']
    scorer = service.RewardScorer(str(INCOMING/'unpacked/Qwen3-8B_reward_seed1/checkpoint-100'),
                                 offline_base_dir=str(INCOMING/'base-metadata'))
    deployment_check = None
    if args.verify_3090_context:
        import torch
        if torch.cuda.device_count() != 1 or '3090' not in torch.cuda.get_device_name(0):
            raise RuntimeError('replacement critic requires one real RTX3090')
        if scorer.max_len != 16384 or scorer.model.training:
            raise RuntimeError('critic context or inference mode changed')
        if any(p.device.type != 'cuda' or p.dtype != torch.bfloat16 for p in scorer.model.parameters()):
            raise RuntimeError('critic was offloaded or changed precision; no fallback allowed')
        code = 'x = 1\n' * 20000
        if len(scorer.encode('deployment-compatibility', code)) != 16384:
            raise RuntimeError('deployment check did not exercise full context')
        torch.cuda.reset_peak_memory_stats()
        check_started = time.monotonic()
        scores = scorer.score_batch([('deployment-compatibility', code)])
        torch.cuda.synchronize()
        if len(scores) != 1 or not math.isfinite(scores[0]):
            raise RuntimeError('critic full-context forward failed')
        deployment_check = dict(gpu_name=torch.cuda.get_device_name(0),
            torch_version=torch.__version__, cuda_version=torch.version.cuda,
            gpu_total_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
            context=16384, forward_seconds=time.monotonic()-check_started,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_bytes=torch.cuda.max_memory_reserved(), all_parameters_cuda_bf16=True,
            synthetic_forwards=1, model_loads=1)
    queue = service.BatchScoringQueue(scorer, batch_size=1)
    listener = service.ThreadingHTTPServer(('127.0.0.1', 8765), service.make_handler(queue))
    value = dict(allocation_id=os.environ['SLURM_JOB_ID'], step_id=os.environ['SLURM_STEP_ID'],
                 host='127.0.0.1', port=8765, model_load_and_bind_seconds=time.monotonic()-started,
                 visible_gpu=os.environ.get('CUDA_VISIBLE_DEVICES'), pid=os.getpid(),
                 acceptance_repeated=False, deployment_check=deployment_check)
    # Rename a completed file so the controller never reads a half-written marker.
    temporary = args.ready.with_suffix('.pending')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
        json.dump(value, f); f.flush(); os.fsync(f.fileno())
    os.rename(temporary, args.ready)
    try:
        listener.serve_forever()
    finally:
        listener.server_close()


if __name__ == '__main__':
    main()
