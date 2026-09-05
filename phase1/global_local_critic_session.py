"""Run/checkpoint/resume a prepared critic consumer, without reading a dataset.

This is a framework-managed DDP persistence path, not input authorization. The
caller owns qualified inputs, model construction, compute approval and bounded
distributed aborts. DeepSpeed/FSDP admission is deliberately still closed.
Existing two-parameter prototype checkpoint guards are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import re

import numpy as np
import torch

from phase1.global_local_accelerate_checkpoint_gate import atomic_json, verify_restored
from phase1.global_local_execution_plan import PlanError, digest_records


def file_sha(path):
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise PlanError('checkpoint_changed_while_hashing')
    return h.hexdigest()


def state_fingerprint(value):
    """Typed, bounded-temporary hashing; handles bf16 without numpy conversion."""
    h = hashlib.sha256()

    def token(raw):
        h.update(len(raw).to_bytes(8, 'big'))
        h.update(raw)

    def visit(obj):
        if isinstance(obj, torch.Tensor):
            tensor = obj.detach().contiguous().reshape(-1)
            token(b'tensor'); token(str(tensor.dtype).encode())
            token(json.dumps(list(obj.shape)).encode())
            for chunk in tensor.split(1 << 20):
                token(chunk.cpu().view(torch.uint8).numpy().tobytes())
        elif isinstance(obj, np.ndarray):
            token(b'numpy'); token(obj.dtype.str.encode())
            token(json.dumps(list(obj.shape)).encode()); token(obj.tobytes())
        elif isinstance(obj, dict):
            if any(type(k) not in (str, int) for k in obj):
                raise PlanError('unsupported_state_mapping_key')
            token(b'dict'); token(str(len(obj)).encode())
            for key in sorted(obj, key=lambda k: (type(k).__name__, str(k))):
                visit(key); visit(obj[key])
        elif isinstance(obj, (list, tuple)):
            token(type(obj).__name__.encode()); token(str(len(obj)).encode())
            for item in obj: visit(item)
        elif obj is None or type(obj) in (str, int, bool, float):
            token(type(obj).__name__.encode())
            token((obj.hex() if type(obj) is float else repr(obj)).encode())
        else:
            raise PlanError('unsupported_state_value')
    visit(value)
    return h.hexdigest()


def current_state(consumer):
    accelerator = consumer.accelerator
    rng = {'cpu': torch.get_rng_state()}
    if accelerator.device.type == 'cuda':
        rng['local_cuda'] = torch.cuda.get_rng_state(accelerator.device)
    return {key: state_fingerprint(value) for key, value in {
        'model': accelerator.unwrap_model(consumer.model).state_dict(),
        'optimizer': consumer.optimizer.state_dict(),
        'python_rng': random.getstate(), 'numpy_rng': np.random.get_state(), 'torch_rng': rng,
    }.items()}


def expected_files(world):
    return {'model.safetensors', 'optimizer.bin'} | {
        f'{stem}_{rank}.{extension}' for rank in range(world)
        for stem, extension in (('random_states', 'pkl'), ('observed', 'json'))
    }


def regular_tree(root, expected):
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != expected:
        raise PlanError('critic_checkpoint_file_set_mismatch')
    for name in expected:
        path = root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size <= 0:
            raise PlanError('unsafe_critic_checkpoint_member')


def read_small(path):
    if path.stat().st_size > 2_000_000:
        raise PlanError('checkpoint_metadata_too_large')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out: raise PlanError('duplicate_checkpoint_metadata_key')
            out[key] = value
        return out
    return json.loads(path.read_text(), object_pairs_hook=unique)


def verify_bundle(root, binding, expected_sha):
    """Check the caller-pinned manifest and every rank BEFORE deserialization."""
    if not re.fullmatch('[0-9a-f]{64}', str(expected_sha)):
        raise PlanError('explicit_checkpoint_manifest_sha_required')
    regular_tree(root, expected_files(binding['world']) | {'manifest.json'})
    if file_sha(root/'manifest.json') != expected_sha:
        raise PlanError('critic_checkpoint_manifest_hash_mismatch')
    manifest = read_small(root/'manifest.json')
    if set(manifest) != {'protocol', 'binding', 'files', 'completed_steps', 'cumulative_valid_tokens'}:
        raise PlanError('critic_checkpoint_manifest_schema')
    if manifest['protocol'] != 'critic-session-ddp-checkpoint-v1' or manifest['binding'] != binding:
        raise PlanError('critic_checkpoint_binding_mismatch')
    step = manifest['completed_steps']
    if (type(step) is not int or not 0 < step <= binding['total_steps']
            or type(manifest['cumulative_valid_tokens']) is not int or manifest['cumulative_valid_tokens'] <= 0):
        raise PlanError('critic_checkpoint_cursor_mismatch')
    if set(manifest['files']) != expected_files(binding['world']):
        raise PlanError('critic_checkpoint_manifest_file_set')
    for name, record in manifest['files'].items():
        path = root/name
        if record != {'bytes': path.stat().st_size, 'sha256': file_sha(path)}:
            raise PlanError('critic_checkpoint_member_hash_mismatch')
    for rank in range(binding['world']):
        row = read_small(root/f'observed_{rank}.json')
        if (set(row) != {'rank', 'binding', 'completed_steps', 'cumulative_valid_tokens', 'state'}
                or type(row['rank']) is not int or row['rank'] != rank or row['binding'] != binding
                or row['completed_steps'] != step
                or row['cumulative_valid_tokens'] != manifest['cumulative_valid_tokens']
                or set(row['state']) != {'model','optimizer','python_rng','numpy_rng','torch_rng'}
                or any(not re.fullmatch('[0-9a-f]{64}', str(v)) for v in row['state'].values())):
            raise PlanError('critic_checkpoint_rank_state_mismatch')
    return manifest


class CriticSession:
    """Same consumer for uninterrupted and fresh-process resumed execution.

    A digest binds a caller's training contract; it does not assert that the
    contract is authorized or factually true. No dataset/prediction reader here.
    Save/restore failures poison the consumer; no in-process retry of mutated
    state. All ranks must participate; the launcher must enforce a timeout.
    """
    def __init__(self, consumer, *, training_contract_sha256):
        if not re.fullmatch('[0-9a-f]{64}', str(training_contract_sha256)):
            raise PlanError('training_contract_hash_required')
        self.consumer = consumer
        accelerator = consumer.accelerator
        backend = str(accelerator.distributed_type).split('.')[-1]
        if backend not in ('NO', 'MULTI_CPU', 'MULTI_GPU'):
            raise PlanError('critic_persistence_backend_not_yet_admitted')
        if (consumer.poisoned or consumer.completed_steps != 0
                or accelerator.mixed_precision not in ('no','bf16')
                or getattr(accelerator,'scaler',None) is not None
                or getattr(accelerator,'_custom_objects',[]) or getattr(accelerator,'_schedulers',[])
                or getattr(accelerator,'_dataloaders',[]) or len(accelerator._models) != 1
                or accelerator.project_configuration.automatic_checkpoint_naming):
            raise PlanError('critic_persistence_initial_state_unsupported')
        model = accelerator.unwrap_model(consumer.model)
        from phase1.global_local_accelerate_resume_validation import checkpoint_runtime
        raw_optimizer = getattr(consumer.optimizer, 'optimizer', consumer.optimizer)
        self.binding = {'protocol':'critic-session-ddp-v1', 'world':accelerator.num_processes,
            'backend':backend,'mixed_precision':accelerator.mixed_precision,
            'training_contract_sha256':training_contract_sha256,
            'plan_sha256':consumer.plan.sha256,'input_sha256':consumer.plan.input_sha256,
            'total_steps':consumer.plan.steps,'seed':consumer.plan.seed,'arm':consumer.plan.arm,
            'runtime_sha256':digest_records([consumer.runtime,checkpoint_runtime()]),
            'optimizer_type':type(raw_optimizer).__module__+'.'+type(raw_optimizer).__qualname__,
            'initial_optimizer_groups_sha256':state_fingerprint([
                {k:v for k,v in group.items() if k != 'params'} for group in raw_optimizer.param_groups]),
            'model_schema_sha256':digest_records([(k,list(v.shape),str(v.dtype)) for k,v in model.state_dict().items()]),
            'session_source_sha256':file_sha(Path(__file__))}

    def _boundary(self):
        c = self.consumer
        if (c.poisoned or c.accelerator.step != 0 or not c.accelerator.sync_gradients
                or not c.model.training):
            raise PlanError('critic_persistence_not_clean_boundary')
        if any(p.grad is not None and bool(torch.count_nonzero(p.grad)) for p in c.model.parameters()):
            raise PlanError('critic_persistence_uncommitted_gradient')

    def _tokens(self, completed):
        return 0 if completed == 0 else self.consumer._updates[completed-1][0].cumulative_valid_tokens_after_update

    def run_until(self, completed_steps):
        c = self.consumer
        if type(completed_steps) is not int or not c.completed_steps <= completed_steps <= c.plan.steps:
            raise PlanError('critic_session_stop_outside_plan')
        # Streaming yield: production callers need not retain all raw receipts.
        while c.completed_steps < completed_steps:
            yield c.run_next_update()

    def save(self, root):
        c, root = self.consumer, Path(root)
        try:
            self._boundary()
            if (c.completed_steps == 0 or root.exists() or not root.is_absolute()
                    or '..' in root.parts or any(p.is_symlink() for p in root.parents)):
                raise PlanError('critic_checkpoint_new_absolute_path_required')
            partial = root.with_name(root.name+'.partial')
            if c.rank == 0: partial.mkdir(mode=0o700)
            c.accelerator.wait_for_everyone()
            before = current_state(c)
            c.accelerator.save_state(str(partial), safe_serialization=True)
            verify_restored(before, current_state(c))
            atomic_json(partial/f'observed_{c.rank}.json',{'rank':c.rank,'binding':self.binding,
                'completed_steps':c.completed_steps,'cumulative_valid_tokens':self._tokens(c.completed_steps),'state':before})
            c.accelerator.wait_for_everyone()
            if c.rank == 0:
                names = expected_files(self.binding['world'])
                regular_tree(partial,names)
                atomic_json(partial/'manifest.json',{'protocol':'critic-session-ddp-checkpoint-v1',
                    'binding':self.binding,'completed_steps':c.completed_steps,
                    'cumulative_valid_tokens':self._tokens(c.completed_steps),
                    'files':{name:{'bytes':(partial/name).stat().st_size,'sha256':file_sha(partial/name)} for name in sorted(names)}})
                os.rename(partial,root)
            c.accelerator.wait_for_everyone()
            digest = file_sha(root/'manifest.json')
            verify_bundle(root,self.binding,digest)
            return digest
        except BaseException:
            c.poisoned = True
            raise

    def restore(self, root, *, manifest_sha256):
        c, root = self.consumer, Path(root)
        try:
            self._boundary()
            if c.completed_steps != 0:
                raise PlanError('critic_restore_requires_fresh_consumer')
            manifest = verify_bundle(root,self.binding,manifest_sha256)
            completed = manifest['completed_steps']
            if manifest['cumulative_valid_tokens'] != self._tokens(completed):
                raise PlanError('critic_restore_token_cursor_mismatch')
            observed = read_small(root/f'observed_{c.rank}.json')
            c.accelerator.load_state(str(root),load_kwargs={'weights_only':True},map_location='cpu')
            verify_restored(observed['state'],current_state(c))
            self._boundary()
            # Only after model, optimizer and every RNG component match.
            c.completed_steps = completed
            return {'completed_steps':completed,'cumulative_valid_tokens':self._tokens(completed),
                    'all_state_components_restored':True,'manifest_sha256':manifest_sha256}
        except BaseException:
            c.poisoned = True
            raise
