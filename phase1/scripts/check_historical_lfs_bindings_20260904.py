import hashlib
import json
import re
import subprocess

repo = '/research/d7/spc/yzyang4/aira-dojo-reproduce'
refs = ('92a9651f2e13a9e43623235b82c07c19721bc2ee', 'ac008af8b907d319b694f26b0ba9cf4053b3bf69', 'b8d095180415957aa1bab31fa53ead1bba261c03')
paths = ('data/augmented_mle_critic/augmented_cards_current.json',
         'data/augmented_mle_critic/batch_value_pairs_filtered_runsplit.jsonl',
         'data/augmented_mle_critic/value_pairs_hardware_timelimit_gap_filtered_runsplit.jsonl')
out = []
for ref in refs:
    for path in paths:
        obj = ref + ':' + path
        result = subprocess.run(['git', '-C', repo, 'cat-file', '-s', obj], capture_output=True)
        if result.returncode:
            out.append(dict(commit=ref, path=path, status='missing'))
            continue
        size = int(result.stdout)
        if size > 256:
            out.append(dict(commit=ref, path=path, status='nonpointer_not_opened', bytes=size))
            continue
        raw = subprocess.check_output(['git', '-C', repo, 'show', obj])
        match = re.fullmatch(rb'version https://git-lfs.github.com/spec/v1\noid sha256:([a-f0-9]{64})\nsize ([0-9]+)\n', raw)
        if not match:
            raise ValueError('unexpected_pointer_shape_no_content_emitted')
        out.append(dict(commit=ref, path=path, status='lfs_pointer_only',
                        lfs_oid=match[1].decode(), lfs_bytes=int(match[2]),
                        pointer_sha256=hashlib.sha256(raw).hexdigest()))
print(json.dumps(dict(status='POINTER_ONLY_NO_PAYLOAD_OPENED', bindings=out), sort_keys=True))
