"""T1 old-development, run-disjoint repair transfer. No API/GPU in preparation."""
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import re
import tempfile

BASE = Path('/research/d7/spc/yzyang4')
SUMMARY = BASE/'forets-wallclock-20260912-5_czzimk/closed-error-families.json'
SUMMARY_SHA = 'fbea5f58486ea518255e6227f5d26014a5e5b0d138c78ce335b66086e3c1ef2b'
INVENTORY = BASE/'forets-repair-memory-inventory-20260913-vcg12_1y/observed-repair-code.private.json'
INVENTORY_SHA = '4caeb8a6494705b7fd103bc66a015b1e8e63f38ffd086267b2bf0499d9884dcb'
SALT = 'repair-transfer-t1-20260913-v1'
TASKS = ('leaf-classification', 'spaceship-titanic')
ARMS = ('no_external_memory', 'retrieved_repair', 'random_repair')
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9a-z_-]{30,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(obj): return (json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
def dump(path, obj):
    raw = encode(obj)
    with path.open('xb') as stream: stream.write(raw)
    return sha(raw)


def read(path, expected=None):
    if path.is_symlink(): raise ValueError('symlink input')
    raw = path.read_bytes()
    if expected and sha(raw) != expected: raise ValueError('fixed input drift')
    if SECRET.search(raw.decode()): raise ValueError('credential shape; no content output')
    return json.loads(raw)


def ast_key(code): return sha(ast.dump(ast.parse(code), include_attributes=False).encode())
def run_key(row): return row['root'], row['run_id']
def text_output(node):
    text = node.get('term_out') or ''
    if isinstance(text, list): text = '\n'.join(text)
    if not isinstance(text, str): raise ValueError('terminal schema')
    return ANSI.sub('', text)


def tokens(text): return set(re.findall(r'[a-z_][a-z0-9_]*', text.lower()))
def overlap(a, b):
    a, b = tokens(a), tokens(b)
    return len(a & b)/len(a | b) if a | b else 0.0


def select_targets(rows, nodes, memories):
    blocked_runs = {run_key(m) for m in memories}
    blocked_ast = {ast_key(m[k]) for m in memories for k in ('parent_code', 'observed_successful_child_code')}
    earliest = {}; excluded = Counter()
    for row in sorted(rows, key=lambda r: (*run_key(r), r['step'])):
        key = run_key(row)
        if key in blocked_runs: excluded['memory_source_run_nodes'] += 1; continue
        if not row['exit_nonzero']: continue
        node = nodes[(*key, row['step'])]
        code = node['code']
        if SECRET.search(code) or SECRET.search(text_output(node)):
            raise ValueError('credential-shaped target')
        try: code_ast = ast_key(code)
        except SyntaxError: excluded['syntax_error'] += 1; continue
        if code_ast in blocked_ast: excluded['same_ast_as_memory'] += 1; continue
        if key in earliest: continue
        earliest[key] = dict(row, code=code, error=text_output(node), code_sha256=sha(code.encode()), ast_sha256=code_ast)
    chosen = []; available = {}
    for task in TASKS:
        pool = [r for r in earliest.values() if r['task'] == task]
        pool.sort(key=lambda r: sha((SALT+'\0'+'\0'.join(run_key(r))).encode()))
        available[task] = len(pool)
        chosen.extend(pool[:4])
    return chosen, available, dict(excluded)


def choose_memories(target, memories):
    pool = [m for m in memories if m['task'] == target['task'] and run_key(m) != run_key(target)]
    if not pool: raise ValueError('no same-task memory')
    families = set(target['message_families'])
    def relevance(m):
        return (len(families & set(m['parent_families'])), overlap(target['error'], m['error']),
                overlap(target['code'], m['parent_code']))
    ranked = sorted(pool, key=lambda m: (*(-v for v in relevance(m)), m['diff_sha256']))
    pool.sort(key=lambda m: (m['diff_sha256'], *run_key(m), m['parent_step']))
    seed = int(sha((SALT+'\0random\0'+'\0'.join(run_key(target))).encode())[:16], 16)
    return ranked[0], random.Random(seed).choice(pool)


def memory_text(row):
    return ('External historical example from another run; NOT a previous attempt in this episode. '
            'It was observed to execute and produce a valid-format submission after the change; '
            'this does not establish optimality or that the entire change is needed here. '
            'Adapt only if relevant and preserve the current solution methodology.\n'
            'Observed earlier error:\n'+row['error']+'\nObserved code change:\n'+row['observed_diff'])


def prepare():
    os.umask(0o077)
    summary = read(SUMMARY, SUMMARY_SHA)
    memories = read(INVENTORY, INVENTORY_SHA)['rows']
    if len(memories) != 11: raise ValueError('inventory size')
    nodes = {}; proof = []
    for item in summary['proof']:
        path = BASE/item['root']/'runs'/item['run_id']/'checkpoint/journal.jsonl'
        raw = path.read_bytes()
        if sha(raw) != item['journal_sha256']: raise ValueError('old journal drift')
        if SECRET.search(raw.decode()): raise ValueError('credential-shaped journal')
        for line in raw.splitlines():
            node = json.loads(line); key = (item['root'], item['run_id'], node['step'])
            if key in nodes: raise ValueError('duplicate node identity')
            nodes[key] = node
        proof.append(item)
    for m in memories: m['error'] = text_output(nodes[(*run_key(m), m['parent_step'])])
    targets, available, excluded = select_targets(summary['rows'], nodes, memories)
    root = Path(tempfile.mkdtemp(prefix='forets-repair-transfer-20260913-', dir=BASE))
    selected = []; public = []
    ready = all(v >= 4 for v in available.values())
    if ready:
        for index, target in enumerate(targets):
            relevant, random_m = choose_memories(target, memories)
            examples = dict(no_external_memory=None, retrieved_repair=relevant, random_repair=random_m)
            arm_order = ARMS[index % 3:] + ARMS[:index % 3]
            for arm in arm_order:
                m = examples[arm]
                row = dict(case=index, arm=arm, task=target['task'], root=target['root'], run_id=target['run_id'],
                    step=target['step'], seed=2026091300+index, code=target['code'], error=target['error'],
                    code_sha256=target['code_sha256'], ast_sha256=target['ast_sha256'],
                    memory=memory_text(m) if m else '', memory_diff_sha256=m['diff_sha256'] if m else None,
                    memory_run=list(run_key(m)) if m else None)
                selected.append(row)
                public.append({k:v for k,v in row.items() if k not in ('code', 'error', 'memory')})
    private_sha = dump(root/'inputs.private.json', dict(rows=selected))
    result = dict(status='PREPARED' if ready else 'INSUFFICIENT_DISJOINT_RUNS_NO_DISPATCH', root=str(root),
        source_summary_sha256=SUMMARY_SHA, inventory_sha256=INVENTORY_SHA, salt=SALT,
        available_target_runs=available, exclusions=excluded, cases=len(targets) if ready else 0,
        planned_calls=len(selected), rows=public, private_sha256=private_sha, source_proofs=proof,
        script_sha256=sha(Path(__file__).read_bytes()),
        role='retrospective_old_development_inputs_new_run_disjoint_repair_intervention_not_e2e',
        api_calls=0, gpu_jobs=0, outcome_values_used_to_retrieve=False,
        caveat='Old execution failure selects targets; not untouched-test or outcome-blind intake. Random memory can equal retrieved memory; lengths are not matched.')
    digest = dump(root/'selection-public.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows', 'source_proofs')} | dict(public_sha256=digest)))


if __name__ == '__main__': prepare()
