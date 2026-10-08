"""Source-only review of every clock hit in the frozen syntax screen.

Print structural expressions/call names, never string constants, complete source,
scores or prediction values. Not an execution or reachability validation.
"""
import ast
import json
from pathlib import Path
import signal

import census as c

SCREEN = c.BASE / 'scheduling-branch-screen-20261008-v1'


def expr(node):
    if isinstance(node, ast.Name): return {'name': node.id}
    if isinstance(node, ast.Constant):
        return {'literal': node.value if type(node.value) in (int, float, bool) else type(node.value).__name__}
    if isinstance(node, ast.Call):
        return {'call': c.dotted(node.func), 'args': [expr(x) for x in node.args]}
    if isinstance(node, ast.Attribute): return {'attribute': c.dotted(node)}
    return {'kind': type(node).__name__, 'children': [expr(n) for n in ast.iter_child_nodes(node) if not isinstance(n, ast.expr_context)]}


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('120s cap')))
    signal.alarm(120)
    screening = json.loads(c.read_pinned(SCREEN / 'branches.json'))
    targets = {(r['task'], r['source_sha256']): r for r in screening if any('clock' in b['sources'] for b in r['branches'])}
    structure = json.loads(c.read_pinned(c.STRUCTURE, c.STRUCTURE_SHA))
    sample = json.loads(c.read_pinned(c.SAMPLE, structure['sample_sha256']))['selected']
    seen = set(); reviewed = []
    for filename, pin in c.PINS.items():
        receipt = json.loads(c.read_pinned(c.ROOT / (filename + '.download.json')))
        if receipt['sha256'] != pin or receipt['credential_categories']: raise ValueError('source receipt mismatch')
        obj = json.loads(c.read_pinned(c.ROOT / filename, pin))
        for row in sample:
            if row['file'] != filename: continue
            for code in c.get_pair(obj, row):
                key = (row['task'], c.sha(code.encode()))
                if key not in targets or key in seen: continue
                seen.add(key); tree = ast.parse(code)
                parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
                branches = []
                clock_lines = {b['line'] for b in targets[key]['branches'] if 'clock' in b['sources']}
                for n in ast.walk(tree):
                    if not isinstance(n, (ast.If, ast.IfExp, ast.While)) or n.lineno not in clock_lines: continue
                    body = n.body if isinstance(n.body, list) else [n.body]
                    descendants = [x for b in body for x in ast.walk(b)]
                    ancestors = []; ancestor = parents.get(n)
                    while ancestor is not None:
                        if isinstance(ancestor, (ast.If, ast.While)):
                            ancestors.append(dict(line=ancestor.lineno, kind=type(ancestor).__name__, condition=expr(ancestor.test)))
                        elif isinstance(ancestor, (ast.For, ast.FunctionDef, ast.AsyncFunctionDef)):
                            ancestors.append(dict(line=ancestor.lineno, kind=type(ancestor).__name__))
                        ancestor = parents.get(ancestor)
                    branches.append(dict(line=n.lineno, kind=type(n).__name__, condition=expr(n.test), ancestors=ancestors,
                        calls=sorted({c.dotted(x.func) for x in descendants if isinstance(x, ast.Call)}),
                        assignments=sorted({x.id for x in descendants if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}),
                        break_lines=[x.lineno for x in descendants if isinstance(x, ast.Break)],
                        return_lines=[x.lineno for x in descendants if isinstance(x, ast.Return)]))
                reviewed.append(dict(task=key[0], source_sha256=key[1], branches=branches))
        del obj
    if seen != set(targets): raise ValueError('incomplete clock review coverage')
    output = SCREEN / 'review-v1'; output.mkdir(mode=0o700, exist_ok=False)
    c.save(output / 'structures.json', reviewed)
    hits = [r for r in reviewed if any(b['break_lines'] for b in r['branches'])]
    summary = dict(status='source_review_only', reviewed_programs=len(seen), execution=False,
        programs_with_clock_condition_and_break=len(hits), tasks_with_clock_condition_and_break=len({r['task'] for r in hits}),
        other_screen_hits=len(reviewed)-len(hits), reachability_verified=False,
        source_screen_sha256=c.sha((SCREEN / 'branches.json').read_bytes()),
        structures_sha256=c.sha((output / 'structures.json').read_bytes()), reviewer_sha256=c.sha(Path(__file__).read_bytes()))
    c.save(output / 'summary.json', summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__': main()
