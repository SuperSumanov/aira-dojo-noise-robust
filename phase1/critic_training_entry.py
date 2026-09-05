"""Production entry, closed until a REAL release and quantified budget are pinned.

An arbitrary JSON boolean/hash declaration does not admit a dataset. The exact
launch-contract bytes must first be registered in this reviewed source after
source, isolation, CPU/GPU, storage, cost and authorization prerequisites pass.
The registry is intentionally EMPTY at implementation time. No --force flag.
"""
import argparse
import json
import os
from pathlib import Path

from phase1.critic_train_projection import PinnedFile, TrainProjectionSpec, read_pinned
from phase1.global_local_execution_plan import EncoderBinding, PlanError


# release_id -> PinnedFile('launch.json', actual approved SHA, actual bytes).
# Populate only from factual qualification, not to make a fixture pass.
ADMITTED_RELEASES = {}


def registered_contract(release_id, contract_root):
    if release_id not in ADMITTED_RELEASES:
        raise PlanError('no_qualified_production_release_registered')
    pinned = ADMITTED_RELEASES[release_id]
    obj = read_pinned(Path(contract_root), pinned)
    if obj.get('protocol') != 'critic-development-launch-v1' or obj.get('release_id') != release_id:
        raise PlanError('launch_contract_identity')
    return obj, pinned.sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release-id', required=True)
    parser.add_argument('--contract-root', type=Path, required=True)
    parser.add_argument('--sequence', type=int, choices=(1, 2, 3, 4), required=True)
    args = parser.parse_args()
    contract, contract_sha = registered_contract(args.release_id, args.contract_root)
    # No file/model/CUDA import before admission above. Parent launcher owns
    # Slurm allocation checking and cumulative GPU-second enforcement.
    if (not os.environ.get('SLURM_JOB_ID', '').isdigit() or os.environ.get('WORLD_SIZE') != '2'
            or os.environ.get('HF_HUB_OFFLINE') != '1' or os.environ.get('TRANSFORMERS_OFFLINE') != '1'):
        raise PlanError('production_allocation_and_offline_environment_required')
    from transformers import AutoTokenizer
    from phase1.verify_critic_component_g0 import validate_model_snapshot, sha256_file
    from phase1.critic_offline_setup import create_zero3_setup
    from phase1.critic_training_run import connect_training, run_session
    model = contract['model']
    if sha256_file(Path(model['manifest'])) != model['manifest_sha256']:
        raise PlanError('production_model_manifest_drift')
    validate_model_snapshot(Path(model['snapshot']), Path(model['manifest']))
    tokenizer = AutoTokenizer.from_pretrained(model['snapshot'], local_files_only=True, trust_remote_code=False)
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id
    if type(pad_id) is not int or pad_id < 0:
        raise PlanError('production_pad_id')
    source = contract['projection']
    spec = TrainProjectionSpec(source['source_package_sha256'], source['split_receipt_sha256'],
        **{key: PinnedFile(**source[key]) for key in ('topology', 'local_targets', 'global_targets')})
    entry = contract['fits'][str(args.sequence)]
    fit, session = connect_training(Path(source['root']), spec, tokenizer,
        encoder=EncoderBinding(**contract['encoder']), protocol_sha256=contract['screen_protocol_sha256'],
        sequence=args.sequence, training_contract_sha256=contract_sha,
        expected_plan_sha256=entry['plan_sha256'], expected_shape=contract['shape'],
        setup=create_zero3_setup(source_root=model['source_root'], model_snapshot=model['snapshot'], pad_id=pad_id))
    result = run_session(session, fit, Path(entry['output']), stop_after=entry['stop_after'],
        checkpoint_steps=entry['checkpoint_steps'], resume=entry.get('resume'),
        resume_manifest_sha256=entry.get('resume_manifest_sha256'))
    if session.consumer.rank == 0:
        print(json.dumps({'status': result['status'], 'sequence': fit.sequence,
                          'stop_step': result['stop_step'], 'plan_sha256': fit.plan.sha256}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never echo an arbitrary exception, input text, environment or path.
        reason = str(exc) if isinstance(exc, PlanError) else 'detail_withheld'
        print(json.dumps({'status': 'TRAINING_ENTRY_FAILED_CLOSED', 'reason': reason}), flush=True)
        raise SystemExit(1)
