"""Read-only post-closure check of actual first returned prompt digests.

Does not read prompt content, labels, predictions or quality. A failed first call
does not prove its prompt identity, even if a later call returned successfully.
This supplements, never rewrites, the frozen experiment and its quality gate.
"""
import argparse
import hashlib
import json
from pathlib import Path

PLAN = 'cba9bad500a106b8c44f18116c491a1744edb50c3744c7f7ef1f498e45cdbd4f'
ORDER = ('old_fast', 'new_medium', 'new_fast', 'old_medium')


def verify(rows):
    assert len(rows) == 32
    for i, r in enumerate(rows):
        assert r['index'] == i and r['arm'] == ORDER[i // 8]
        assert r['seed'] == 214401 + i % 8
        assert r['first_call_success'] in (True, False, None)
        assert r['first_call_role'] in ('improve', 'draft', 'debug', 'analyze', None)
        if r['prompt_sha256'] is not None:
            assert len(r['prompt_sha256']) == 64
            int(r['prompt_sha256'], 16)
    groups = []
    for slot in range(8):
        group = [rows[slot + b * 8] for b in range(4)]
        observed = all(r['first_call_success'] is True and r['first_call_role'] == 'improve'
                       and r['prompt_role'] == 'improve' and r['prompt_sha256'] is not None for r in group)
        groups.append(dict(seed=214401 + slot, complete_first_call_evidence=observed,
                           all_four_equal=observed and len({r['prompt_sha256'] for r in group}) == 1))
    return dict(planned=32, paired_groups=8, pairs=groups,
                first_runtime_prompt_identity_verified=all(g['all_four_equal'] for g in groups),
                limitation='Returned-prompt digests only; failed first calls are unverified, not mismatches. Later search histories are allowed to diverge by treatment.')


def main(root, output):
    root = Path(root)
    assert (root/'closed.json').is_file(), 'Wait for batch closure'
    assert hashlib.sha256((root/'plan.json').read_bytes()).hexdigest() == PLAN
    plan = json.loads((root/'plan.json').read_text())
    rows = []
    for s in plan['schedule']:
        ep = root/f"episode-{s['index']}"
        def events(name):
            path = ep/name
            return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []
        calls, prompts = events('effort.jsonl'), events('prompt-hashes.jsonl')
        call, prompt = calls[0] if calls else {}, prompts[0] if prompts else {}
        for event in (call, prompt):
            if event:
                assert event['arm'] == s['arm']
                expected = 'qwen3.8-27b-score-step30' if s['arm'].startswith('new_') else 'qwen3.8-27b'
                assert event['model_id'] == expected
        rows.append(dict(index=s['index'], arm=s['arm'], seed=s['seed'],
                         first_call_success=call.get('success'), first_call_role=call.get('role'),
                         prompt_role=prompt.get('role'), prompt_sha256=prompt.get('sha256')))
    out = dict(verify(rows), plan_sha256=PLAN, source_commit=plan['source_commit'], rows=rows,
               verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with Path(output).open('x') as f:
        json.dump(out, f, indent=2, sort_keys=True, allow_nan=False)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root'); parser.add_argument('output')
    args = parser.parse_args()
    main(args.root, args.output)
