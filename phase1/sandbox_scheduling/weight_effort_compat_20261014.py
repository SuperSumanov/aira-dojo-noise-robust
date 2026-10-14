"""CPU-only shape/source compatibility; never claims exact training provenance."""
from collections import Counter
import argparse
import json
from pathlib import Path
import sys

from weight_effort_intake_20261014 import header, digest, safe_json

B = Path('/research/d7/spc/yzyang4')
MODEL = B/'local-qwen27b-20260914-zcx1k1dy/model'
ADAPTER = B/'weight-effort-adapter-20261014-ynf9spm3/accepted_adapter'


def check():
    cfg = safe_json((MODEL/'config.json').read_bytes())
    ac = safe_json((ADAPTER/'adapter_config.json').read_bytes())
    ah = header(ADAPTER/'adapter_model.safetensors')
    bh = {}
    for f in sorted(MODEL.glob('*.safetensors')):
        new = header(f)
        assert not set(new) & set(bh)
        bh.update(new)
    pairs, kinds, failures = 0, Counter(), []
    for key, a in ah.items():
        if not key.endswith('.lora_A.weight'):
            continue
        stem = key.removesuffix('.lora_A.weight')
        b = ah[stem+'.lora_B.weight']
        base = stem.removeprefix('base_model.model.')
        assert a['shape'][0] == b['shape'][1] == ac['r']
        expected = [b['shape'][0], a['shape'][1]]
        if base+'.weight' in bh:
            actual = bh[base+'.weight']['shape']
            kind = 'dense'
        elif base+'.weight_packed' in bh:
            packed = bh[base+'.weight_packed']['shape']
            assert cfg['quantization_config']['format'] == 'pack-quantized'
            assert cfg['quantization_config']['config_groups']['group_0']['weights']['num_bits'] == 4
            # compressed-tensors pack-quantized packs eight int4s into int32.
            assert bh[base+'.weight_packed']['dtype'] == 'I32'
            actual = [packed[0], packed[1]*8]
            kind = 'int4_packed'
        else:
            failures.append(dict(module=base, reason='no_base_tensor'))
            continue
        if expected != actual:
            failures.append(dict(module=base, reason='shape', adapter=expected, base=actual))
        pairs += 1
        kinds[kind] += 1
    result = dict(shape_compatible=not failures and pairs*2 == len(ah), pairs=pairs,
        tensors=len(ah), kinds=dict(kinds), failures=failures,
        config_sha256=digest(MODEL/'config.json'), adapter_config_sha256=digest(ADAPTER/'adapter_config.json'),
        model_type=cfg['model_type'], layers=cfg['text_config']['num_hidden_layers'],
        hidden=cfg['text_config']['hidden_size'], rank=ac['r'],
        training_base_revision_known=bool(ac.get('revision')),
        limitation='Shape compatibility alone is not exact training-base lineage or runtime/quality acceptance.')
    out = ADAPTER.parent/'shape-compat.safe.json'
    with out.open('x') as handle:
        handle.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    assert result['shape_compatible']


def source():
    import vllm
    root = Path(vllm.__file__).parent
    files = ['model_executor/models/qwen3_5.py', 'model_executor/models/qwen3_next.py',
             'lora/utils.py', 'lora/peft_helper.py', 'config/lora.py',
             'model_executor/layers/fla/ops/lora.py']
    terms = ('lora', 'packed_modules_mapping', 'hf_to_vllm_mapper', 'in_proj_',
             'supports_', 'weight_packed', 'max_lora_rank', 'prefix_caching')
    print(json.dumps(dict(vllm_version=vllm.__version__, root=str(root))))
    for name in files:
        p = root/name
        if not p.exists():
            continue
        lines = p.read_text().splitlines()
        indices = {j for i, line in enumerate(lines) if any(t in line.lower() for t in terms)
                   for j in range(max(0, i-2), min(len(lines), i+4))}
        print(json.dumps(dict(file=name, sha256=digest(p), relevant_lines=[f'{i+1}: {lines[i]}' for i in sorted(indices)])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapter', type=Path, default=ADAPTER)
    parser.add_argument('--source', action='store_true')
    args = parser.parse_args()
    ADAPTER = args.adapter.resolve()
    if not ADAPTER.is_relative_to(B.resolve()) or ADAPTER.name != 'accepted_adapter':
        raise ValueError('adapter outside research intake scope')
    source() if args.source else check()
