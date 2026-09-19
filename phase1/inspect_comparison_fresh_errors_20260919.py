"""Closed-run failure diagnoses; emit no code, prompt, or complete log."""
import hashlib, json, re
from pathlib import Path
from discover_comparison_20260919 import SECRET, safe_text

ROOT = Path('/research/d7/spc/yzyang4/comparison-fresh-debug-exec-20260919-53mn3zh0')

def main():
    summary = (ROOT/'summary.json').read_bytes()
    data = json.loads(summary)
    if data['job'] != '14133' or data['allocation_state'] != 'COMPLETED':
        raise ValueError('closed allocation required')
    rows = []
    for row in data['rows']:
        raw = (ROOT/f'output-{row["index"]}.private.log').read_bytes()
        clean = SECRET.sub('[REDACTED]',raw.decode())
        clean = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',clean)
        matches = re.findall(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)',clean)
        error = safe_text(matches[-1].strip())[:400] if matches else None
        code = (ROOT/'codes'/f'{row["index"]}.private.py').read_bytes()
        if hashlib.sha256(code).hexdigest() != row['code_sha256']:
            raise ValueError('code identity')
        rows.append(dict(seed=row['seed'],request_seed=row['request_seed'],code_sha256=row['code_sha256'],
            log_sha256=hashlib.sha256(raw).hexdigest(),credential_shape_hits=len(SECRET.findall(raw.decode())),
            terminal_error=error,exit_code=row['exit_code'],timed_out=row['timed_out']))
    result = dict(role='closed_fresh_debug_error_diagnosis',source_summary_sha256=hashlib.sha256(summary).hexdigest(),rows=rows)
    payload = json.dumps(result,indent=2)+'\n'
    if SECRET.search(payload):
        raise ValueError('output security')
    with (ROOT/'errors.redacted.json').open('x') as handle:
        handle.write(payload)
    print(payload)

if __name__ == '__main__':
    main()
