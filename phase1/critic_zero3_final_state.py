"""Load a caller-qualified, FINAL ZeRO-3 checkpoint into a fresh CPU critic.

Not an admission gate or a pickle sandbox. Caller must own/authenticate the
checkpoint and discard the supplied model after ANY error. Never executes the
checkpoint's copied Python helper, guesses a 'latest', downloads or uses CUDA.
The fixed runtime converter supplies lazy FP32 masters, cast to the caller's
declared model dtype one parameter at a time. This is inference, not resume.
"""
import contextlib
import hashlib
import inspect
import io
from pathlib import Path

from phase1.global_local_execution_plan import PlanError

CONVERTER_SHA = '2859057b959683c8aff715cec1691c9c46bf75b14859003202f561df2be3b1fb'


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def load_final_into_cpu(model, checkpoint, *, binding, manifest_sha256, expected_tokens):
    import torch
    from deepspeed.utils import zero_to_fp32
    from phase1.global_local_zero3_session import TAG, verify_bundle
    from phase1.global_local_critic_session import state_fingerprint

    require(isinstance(model, torch.nn.Module) and all(not m.training for m in model.modules()), 'final_readout_eval_required')
    state = model.state_dict()
    require(bool(state) and all(t.device.type == 'cpu' and t.is_floating_point() for t in state.values()),
            'final_readout_floating_cpu_model_required')
    require(not any(hasattr(p, 'ds_id') for p in model.parameters()), 'final_readout_fresh_nonpartitioned_model')
    require(type(expected_tokens) is int and expected_tokens > 0, 'final_readout_token_binding')
    source = Path(inspect.getsourcefile(zero_to_fp32))
    require(hashlib.sha256(source.read_bytes()).hexdigest() == CONVERTER_SHA, 'final_converter_runtime_drift')
    root = Path(checkpoint)
    manifest = verify_bundle(root, binding, manifest_sha256)
    require(manifest['completed_steps'] == binding['total_steps']
            and manifest['cumulative_valid_tokens'] == expected_tokens, 'final_readout_incomplete_checkpoint')
    # The converter emits names/paths on stdout and progress on stderr. These
    # are not public evidence. Suppress both, including exceptional paths.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        lazy = zero_to_fp32.get_fp32_state_dict_from_zero_checkpoint(str(root), tag=TAG,
            exclude_frozen_parameters=False, lazy_mode=True)
    require(type(lazy) is dict or isinstance(lazy, dict), 'final_converter_mapping')
    require(set(lazy) == set(state), 'final_readout_parameter_set')
    require(all(tuple(lazy[k].shape) == tuple(t.shape) and lazy[k].dtype == torch.float32
                for k, t in state.items()), 'final_readout_shape_or_master_dtype')
    # Recheck the exact bytes after library parsing and before model mutation.
    require(verify_bundle(root, binding, manifest_sha256) == manifest, 'final_readout_input_changed')
    with torch.no_grad():
        for name, target in state.items():
            tensor = lazy[name].contiguous()
            require(isinstance(tensor, torch.Tensor) and tensor.device.type == 'cpu'
                    and tensor.dtype == torch.float32 and tuple(tensor.shape) == tuple(target.shape),
                    'final_converter_tensor')
            require(bool(torch.isfinite(tensor).all()), 'final_readout_nonfinite_master')
            converted = tensor.to(dtype=target.dtype)
            require(bool(torch.isfinite(converted).all()), 'final_readout_nonfinite_cast')
            target.copy_(converted)
            require(torch.equal(target, converted), 'final_readout_copy_mismatch')
    require(verify_bundle(root, binding, manifest_sha256) == manifest, 'final_readout_input_changed')
    return {'classification': 'FINAL_ZERO3_TO_CPU_MODEL_NOT_RESUME_OR_ADMISSION',
        'checkpoint_manifest_sha256': manifest_sha256, 'converter_source_sha256': CONVERTER_SHA,
        'completed_steps': manifest['completed_steps'], 'valid_tokens': expected_tokens,
        'state_tensor_count': len(state), 'state_elements': sum(t.numel() for t in state.values()),
        'model_state_sha256': state_fingerprint(state), 'copied_checkpoint_script_executed': False,
        'inference_only_optimizer_and_rng_not_restored': True,
        'production_source_or_GPU_qualification': False}
