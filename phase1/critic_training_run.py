"""Connect pinned TRAIN files to a prepared model and durable training session.

No scheduler, network, dev reader or source admission. setup() supplies the
separately qualified model/runtime. The same run loop works with the existing
CPU-DDP and explicit ZeRO-3 sessions; no fallback changes the backend.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from phase1.critic_train_projection import load_training_inputs, load_training_targets
from phase1.g_reuse_development_screen_plan import prepare_screen
from phase1.global_local_execution_plan import PlanError


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def select_fit(prepared, sequence):
    require(type(sequence) is int and 1 <= sequence <= 4, 'training_fit_sequence')
    return prepare_screen(prepared)[sequence-1]


def connect_training(root, spec, tokenizer, *, encoder, protocol_sha256, sequence,
                     setup, training_contract_sha256, expected_plan_sha256=None,
                     expected_shape=None):
    """Load topology -> plan -> only required labels -> model, in that order."""
    data = load_training_inputs(root, spec, tokenizer, encoder=encoder, protocol_sha256=protocol_sha256)
    fit = select_fit(data, sequence)
    if expected_plan_sha256 is not None:
        require(fit.plan.sha256 == expected_plan_sha256, 'production_encoded_plan_drift')
    if expected_shape is not None:
        require(asdict(fit.plan.shape) == expected_shape, 'production_encoded_shape_drift')
    truth = load_training_targets(root, spec, data, plan=fit.plan)
    # A failed input never constructs a model or an optimizer.
    session = setup(fit.plan, data.pools, data.encoding_provider, truth,
                    training_contract_sha256=training_contract_sha256)
    require(session.consumer.plan == fit.plan, 'training_setup_changed_plan')
    return fit, session


def atomic_json(path, value):
    temporary = path.with_name(path.name+'.partial')
    require(not path.exists() and not temporary.exists(), 'training_output_overwrite')
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with temporary.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def run_session(session, fit, output, *, stop_after, checkpoint_steps,
                resume=None, resume_manifest_sha256=None):
    """Run a bounded plan prefix. Only a full plan gets COMPLETED status.

    Every stop is a durable checkpoint. The external launcher must bound job
    time and all-rank termination; this routine never kills or requeues a job.
    Repeated/resumed invocations require a NEW output directory.
    """
    import torch
    import torch.distributed as dist
    c = session.consumer
    require(c.plan == fit.plan and c.completed_steps == 0, 'training_fresh_session_required')
    require(type(stop_after) is int and 1 <= stop_after <= c.plan.steps, 'training_stop_boundary')
    require(type(checkpoint_steps) in (list, tuple) and all(type(s) is int for s in checkpoint_steps), 'training_checkpoint_steps')
    require(list(checkpoint_steps) == sorted(set(checkpoint_steps))
            and all(1 <= s <= stop_after for s in checkpoint_steps)
            and stop_after in checkpoint_steps, 'training_checkpoint_schedule')
    require((resume is None) == (resume_manifest_sha256 is None), 'training_resume_binding_required')
    output = Path(output)
    require(output.is_absolute() and '..' not in output.parts and not output.exists()
            and not any(p.is_symlink() for p in (output, *output.parents)), 'training_new_output_root')
    require(output.parent.is_dir(), 'training_output_parent_missing')
    # All ranks must finish the nonexistence check before rank zero creates it.
    c.accelerator.wait_for_everyone()
    if c.rank == 0:
        output.mkdir(mode=0o700)
    c.accelerator.wait_for_everyone()
    started = time.monotonic()
    if resume is not None:
        session.restore(Path(resume), manifest_sha256=resume_manifest_sha256)
    start = c.completed_steps
    require(start < stop_after, 'training_no_new_updates')
    require(all(s > start for s in checkpoint_steps), 'training_save_schedule_before_resume')
    active_gpu = c.accelerator.device.type == 'cuda'
    if active_gpu:
        torch.cuda.reset_peak_memory_stats(c.accelerator.device)
    header = {
        'protocol': 'critic-training-run-v1', 'sequence': fit.sequence,
        'arm': fit.reported_arm, 'consumer_arm': c.plan.arm, 'seed': c.plan.seed,
        'rank': c.rank, 'world_size': c.plan.shape.world_size,
        'plan_sha256': c.plan.sha256, 'session_binding': session.binding,
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'start_step': start, 'stop_step': stop_after, 'full_plan_steps': c.plan.steps,
        'checkpoint_steps': list(checkpoint_steps),
        'resume_manifest_sha256': resume_manifest_sha256,
        'dev_or_test_reader_present': False,
    }
    atomic_json(output/f'rank_{c.rank}_context.json', header)
    saved = []
    warmup_seconds, measured_seconds, updates = [], [], 0
    with (output/f'rank_{c.rank}_updates.jsonl').open('x', encoding='utf-8', newline='\n') as log:
        for step in range(start+1, stop_after+1):
            if active_gpu:
                torch.cuda.synchronize(c.accelerator.device)
            before = time.monotonic()
            events = list(session.run_until(step))
            if active_gpu:
                torch.cuda.synchronize(c.accelerator.device)
            elapsed = time.monotonic()-before
            require(len(events) == 1 and events[0].completed_steps == step, 'training_update_cursor')
            event = events[0]
            # No row identities, label values, code or evaluation outcomes.
            consumed = hashlib.sha256(json.dumps(asdict(event), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            record = {
                'step': step, 'rank': c.rank, 'source': event.source, 'cycle': event.cycle,
                'local_pair_visits': event.local_pair_visits, 'local_valid_tokens': event.local_valid_tokens,
                'global_update_pairs': event.global_update_pairs,
                'cumulative_global_valid_tokens': event.cumulative_global_valid_tokens,
                'learning_rate': event.learning_rate, 'step_owner': event.step_owner,
                'consumption_receipt_sha256': consumed, 'update_seconds': elapsed,
                'first_update_of_process': step == start+1,
            }
            log.write(json.dumps(record, sort_keys=True, allow_nan=False)+'\n'); log.flush(); os.fsync(log.fileno())
            (warmup_seconds if step == start+1 else measured_seconds).append(elapsed)
            updates += 1
            if step in checkpoint_steps:
                save_begin = time.monotonic()
                manifest = session.save(output/f'checkpoint-{step}')
                saved.append({'step': step, 'manifest_sha256': manifest, 'save_seconds': time.monotonic()-save_begin})
    state = {
        'rank': c.rank, 'completed_steps': c.completed_steps,
        'cumulative_global_valid_tokens': session._tokens(c.completed_steps),
        'new_updates': updates, 'first_update_seconds': warmup_seconds,
        'later_update_seconds': measured_seconds, 'saved': saved,
        'segment_elapsed_seconds': time.monotonic()-started,
        'peak_allocated_bytes': torch.cuda.max_memory_allocated(c.accelerator.device) if active_gpu else None,
        'peak_reserved_bytes': torch.cuda.max_memory_reserved(c.accelerator.device) if active_gpu else None,
    }
    gathered = [None]*c.plan.shape.world_size
    dist.all_gather_object(gathered, state)
    require({x['rank'] for x in gathered} == set(range(c.plan.shape.world_size)), 'training_rank_coverage')
    require(all(x['completed_steps'] == stop_after and x['cumulative_global_valid_tokens'] == session._tokens(stop_after)
                and [r['manifest_sha256'] for r in x['saved']] == [r['manifest_sha256'] for r in saved]
                for x in gathered), 'training_final_rank_mismatch')
    result = {
        'status': 'COMPLETED' if stop_after == c.plan.steps else 'CHECKPOINTED_NOT_COMPLETED',
        'sequence': fit.sequence, 'arm': fit.reported_arm, 'seed': c.plan.seed,
        'plan_sha256': c.plan.sha256, 'start_step': start, 'stop_step': stop_after,
        'ranks': sorted(gathered, key=lambda x: x['rank']),
        'source_qualification_attested_by_runner': False,
        'model_effect_evaluated': False, 'contains_preprocessing_or_queue_time': False,
    }
    if c.rank == 0:
        atomic_json(output/'run_receipt.json', result)
    c.accelerator.wait_for_everyone()
    return result
