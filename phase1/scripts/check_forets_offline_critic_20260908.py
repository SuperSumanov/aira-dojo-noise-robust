"""CPU-only loader regression and real-header compatibility, never an effect test."""
import argparse
import importlib.util
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import types
from unittest.mock import patch

import torch
from accelerate import init_empty_weights
from safetensors.torch import save_file
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from transformers import AutoConfig, AutoModel, AutoTokenizer, PreTrainedTokenizerFast, Qwen3Config


def load_sources(root):
    package = types.ModuleType('offline_check_source')
    package.__path__ = [str(root)]
    sys.modules[package.__name__] = package
    result = []
    for name in ('bradley_terry_evaluation', 'bradley_terry_server'):
        key = package.__name__ + '.' + name
        spec = importlib.util.spec_from_file_location(key, root / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        result.append(module)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--incoming-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not torch.cuda.is_available(), 'Run this check with CUDA_VISIBLE_DEVICES empty'
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    evaluation, server = load_sources(args.source_root)
    receipt = dict(status='STARTED', checks=[], real_8b_weights_loaded=False,
                   real_8b_forward=False, gpu_requested=False, inference_api_calls=0,
                   protected_data_read=False, tiny_fixture_seeds=[6, 7])

    def expect_failure(name, call, kind):
        try:
            call()
        except kind:
            receipt['checks'].append(name)
        else:
            raise AssertionError('Expected rejection: ' + name)

    # Even accidental networking is an error; all fixtures and base metadata are local.
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
        with tempfile.TemporaryDirectory(prefix='forets-offline-cpu-') as temp:
            root = Path(temp)
            base = root / 'base'
            base.mkdir()
            config = Qwen3Config(vocab_size=8, hidden_size=32, intermediate_size=64,
                                 num_hidden_layers=1, num_attention_heads=2,
                                 num_key_value_heads=1, head_dim=16, max_position_embeddings=64)
            config.save_pretrained(base)
            tokenizer = PreTrainedTokenizerFast(
                tokenizer_object=Tokenizer(WordLevel({'[UNK]': 0, '[EOS]': 1, 'hello': 2}, unk_token='[UNK]')),
                unk_token='[UNK]', eos_token='[EOS]')
            tokenizer.save_pretrained(base)
            for seed in (6, 7):
                torch.manual_seed(seed)
                original = evaluation._RewardModel(AutoModel.from_config(config)).eval()
                checkpoint = root / ('checkpoint-' + str(seed))
                checkpoint.mkdir()
                state = {key: value.detach().clone().contiguous() for key, value in original.state_dict().items()}
                save_file(state, checkpoint / 'model.safetensors')
                with patch.object(AutoModel, 'from_pretrained', side_effect=AssertionError('Pretrained download forbidden')):
                    loaded, loaded_tokenizer, meta = evaluation.load_checkpoint(
                        str(checkpoint), offline_base_dir=str(base))
                    assert meta == {} and loaded_tokenizer.pad_token_id == loaded_tokenizer.eos_token_id
                    assert not loaded.training
                    assert all(not value.is_meta for value in (*loaded.parameters(), *loaded.buffers()))
                    sequences = [[2, 1], [1, 2, 1, 2]]
                    expected = evaluation._score_sequences(original, sequences, 1)
                    observed = evaluation._score_sequences(loaded, sequences, 1)
                    assert expected == observed
                    for key, value in loaded.state_dict().items():
                        assert torch.equal(value, state[key])
                    scorer = server.RewardScorer(str(checkpoint), offline_base_dir=str(base))
                    requests = [('toy', 'hello'), ('toy', 'hello hello')]
                    encoded = [scorer.encode(*item) for item in requests]
                    expected_server = [float(torch.sigmoid(torch.tensor(x)).item()) for x in
                                       evaluation._score_sequences(original, encoded, loaded_tokenizer.pad_token_id)]
                    assert scorer.score_batch(requests) == expected_server
                receipt['checks'].append('tiny_qwen3_load_and_scorer_equal_seed_' + str(seed))

            # Default path still calls the legacy pretrained factory when the new option is absent.
            with patch.object(AutoModel, 'from_pretrained', return_value=AutoModel.from_config(config)) as legacy:
                evaluation.load_checkpoint(str(checkpoint), base_model=str(base))
                assert legacy.call_count == 1
            receipt['checks'].append('legacy_path_unchanged')

            for case in ('missing_head_bias', 'extra_tensor', 'head_shape_mismatch'):
                bad = dict(state)
                if case == 'missing_head_bias':
                    del bad['head.bias']
                elif case == 'extra_tensor':
                    bad['unexpected_tensor'] = torch.zeros(1)
                else:
                    bad['head.weight'] = torch.zeros(2, config.hidden_size)
                bad_dir = root / case
                bad_dir.mkdir()
                save_file(bad, bad_dir / 'model.safetensors')
                expect_failure(case, lambda: evaluation.load_checkpoint(str(bad_dir), offline_base_dir=str(base)), RuntimeError)
            expect_failure('local_metadata_required', lambda: evaluation.load_checkpoint(
                str(checkpoint), offline_base_dir='Qwen/Qwen3-8B-Base'), ValueError)
            with patch.object(torch.cuda, 'is_available', return_value=True), patch.object(torch.cuda, 'device_count', return_value=2):
                expect_failure('multiple_visible_gpus_rejected', lambda: evaluation.load_checkpoint(
                    str(checkpoint), offline_base_dir=str(base)), ValueError)
            (checkpoint / 'head.pt').touch()
            expect_failure('separate_pickle_head_rejected_without_load', lambda: evaluation.load_checkpoint(
                str(checkpoint), offline_base_dir=str(base)), ValueError)

        incoming = args.incoming_root
        weights = incoming / 'unpacked/Qwen3-8B_reward_seed1/checkpoint-100/model.safetensors'
        with weights.open('rb') as source:
            length = struct.unpack('<Q', source.read(8))[0]
            assert 0 < length < 16 * 1024**2
            header = json.loads(source.read(length))
        actual_shapes = {key: value['shape'] for key, value in header.items() if key != '__metadata__'}
        config = AutoConfig.from_pretrained(str(incoming / 'base-metadata'), local_files_only=True, trust_remote_code=False)
        with init_empty_weights(include_buffers=False):
            empty_model = evaluation._RewardModel(AutoModel.from_config(config, torch_dtype=torch.bfloat16))
        expected_shapes = {key: list(value.shape) for key, value in empty_model.state_dict().items()}
        assert expected_shapes == actual_shapes, 'Real checkpoint keys/shapes differ from fixed local Qwen3 config'
        assert all(value.is_meta for value in empty_model.parameters())
        real_tokenizer = AutoTokenizer.from_pretrained(str(incoming / 'base-metadata'), local_files_only=True, trust_remote_code=False)
        ids = real_tokenizer("# MLE-bench task: toy\nprint('ready')", add_special_tokens=False)['input_ids']
        assert ids and max(ids) < config.vocab_size
        receipt.update(real_header_tensor_count=len(actual_shapes),
                       real_header_keys_and_shapes_equal=True, real_tokenizer_offline_ready=True)
        receipt['checks'].append('real_8b_header_matches_meta_architecture_and_tokenizer_loads_offline')
    receipt.update(status='CPU_LOADER_REGRESSION_AND_HEADER_COMPATIBILITY_PASS',
                   checks_passed=len(receipt['checks']), torch_version=torch.__version__)
    with args.output.open('x') as output:
        json.dump(receipt, output, sort_keys=True, indent=2)
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
