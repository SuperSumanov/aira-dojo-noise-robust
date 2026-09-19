"""Coarse historical runtime markers for original choices already replayed.

Only bounded, credential-redacted timeout excerpts enter a remote private receipt.
No code/env is exported; not an automatic cause attribution or public artifact.
"""
import hashlib,json,re,tarfile
from pathlib import Path,PurePosixPath
from discover_comparison_20260919 import SECRET,safe_text

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'comparison-quarantine-20260919-_tda9fh6'
REPLAY=BASE/'comparison-pool-20260919-7ujiaajp'


def text_values(value):
    if isinstance(value,str):return value
    if isinstance(value,list):return '\n'.join(text_values(x) for x in value)
    if isinstance(value,dict):return '\n'.join(text_values(x) for x in value.values())
    return ''


def main():
    raw=(REPLAY/'summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!='238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a':raise ValueError('closed readout identity')
    wanted={r['node']:r for r in json.loads(raw)['rows'] if r['original_selected'] and r['valid'] is not None}
    records=[]
    with tarfile.open(ROOT/'archives/leaf-classification.tar.gz','r|gz') as archive:
        for member in archive:
            if not member.isfile() or PurePosixPath(member.name).name!='journal.jsonl':continue
            for line in archive.extractfile(member):
                node=json.loads(SECRET.sub('[REDACTED]',line.decode()))
                if node.get('id') not in wanted:continue
                row=wanted[node['id']]
                if hashlib.sha256((node.get('code') or '').encode()).hexdigest()!=row['raw_code_sha256']:raise ValueError('code identity')
                text=text_values(node.get('term_out'))+'\n'+text_values(node.get('_term_out'))
                text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
                ready_seconds=re.findall(r"Kernel didn.t respond in ([0-9]+(?:\.[0-9]+)?) seconds",text)
                markers={name:bool(re.search(pattern,text,re.I)) for name,pattern in {
                    'timeout':'timed out|TimeoutError|time limit exceeded',
                    'kernel':'dead kernel|kernel died|kernel.*restart|kernel.*timeout',
                    'import':'ImportError|ModuleNotFoundError',
                    'file_missing':'FileNotFoundError|No such file or directory',
                    'device':'CUDA error|invalid device ordinal|no kernel image',
                    'memory':'OutOfMemoryError|out of memory|MemoryError',
                    'argument':'unexpected keyword|TypeError',
                    'value':'ValueError',
                    'permission':'Permission denied|PermissionError',
                    'keyboard_interrupt':'KeyboardInterrupt',
                }.items()}
                records.append(dict(seed=row['seed'],slot=row['slot'],node=node['id'],
                    historical_exit_code=node.get('exit_code'),historical_buggy=node.get('is_buggy'),
                    historical_execution_seconds=node.get('exec_time'),fresh_valid=row['valid'],
                    canonical_kernel_ready_timeout_seconds=sorted(set(float(x) for x in ready_seconds)),
                    timeout_context_redacted=[safe_text(t)[:350] for t in text.splitlines()
                        if re.search(r'timed out|TimeoutError|kernel.*timeout',t,re.I)][:6],
                    markers=markers,output_text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    if len(records)!=len(wanted) or len({r['node'] for r in records})!=len(wanted):raise ValueError('scope incomplete')
    result=dict(replay_summary_sha256=hashlib.sha256(raw).hexdigest(),rows=records,
                caveat='Keyword markers may describe warnings; not proof of root cause. Bounded redacted timeout excerpts are remote-private only; no code/env exported.')
    with (REPLAY/'historical-runtime-detail-v3.private.json').open('x') as out:json.dump(result,out,indent=2)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
