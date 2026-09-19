"""Explicit third-prefix extension; prior unstarted and completed banks immutable."""
import argparse, json, os, re, tarfile
from pathlib import Path, PurePosixPath
import run_comparison_reuse_20260919 as driver

RUN='e4a4275f2df8028e'
def configure():
    driver.RUNS={3:RUN}
    driver.ROOT_PREFIX='comparison-third-bank-20260919-'
    driver.ALLOCATION_SECONDS=7800
    driver.SCRIPT=Path(__file__).name
    driver.PLAN='comparison_third_bank_plan_20260919.json'
    driver.READER='readout_comparison_third_bank_20260919.py'
    driver.CONTEXT_MODULE='run_comparison_third_bank_20260919'
    driver.EXTRA_FILES=('run_comparison_reuse_20260919.py','readout_comparison_reuse_20260919.py','verify_comparison_reuse_driver_20260919.py')

def prefix_error():
    configure()
    rows=driver.select_rows(driver.read(driver.INPUT/'qwen-readout-v1/nodes.json',driver.NODES))
    prefix,=[r for r in rows if r['role']=='prefix']
    errors=[]
    with tarfile.open(driver.INPUT/'archives/spooky-author-identification.tar.gz','r|gz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            if not member.isfile() or p.name!='journal.jsonl' or driver.sha(str(p.parent.parent).encode())[:16]!=RUN:continue
            for line in archive.extractfile(member):
                if driver.SECRET.search(line):raise ValueError('credential-first prefix')
                node=json.loads(line)
                if node.get('id')!=prefix['node']:continue
                if driver.sha(node['code'].encode())!=prefix['raw_code_sha256']:raise ValueError('prefix code identity')
                raw=node.get('_term_out') or node.get('term_out') or ''
                text=''.join(raw) if isinstance(raw,list) else raw
                text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
                matches=re.findall(r'(?m)^\s*((?:\w+Error|Exception):[^\n]*)',text)
                if not matches:raise ValueError('unrecognized original prefix error')
                core=re.sub(r'\s+Execution time:.*$','',matches[-1].strip())
                if driver.SECRET.search(core.encode()):raise ValueError('error security')
                errors.append(core)
    if len(errors)!=1:raise ValueError('unique original prefix error')
    return errors[0]

def prepared(root):
    configure();return driver.prepared(root)

def binding_context(env):
    configure();return driver.binding_context(env)

if __name__=='__main__':
    os.umask(0o077);configure()
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','cpu','submit','coordinate','execute','prefix'])
    parser.add_argument('--root',type=Path);parser.add_argument('--commit');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.mode=='prefix':print(json.dumps(dict(run=RUN,prefix_error=prefix_error())))
    elif args.mode=='prepare':
        prior=driver.read(driver.BASE/'comparison-spooky-pool-20260919-04qsl2xc/summary.json','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1')
        if any(r['status']!='not_started' for r in prior['rows'] if r['seed']==3):raise ValueError('original third pool attempted')
        driver.PREPARED_METADATA=dict(source_run=RUN,historical_prefix_error=prefix_error())
        driver.prepare(args.commit)
    elif args.mode=='cpu':
        import verify_comparison_reuse_driver_20260919 as checker
        checker.prepared=prepared;checker.main(args.root)
    elif args.mode=='execute':driver.execute(args.root,args.index)
    else:getattr(driver,args.mode)(args.root)
