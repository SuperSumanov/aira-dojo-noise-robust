"""Exercise all actual code-delivery/config paths without using GPU or labels."""
import json,os,shutil,sys,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from run_comparison_spooky_pool_20260919 import prepared,setup,read,write,sha,one

def main(root):
    p=prepared(root);setup(root,p['commit']);counts=dict(calls=0,cleanups=0)
    with tempfile.TemporaryDirectory(prefix='cpu-check-',dir=root) as temporary:
        target=Path(temporary);(target/'configs').mkdir();(target/'codes').mkdir()
        for row in p['rows']:
            i=row['index'];config=read(root/'configs'/f'{i}.json');config['working_dir']=str(target/f'work-{i}')
            write(target/'configs'/f'{i}.json',config);shutil.copy2(root/'codes'/f'{i}.private.py',target/'codes'/f'{i}.private.py')
            class Fake:
                def __init__(self,cfg,data_dir):
                    if cfg.timeout!=7200 or data_dir.name!='public' or set(cfg.env.values())!={'6'}:raise ValueError('config contract')
                    self.work=Path(cfg.working_dir)
                def run(self,code,**kwargs):
                    if sha(code.encode())!=row['code_sha256']:raise ValueError('code delivery')
                    counts['calls']+=1
                    write(Path(os.environ['DOJO_WORKER_IDENTITY_PATH']).with_suffix('.native-binding.json'),dict(namespace=dict(exact_device_namespace=True)))
                    (self.work/'submission.csv').write_text('id,target\n1,0\n')
                    return NS(term_out=['mock'],exit_code=0,timed_out=False,exec_time=.001)
                def fetch_file(self,path):return str(path)
                def close(self):counts['cleanups']+=1
            outcome=one(target,row,Fake)
            if outcome['status']!='returned' or not outcome['submission_sha256']:raise ValueError('actual driver failed')
    if counts!={'calls':18,'cleanups':18}:raise ValueError('incomplete mock matrix')
    receipt=dict(status='PASS',kind='CPU_MOCK_NOT_GPU_ACCEPTANCE',cases=18,counts=counts,
        prepared_sha256=sha((root/'prepared.json').read_bytes()))
    write(root/'cpu-preflight.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':main(Path(sys.argv[1]))
