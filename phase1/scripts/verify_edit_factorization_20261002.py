"""Independent read-only qualification of saved edit-factorization artifacts.

No imports/execution of candidate programs and no metric-based selection.
Name checks are conservative diagnostics, NOT proofs of execution validity.
"""
import ast
import builtins
import difflib
import hashlib
import json
import re
import symtable
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
ROOT = B / 'edit-factorization-census-20261002-v1'
EXPECTED = '3de13b0b85d25da6f68b941a0d2e2db142754200aa6b525edde3c5579e21e582'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    raw = p.read_bytes()
    assert not SECRET.search(raw), 'credential-bearing artifact withheld'
    return json.loads(raw)


def keys(source):
    return [ast.dump(n, include_attributes=False) for n in ast.parse(source).body]


def unresolved(source):
    table = symtable.symtable(source, 'candidate', 'exec')
    defined = {s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported() or s.is_parameter()}
    external = set(dir(builtins)) | {'__name__', '__file__', '__package__', '__doc__', '__builtins__', '__annotations__', '__spec__', '__loader__'}
    names = set()
    def walk(t):
        for s in t.get_symbols():
            if s.is_referenced() and (t.get_type() == 'module' or s.is_global()):
                if s.get_name() not in defined | external:
                    names.add(s.get_name())
        for child in t.get_children():
            walk(child)
    walk(table)
    return names


def main():
    assert digest(ROOT / 'summary.json') == EXPECTED
    summary = read(ROOT / 'summary.json')
    plan = read(ROOT / 'plan.json')
    assert digest(ROOT / 'plan.json') == summary['plan_sha256']
    # Independent enumeration: every returned improve action has a valid parent
    # selected before it. We do not replay the producer's debug-streak state.
    expected = {}
    for basename, psha in plan['roots'].items():
        old = B / basename
        assert digest(old / 'plan.json') == psha
        assert (old / 'all-closed.json').is_file()
        for s in read(old / 'plan.json')['schedule']:
            ep = old / f'episode-{s["index"]}'
            chosen = None
            for a in sorted(ep.glob('action-*'), key=lambda p: int(p.name.split('-')[1])):
                n = int(a.name.split('-')[1])
                if not (a / 'result.json').exists() or not (a / 'node.private.json').exists():
                    break
                r = read(a / 'result.json')
                code = read(a / 'node.private.json')['code']
                h = hashlib.sha256(code.encode()).hexdigest()
                assert r['code_sha256'] == h
                if n and r['kind'] == 'improve':
                    assert chosen is not None
                    expected[basename, s['index'], n] = (chosen[0], chosen[1], h)
                if (a / 'selected.json').exists():
                    assert r['valid']
                    chosen = (n, h)
    actual = {}
    diagnostics = []
    for index, row in enumerate(summary['rows']):
        identity = row['batch'], row['episode'], row['step']
        assert identity not in actual
        actual[identity] = (row['parent_step'], row['parent_raw_sha256'], row['child_raw_sha256'])
        if row.get('distinct_variants') != 4:
            continue
        folder = ROOT / f'{index:03d}.private'
        programs = {n: (folder / f'{n}.py').read_text() for n in ('parent', 'child', 'left', 'right')}
        for n in programs:
            assert not SECRET.search(programs[n].encode())
            compile(programs[n], n, 'exec')
        for n, h in zip(('left', 'right'), row['partial_sha256']):
            assert digest(folder / f'{n}.py') == h
        a, b = keys(programs['parent']), keys(programs['child'])
        opcodes = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes()
        blocks = [o for o in opcodes if o[0] != 'equal']
        assert len(blocks) == row['edit_blocks']
        cut = (len(blocks) + 1) // 2
        for side, name in enumerate(('left', 'right')):
            expected_keys = []; ordinal = 0
            for tag, i, j, k, l in opcodes:
                if tag == 'equal':
                    expected_keys.extend(a[i:j]); continue
                use_child = ordinal < cut if side == 0 else ordinal >= cut
                expected_keys.extend(b[k:l] if use_child else a[i:j]); ordinal += 1
            assert keys(programs[name]) == expected_keys
        original_missing = unresolved(programs['parent']) | unresolved(programs['child'])
        introduced = {n: sorted(unresolved(programs[n]) - original_missing) for n in ('left', 'right')}
        diagnostics.append(dict(index=index, task=row['task'], batch=row['batch'], episode=row['episode'], step=row['step'],
                                new_unresolved_count={n: len(v) for n, v in introduced.items()},
                                both_without_new_unresolved=not any(introduced.values())))
    assert actual == expected
    result = dict(status='PASS_STRUCTURAL_RECONSTRUCTION_ONLY', summary_sha256=EXPECTED,
                  verifier_sha256=digest(Path(__file__)), parent_bindings=len(actual),
                  four_vertices=len(diagnostics), diagnostics=diagnostics,
                  both_without_new_unresolved=sum(d['both_without_new_unresolved'] for d in diagnostics),
                  note='Missing-global-name heuristic only; dynamic imports, use-before-definition, dependent tensor shapes and dead branches remain unresolved. No execution or effect.')
    with (ROOT / 'verification.json').open('x') as f:
        json.dump(result, f, sort_keys=True, indent=2); f.write('\n')
    brief = {k: v for k, v in result.items() if k not in ('diagnostics', 'note')}
    brief['by_task'] = {t: dict(factorizable=sum(d['task'] == t for d in diagnostics),
                               both_without_new_unresolved=sum(d['task'] == t and d['both_without_new_unresolved'] for d in diagnostics))
                       for t in sorted({d['task'] for d in diagnostics})}
    print(json.dumps(brief, sort_keys=True))


if __name__ == '__main__':
    main()
