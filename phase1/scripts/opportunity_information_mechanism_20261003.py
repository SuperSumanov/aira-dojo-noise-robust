"""Closed-all, credential-first inspection; never prints submissions or labels."""
import argparse, ast, hashlib, json, re
from pathlib import Path
R = Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2')
PLAN = '6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def read(p):
    raw = p.read_bytes()
    assert not SECRET.search(raw), 'credential-shaped content; do not print'
    return json.loads(raw)
def main():
    a = argparse.ArgumentParser(); a.add_argument('--index', type=int); a.add_argument('--step', type=int); a.add_argument('--brief', action='store_true'); q = a.parse_args()
    assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest() == PLAN
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    plan = read(R/'plan.json')
    for s in plan['schedule']:
        if q.index is not None and s['index'] != q.index: continue
        for step in range(1, 5):
            if q.step is not None and step != q.step: continue
            root = R/f'episode-{s["index"]}'/f'action-{step}'
            if not (root/'generation.private.json').exists(): continue
            g = read(root/'generation.private.json'); raw = g['response']
            result = read(root/'result.json') if (root/'result.json').exists() else None
            fmt = read(root/'format.json') if (root/'format.json').exists() else None
            codes = re.findall(r'```python\s*\n(.*?)```', raw, re.S)
            item = dict(index=s['index'], task=s['task'], arm=s['arm'], seed=s['seed'], step=step,
                returned=result is not None, format_status=fmt['status'] if fmt else None,
                execution_success=result['execution_success'] if result else None,
                valid=result['valid'] if result else None, generation_seconds=g['generation_seconds'],
                rationale=raw.split('```',1)[0][:1200] if q.brief else raw.split('```',1)[0], code_blocks=len(codes), raw_sha256=hashlib.sha256(raw.encode()).hexdigest())
            if q.step is not None:
                item['codes']=codes
            elif not q.brief:
                item['signatures']=[]
                for code in codes:
                    try: tree=ast.parse(code)
                    except SyntaxError: item['signatures'].append({'parse':'FAIL'}); continue
                    item['signatures'].append(dict(
                        lines=len(code.splitlines()),
                        calls=sorted(set(ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call))),
                        assignments=[ast.unparse(n)[:1000] for n in ast.walk(tree) if isinstance(n,(ast.Assign,ast.AugAssign,ast.AnnAssign))]))
            print(json.dumps(item))
if __name__=='__main__': main()
