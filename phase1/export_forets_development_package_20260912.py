"""Export only our already-unblinded generated programs and safe development receipts."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

BASE=Path('/research/d7/spc/yzyang4')
INPUTS=(('s16_s17','asl_0ytg','1ab23e7ff96910cdd3a73a671e9139c20edbc2856abf237060d6f4fa0c1d23e2'),
        ('s18_s19','hp7jtagu','84ff9345b0123f90555b278371308be3680ebf6d2d5a362eaa8377efa2ceeba7'),
        ('s20_s21','thgk111r','76c3387a3ff942aaffa60c996c293d0b73dea761a2f532fb32b1c193a07afcc3'))
SECRET=re.compile(rb'(?i)sk-[a-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|ghp_[a-zA-Z0-9]{20,}|BEGIN[^\n]*PRIVATE KEY')


def build():
    files={};records=[];pools=[];sources=[]
    for batch,suffix,expected in INPUTS:
        root=BASE/('forets-generation-capacity-20260912-'+suffix)
        raw=(root/'generation-capacity-summary.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('closed receipt changed')
        summary=json.loads(raw)
        rows=list(csv.DictReader((root/'generation-capacity-runs.csv').open(newline='')))
        if len(rows)!=8 or not summary['all_program_slots_included'] or summary['protected_cohort_read']:raise ValueError('scope')
        sources.append(dict(batch=batch,job=summary['job'],controller_commit=summary['controller_commit'],
                            source_tree=summary['source_tree'],summary_sha256=expected))
        for row in rows:
            i=int(row['index']);path=root/'codes'/f'{i}.py';code=path.read_bytes()
            if path.is_symlink() or hashlib.sha256(code).hexdigest()!=row['code_sha256'] or SECRET.search(code):
                raise ValueError('code drift/security')
            name=f'{batch}/code-{i}.py';files[name]=code
            fields=('task','model','replicate','status','valid','score','execution_seconds','api_cost_usd',
                    'code_sha256','submission_sha256','image_version','node','allocated_cpus','allocated_gpu_count')
            record={k:row[k] for k in fields};record.update(batch=batch,index=i,code_path=name)
            # Only final exception messages, never full candidate stdout, data or labels.
            if row['valid']=='False':
                output=(root/f'program-{i}.txt').read_bytes()
                if hashlib.sha256(output).hexdigest()!=row['output_sha256'] or SECRET.search(output):raise ValueError('output drift/security')
                plain=re.sub(r'\x1b\[[0-9;]*m','',output.decode())
                errors=re.findall(r'(?m)^(?:[\w.]*Error|Exception):[^\n]*',plain)
                record['final_exception_line']=errors[-1] if errors else None
            else:record['final_exception_line']=None
            records.append(record)
        for selection in summary.get('blind_selection',[]):
            pools.append(dict(batch=batch,**selection))
    manifest=dict(role='unblinded_development_diagnostic_not_frozen_evaluation',programs=len(records),
        valid=sum(r['valid']=='True' for r in records),tasks=sorted({r['task'] for r in records}),sources=sources,
        limitations=['All outcomes already inspected. Never report this as a fresh held-out test.',
            '24 programs are not 24 search runs; only two tasks, three sampling batches and four blind-ranked pools.',
            'Mixed generators, single execution per program, additional judge fees; not equal-budget e2e evidence.',
            'Do not feed labels or exception lines to a pre-execution critic when studying its information boundary.'],
        files_sha256={k:hashlib.sha256(v).hexdigest() for k,v in files.items()})
    for name,value in [('manifest.json',manifest),('programs.json',records),('blind-pools.json',pools)]:
        files[name]=json.dumps(value,indent=2,allow_nan=False).encode()
    if any(SECRET.search(v) for v in files.values()):raise ValueError('export credential shape')
    directory=Path(tempfile.mkdtemp(prefix='forets-development-export-20260912-',dir=BASE));os.chmod(directory,0o700)
    archive=directory/'forets-development-20260912.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in sorted(files.items()):z.writestr(name,raw)
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist())!=set(files) or any(z.read(k)!=v for k,v in files.items()):raise ValueError('archive mismatch')
    print(json.dumps(dict(path=str(archive),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                         bytes=archive.stat().st_size,files=len(files),programs=len(records),valid=manifest['valid'])))


if __name__=='__main__':build()
