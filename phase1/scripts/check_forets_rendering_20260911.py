"""CPU-only comparison of actual train/server encoders on artificial text.

Not a model evaluation or proof of a checkpoint's historical training template.
"""
import ast
import dataclasses
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys
import tarfile
import tempfile
import types
from typing import Any
from unittest.mock import patch

BASE = Path('/research/d7/spc/yzyang4')
COMMIT = '065b0fbaa89e0eb663f2834ec768081f5d56394d'
TRAIN_PATH = 'src/mle_critic/src/train/dataset/pairs.py'
TRAIN_BLOB = 'ea37f06c6866fb49b16bd303e0e7cd8092f7bb54'
SERVER = BASE / 'forets-e2e-dev-20260908-IMuJx6/critic-offline-v1/src/mle_critic/src/evaluation/bradley_terry_server.py'
SERVER_SHA = 'ebe289b5d22ac8186c8a13c9462aa62782d12cd32c628283081b488468d35fad'
INCOMING = BASE / 'forets-critic-incoming-20260908-3lcjjcwq'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{12,})')


def h(raw): return hashlib.sha256(raw).hexdigest()


def source_class(raw, name, methods=None):
    if SECRET.search(raw): raise ValueError('credential_shaped_source')
    node = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == name)
    if methods is not None:
        node.body = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in methods]
        if {n.name for n in node.body} != set(methods): raise ValueError('method_scope')
        node.decorator_list = []
    namespace = types.ModuleType('_render_' + name)
    namespace.__dict__.update(dataclass=dataclasses.dataclass, Any=Any)
    sys.modules[namespace.__name__] = namespace
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<bound-source>', 'exec'), namespace.__dict__)
    return namespace.__dict__[name]


def main():
    os.umask(0o077)
    os.environ.update(CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1')
    def timeout(*_): raise TimeoutError('bounded_cpu_diagnostic')
    signal.signal(signal.SIGALRM, timeout); signal.alarm(120)
    # Exported from the local public branch: the production Git mirror omits
    # this nested training path. Read one code member, never modify that mirror.
    with tarfile.open(Path(__file__).with_name('train-source-lf.tar'), 'r:') as archive:
        if archive.pax_headers.get('comment') != COMMIT: raise ValueError('source_archive_commit')
        member = archive.getmember(TRAIN_PATH)
        if not member.isfile() or member.size > 1024**2: raise ValueError('source_member')
        with archive.extractfile(member) as f: train = f.read()
    if hashlib.sha1(b'blob ' + str(len(train)).encode() + b'\0' + train).hexdigest() != TRAIN_BLOB:
        raise ValueError('training_blob_changed')
    server = SERVER.read_bytes()
    if h(server) != SERVER_SHA: raise ValueError('deployed_service_changed')
    Encoder = source_class(train, 'CardEncoder')
    Service = source_class(server, 'RewardScorer', ['encode', '_truncate'])
    from transformers import AutoTokenizer
    rows = []
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network_forbidden')):
        tokenizer = AutoTokenizer.from_pretrained(str(INCOMING/'base-metadata'), local_files_only=True, trust_remote_code=False)
        for shape, code in [('short', 'print(1)\n'), ('long', 'x = 1\n'*7000)]:
            for condition in (False, True):
                trainer = Encoder(code={'synthetic': code}, tasks={'synthetic': 'artificial-task'}, tokenizer=tokenizer,
                                  max_len=16384, head_frac=0.25, task_cond=condition, budget_cond=False)
                service = Service()
                service.tokenizer = tokenizer
                service.max_len=16384; service.head_frac=0.25; service.task_cond=condition
                train_ids = trainer.encode('synthetic')
                server_ids = service.encode('artificial-task', code)
                rendered = trainer.render('synthetic')
                marker = '# Please predict whether the following code will be a better solution to this MLE task.\n'
                if not rendered.startswith(marker): raise ValueError('unexpected_training_renderer')
                removed = service._truncate(tokenizer(rendered[len(marker):], add_special_tokens=False)['input_ids'])
                restored = service._truncate(tokenizer(marker + rendered[len(marker):], add_special_tokens=False)['input_ids'])
                if removed != server_ids or restored != train_ids: raise ValueError('difference_not_explained_by_prefix')
                rows.append({'shape': shape, 'task_cond': condition, 'train_tokens': len(train_ids),
                             'service_tokens': len(server_ids), 'same_token_sequence': train_ids == server_ids,
                             'instruction_removal_matches_service': removed == server_ids,
                             'instruction_restoration_matches_training': restored == train_ids,
                             'train_token_sha256': h(json.dumps(train_ids).encode()),
                             'service_token_sha256': h(json.dumps(server_ids).encode())})
    checkpoint = INCOMING/'unpacked/Qwen3-8B_reward_seed1/checkpoint-100'
    result = {'status': 'SOURCE_RENDERING_DIFFERENCE_CONFIRMED_CHECKPOINT_HISTORY_UNKNOWN',
              'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'train_commit': COMMIT,
              'train_source_sha256': h(train), 'deployed_service_sha256': h(server),
              'tokenizer_files_sha256': {p.name: h(p.read_bytes()) for p in sorted((INCOMING/'base-metadata').glob('*.json'))},
              'script_sha256': h(Path(__file__).read_bytes()), 'cases': rows,
              'checkpoint_rm_meta_exists': (checkpoint/'rm_meta.json').exists(),
              'budget_conditioning_tested': False, 'checkpoint_training_rendering_attested': False,
              'service_constructor_or_scoring_called': False, 'model_loads': 0, 'gpu_jobs': 0,
              'network_requests': 0, 'real_candidates_or_protected_values_read': False,
              'production_files_changed': False}
    output = Path(tempfile.mkdtemp(prefix='forets-rendering-20260911-', dir=BASE))/'summary.json'
    with output.open('x') as f: json.dump(result, f, indent=2, sort_keys=True)
    print(json.dumps({'output': str(output), **result}, sort_keys=True))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status': 'RENDERING_DIAGNOSTIC_FAILED_CLOSED', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
