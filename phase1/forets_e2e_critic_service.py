"""Serve the already-accepted critic for real search; no acceptance fixtures."""
import argparse
import importlib.util
import json
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
    queue = service.BatchScoringQueue(scorer, batch_size=1)
    listener = service.ThreadingHTTPServer(('127.0.0.1', 8765), service.make_handler(queue))
    value = dict(allocation_id=os.environ['SLURM_JOB_ID'], step_id=os.environ['SLURM_STEP_ID'],
                 host='127.0.0.1', port=8765, model_load_and_bind_seconds=time.monotonic()-started,
                 visible_gpu=os.environ.get('CUDA_VISIBLE_DEVICES'), pid=os.getpid(),
                 acceptance_repeated=False)
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
