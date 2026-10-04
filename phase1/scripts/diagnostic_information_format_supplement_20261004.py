"""Syntax-only posthoc audit of rejected replies. Never runs or rescues code."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

R = Path('/research/d7/spc/yzyang4/diagnostic-information-20261004-v1')
PLAN = '63322ce2f5e38ac22c2a98b2c7bae5fa27334c4d5f3052297938418c26627679'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+\S{12,})')

def read(p):
    raw = p.read_bytes()
    assert not SECRET.search(raw), 'credential shape; output withheld'
    return json.loads(raw)

def describe(raw):
    header = raw.split('```',1)[0]
    blocks = re.findall(r'```python\s*\n(.*?)```',raw,re.S)
    syntax = False
    if len(blocks)==1:
        try:
            ast.parse(blocks[0])
            syntax = True
        except SyntaxError:
            pass
    # A bounded lexical description, not action inference from arbitrary prose.
    bold = re.findall(r'(?m)^\s*\*\*(CHECK|SOLUTION)\*\*\s*$',header)
    inline = re.findall(r'(?m)^\s*(CHECK|SOLUTION)\s*[:\u2014\u2013-]\s*\S.*$',header)
    return dict(one_complete_python_block=len(blocks)==1, python_ast_parseable=syntax,
                bold_standalone_markers=len(bold), inline_mode_prefixes=len(inline),
                explicit_prefix_modes=sorted(set(bold+inline)))

def main():
    assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest()==PLAN
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    audit=read(R/'readout-v1/format-audit.json')
    rows=[]
    for a in audit['rows']:
        if a.get('format_status')!='REJECT':
            continue
        raw=read(R/f"episode-{a['index']}/action-{a['step']}/generation.private.json")['response']
        assert hashlib.sha256(raw.encode()).hexdigest()==a['response_sha256']
        rows.append(dict(index=a['index'],step=a['step'],arm=a['arm'],task=a['task'],
                         response_sha256=a['response_sha256'],**describe(raw)))
    assert len(rows)==audit['rejected']==23
    counts={k:sum(r[k] is True for r in rows) for k in ('one_complete_python_block','python_ast_parseable')}
    counts.update(bold_standalone=sum(bool(r['bold_standalone_markers']) for r in rows),
                  inline_prefix=sum(bool(r['inline_mode_prefixes']) for r in rows),
                  no_recognized_prefix=sum(not r['explicit_prefix_modes'] for r in rows))
    payload=dict(plan_sha256=PLAN,status='POSTHOC_SYNTAX_ONLY',rejected=23,counts=counts,rows=rows,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        boundary='Descriptive overlapping surface categories, not a new parser. AST parseability does not establish safe execution, task validity or gain. No rejected response executed, no frozen result changed; unrecognized prefix is not proof the mode is semantically absent.')
    raw=(json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw)
    with (R/'readout-v1/format-syntax-supplement.json').open('xb') as f:
        f.write(raw)
    print(json.dumps(dict(status=payload['status'],counts=counts,sha256=hashlib.sha256(raw).hexdigest())))

if __name__=='__main__':
    main()
