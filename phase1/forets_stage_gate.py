"""Reuse recorded compatibility, not synthetic GPU acceptance on each retry."""
import hashlib
import json
import datetime
from pathlib import Path

PREVIOUS = Path('/research/d7/spc/yzyang4/forets-e2e-3090-20260910-j6zb6d6i/package-r2')
RECEIPTS = {
    'container.compatibility.json': '0e78fa1d53e8d65a061f6f20ca8676b6575f928cb431d86a09673bfeff046c40',
    'critic.ready.json': '8effbf82808eb9c5492bb7c17f699d6befa6e2b867d04a48ff502ed12a1bb853',
}


def prior_compatibility(node, image, previous=PREVIOUS):
    receipts = {}
    for name, expected in RECEIPTS.items():
        payload = (previous/name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise RuntimeError('prior compatibility receipt changed')
        receipts[name] = json.loads(payload)
    task = receipts['container.compatibility.json']
    info = Path(image).stat()
    if (node != task['node'] or str(image) != task['image']
            or info.st_size != task['image_bytes'] or info.st_mtime_ns != task['image_mtime_ns']
            or task['forward_backward_cuda'] is not True):
        raise RuntimeError('reuse requires the same node and unchanged task image metadata')
    critic = receipts['critic.ready.json']['deployment_check']
    if critic['context'] != 16384 or not critic['all_parameters_cuda_bf16']:
        raise RuntimeError('prior critic deployment not qualified')
    return dict(role='prior_compatibility_reuse_not_new_gpu_test', previous_job='12977',
                node=node, image=str(image), receipt_sha256=RECEIPTS,
                image_content_rehashed=False, synthetic_gpu_forwards=0)


def stage_reached(tasks, run_limit):
    if type(run_limit) is not int or run_limit not in (2, 8):
        raise ValueError('only the first complete pair or full matrix is allowed')
    ordered = sorted(tasks.items())
    if len(ordered) != 8:
        raise ValueError('all eight planned slots must be retained')
    return all(task['status'] in ('completed', 'failed') for _, task in ordered[:run_limit])


def validate_route_receipt(path, source, now=None):
    raw = Path(path).read_bytes()
    receipt = json.loads(raw)
    calls = receipt.get('calls', [])
    if (receipt.get('status') != 'READY' or len(calls) != 2
            or not all(call.get('fixture_matched') is True for call in calls)
            or receipt.get('public_artificial_input_only') is not True
            or receipt.get('model') != 'nvidia/nemotron-3-ultra-550b-a55b:free'):
        raise RuntimeError('fixed free route has no successful two-request receipt')
    now = datetime.datetime.now(datetime.timezone.utc) if now is None else now
    observed = datetime.datetime.fromisoformat(receipt['utc'])
    if observed.tzinfo is None or not -60 <= (now-observed).total_seconds() <= 3600:
        raise RuntimeError('route receipt is stale or future-dated')
    expected = {name:hashlib.sha256((Path(source)/'src/dojo/core/solvers/llm_helpers/backends'/name).read_bytes()).hexdigest()
                for name in ('lite_llm.py', 'bounded_retry.py')}
    if receipt.get('source_hashes') != expected:
        raise RuntimeError('route receipt is not bound to current transport code')
    return dict(receipt_sha256=hashlib.sha256(raw).hexdigest(), observed_utc=receipt['utc'],
                note='Two public requests do not prove long-term endpoint reliability.')
