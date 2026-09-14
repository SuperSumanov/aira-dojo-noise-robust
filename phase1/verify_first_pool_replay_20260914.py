"""Actual driver with mock execution only; no new GPU acceptance."""
import json,os,shutil,sys,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from run_first_pool_replay_20260914 import prepared,inputs,one,setup,write,sha
def main(root):
    p=prepared(root);rows,codes,configs=inputs()
    if rows!=p['rows']:raise ValueError('independent current all-source first-pool reconstruction')
    setup(root,p);counts=dict(calls=0,cleanups=0)
    with tempfile.TemporaryDirectory(prefix='cpu-replay-',dir=root) as temp:
        tmp=Path(temp);(tmp/'configs').mkdir();(tmp/'codes').mkdir()
        for row in rows:
            i=row['index'];cfg=json.loads((root/'configs'/f'{i}.json').read_bytes());cfg['working_dir']=str(tmp/f'work-{i}')
            write(tmp/'configs'/f'{i}.json',cfg);shutil.copy2(root/'codes'/f'{i}.private.py',tmp/'codes'/f'{i}.private.py')
            class Fake:
                def __init__(self,cfg,data_dir):
                    if cfg.timeout!=300 or data_dir.name!='public':raise ValueError('actual fake boundary contract')
                    self.work=Path(cfg.working_dir)
                def run(self,code,**kw):
                    if sha(code.encode())!=row['code_sha256'] or kw['file_name']!='solution.py':raise ValueError('native delivery')
                    counts['calls']+=1
                    write(Path(os.environ['DOJO_WORKER_IDENTITY_PATH']).with_suffix('.native-binding.json'),{'mock':True})
                    (self.work/'submission.csv').write_text('id,target\n1,0\n')
                    return NS(term_out=['mock'],exit_code=0,timed_out=False,exec_time=.001)
                def fetch_file(self,path):return str(path)
                def close(self):counts['cleanups']+=1
            r=one(tmp,row,factory=Fake)
            if r['status']!='returned' or not r['submission_sha256']:raise ValueError('actual driver output')
    if counts!={'calls':24,'cleanups':24}:raise ValueError('all24 actual driver paths')
    result=dict(status='PASSED_CPU_DRIVER_NOT_GPU_ACCEPTANCE',source_tree=p['source_tree'],prepared_sha256=sha((root/'prepared.json').read_bytes()),
        actual_cases=24,counts=counts,api_calls=0,gpu_jobs=0,script_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(sha256=write(root/'cpu-preflight.json',result),**result)))
if __name__=='__main__':main(Path(sys.argv[1]))
