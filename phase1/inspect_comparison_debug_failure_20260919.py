"""Check whether fresh first-debug failure also occurred in producer execution."""
import hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
from discover_comparison_20260919 import SECRET,safe_text
BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'comparison-reuse-20260919-5m6jrtah'
raw=(ROOT/'summary.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!='f3ea334c94257bbbbc06229a8a3aeea609e2516879bdf9a32822e176897ee9ce':raise ValueError('closed result identity')
row,=[r for r in json.loads(raw)['rows'] if r['seed']==1 and r['role']=='debug']
def terminal(value):
    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',value)
    matches=re.findall(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)',text)
    return safe_text(matches[-1].strip()) if matches else None
fresh=(ROOT/f'output-{row["index"]}.private.log').read_text()
if SECRET.search(fresh):raise ValueError('fresh log credential shape')
matches=[]
with tarfile.open(BASE/'comparison-quarantine-20260919-_tda9fh6/archives/spooky-author-identification.tar.gz','r|gz') as archive:
    for member in archive:
        p=PurePosixPath(member.name)
        if not member.isfile() or p.name!='journal.jsonl':continue
        if hashlib.sha256(str(p.parent.parent).encode()).hexdigest()[:16]!=row['run']:continue
        for line in archive.extractfile(member):
            text=SECRET.sub('[REDACTED]',line.decode());n=json.loads(text)
            if n.get('id')!=row['node']:continue
            historical=n.get('_term_out') or n.get('term_out') or ''
            if isinstance(historical,list):historical=''.join(historical)
            digest=hashlib.sha256((n.get('code') or '').encode()).hexdigest()
            if digest!=row['raw_code_sha256']:raise ValueError('debug source code identity')
            matches.append(dict(node=row['node'],run=row['run'],raw_code_sha256=digest,
                historical_exit_code=n.get('exit_code'),historical_is_buggy=n.get('is_buggy'),
                fresh_exit_code=row.get('exit_code'),historical_terminal_error=terminal(historical),
                fresh_terminal_error=terminal(fresh),same_terminal_error=terminal(historical)==terminal(fresh)))
if len(matches)!=1:raise ValueError('unique source debug record')
out=dict(role='same_code_historical_debug_error_check',source_summary_sha256=hashlib.sha256(raw).hexdigest(),records=matches)
payload=json.dumps(out,indent=2)
if SECRET.search(payload):raise ValueError('output security')
with (ROOT/'debug-history.redacted.json').open('x') as handle:handle.write(payload+'\n')
print(payload)
