"""Read-only fixed-job warmup diagnostic. No candidate code or secrets emitted."""
import json
from pathlib import Path
import re

R = Path('/research/d7/spc/yzyang4/scheduling-neural-overlap-20261008-v1')

def main():
    launch = json.loads((R/'launch.json').read_text())
    if launch['job'] != '17014' or not (R/'closed.json').exists():
        raise ValueError('closed exact job required')
    ep = R/'episode-36'
    result = {'job': '17014', 'warmup_receipts': {}, 'logs': []}
    allowed = ('returncode', 'start', 'end', 'time', 'stage', 'exit_code',
               'timed_out', 'exec_seconds', 'timeout_phase', 'complete', 'error_type')
    for name in ('closed.json', 'completed.json', 'candidate_started.json',
                 'candidate_ended.json', 'cell-0.json'):
        path = ep/name
        if path.exists():
            record = json.loads(path.read_text())
            result['warmup_receipts'][name] = {k:record[k] for k in allowed if k in record}
    shapes = re.compile(r'(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})')
    for path in (ep/'worker.private.log', ep/'cell-0.private.txt', R/'allocation-17014.err'):
        if not path.exists():
            continue
        text = path.read_text(errors='replace')
        frames = [{'file':Path(p).name,'line':int(n),'function':f}
                  for p,n,f in re.findall(r'File "([^"\n]+)", line (\d+), in ([^\n]+)', text)]
        result['logs'].append({'file':path.name, 'bytes':path.stat().st_size,
            'credential_shape_hits':len(shapes.findall(text)), 'trace_frames':frames,
            'exception_types':sorted(set(re.findall(r'\b([A-Za-z_]*(?:Error|Exception|Exit))\b',text))),
            'diagnostic_terms':[t for t in ('kernel did not', 'kernel readiness', 'timeout', 'deadline',
                'out of memory', 'permission denied', 'address already in use', 'connection refused',
                'recursion', 'no module named', 'maximum') if t in text.lower()]})
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
