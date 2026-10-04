"""Check actual recorded analysis input; no payloads or labels exported."""
import ast,hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
def strings(x):
    if isinstance(x,str):return [x]
    if isinstance(x,list):return [s for v in x for s in strings(v)]
    if isinstance(x,dict):return [s for k,v in x.items() for s in strings(v)]
    return []
out=[]
assert json.loads((R/'readout-v1/summary.json').read_bytes())['all_closed_receipts']
for i in range(8):
    for n in (json.loads(x) for x in (R/f'episode-{i}/checkpoint/journal.jsonl').read_bytes().splitlines() if x):
        if not n.get('operators_used'):continue
        ms=[m for role,m in zip(n['operators_used'],n['operators_metrics']) if role=='analysis'];assert len(ms)==1
        prompt='\n'.join(strings(ms[0].get('prompt_messages')))
        astree=ast.parse(n['code']);author_access=[]
        for a in ast.walk(astree):
            if isinstance(a,ast.Subscript) and isinstance(a.slice,ast.Constant) and a.slice.value=='author':
                author_access.append(dict(line=a.lineno,base=ast.unparse(a.value)))
        terminal=n.get('term_out','')
        terminal=''.join(terminal) if isinstance(terminal,list) else terminal
        measured_lines=[s for s in terminal.splitlines() if re.search(r'Fold \d+: CV Log Loss = \d|Average CV Log Loss: \d|Total execution time: \d',s)]
        out.append(dict(index=i,code_sha256=hashlib.sha256(n['code'].encode()).hexdigest(),
            prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),full_code_in_prompt=n['code'] in prompt,
            author_access=author_access,full_recorded_terminal_in_prompt=bool(terminal) and terminal in prompt,
            measured_terminal_lines=len(measured_lines),all_measured_lines_in_prompt=bool(measured_lines) and all(s in prompt for s in measured_lines),
            has_traceback_in_prompt='Traceback' in prompt))
result=dict(scope='posthoc recorded prompt inclusion, not new execution or model call',rows=out,
    caveat='Substring matching arbitrary success wording also matches program print literals and is not used as proof; compare full recorded terminal and numerical output lines instead.')
with (R/'prompt-factcheck-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
print(json.dumps(result))
