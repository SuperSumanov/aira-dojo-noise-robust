"""Only the public August v9 release: identity, security and label schema."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

SOURCE = Path('/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v9.jsonl')
EXPECTED = 'daeb29fc07ad670b5ca7a10cd2d84f1fa9a27dfa9d22510533417f1a8ad9407f'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def main():
    digest = hashlib.sha256()
    with SOURCE.open('rb') as stream:
        for line in stream:
            digest.update(line)
            if SECRET.search(line):
                raise ValueError('credential-shaped source; do not inspect contents')
    if digest.hexdigest() != EXPECTED:
        raise ValueError('immutable v9 release differs; no fallback to newer corpus')
    fields = defaultdict(Counter)
    flags = defaultdict(Counter)
    nested = defaultdict(Counter)
    rows = 0
    tasks = Counter()
    with SOURCE.open('rb') as stream:
        for line in stream:
            card = json.loads(line)
            rows += 1
            tasks[card['task']['name']] += 1
            for key, value in card.items():
                fields[key][type(value).__name__] += 1
                if isinstance(value, dict):
                    for sub, item in value.items():
                        nested[key + '.' + sub][type(item).__name__] += 1
                if key.lower() in ('valid_submission', 'is_buggy', 'exit_code', 'success', 'is_valid', 'valid'):
                    flags[key][json.dumps(value, sort_keys=True)] += 1
    if rows != 14323:
        raise ValueError('v9 row count differs')
    print(json.dumps(dict(source_sha256=EXPECTED, rows=rows, fields=fields, nested=nested, flags=flags, tasks=tasks), sort_keys=True))

if __name__ == '__main__':
    main()
