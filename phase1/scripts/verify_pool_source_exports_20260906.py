"""Verify actual Windows git-archive exports against Git and run receipts."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

def h(raw):return hashlib.sha256(raw).hexdigest()

def run():
    root=Path('phase1/results/historical_pool_lineage_20260906')
    records=[]
    for stage,bundle in [('srun_stage','historical-pool-14e38d2.tar'),('combined_stage','historical-pool-retry.tar')]:
        summary=json.loads((root/stage/'summary.json').read_bytes())
        context=json.loads((root/stage/'execution_context.json').read_bytes())
        archive=Path('tmp')/bundle
        assert h(archive.read_bytes())==context['source_bundle_sha256']
        files=[]
        with tarfile.open(archive) as tar:
            for m in tar:
                if not m.isfile():continue
                assert m.name.startswith('phase1/') and m.name.endswith('.py')
                exported=tar.extractfile(m).read()
                git=subprocess.check_output(['git','show',context['source_commit']+':'+m.name])
                assert exported.replace(b'\r\n',b'\n')==git
                assert ast.dump(ast.parse(exported))==ast.dump(ast.parse(git))
                files.append({'path':m.name,'git_blob_sha256':h(git),'executed_export_sha256':h(exported),
                              'export_crlf_lines':exported.count(b'\r\n'),'LF_normalized_byte_equal':True,'ast_equal':True})
                if m.name=='phase1/recover_historical_pool_lineage.py':assert h(exported)==summary['source_sha256']
        records.append({'stage':stage,'source_commit':context['source_commit'],
                        'source_bundle_sha256':h(archive.read_bytes()),'python_files':files})
    result={'status':'ACTUAL_FIXED_ARCHIVE_MATCHES_RECEIPTS_AND_NORMALIZED_GIT_SOURCE',
            'records':records,'original_receipts_changed':False,
            'next_export_rule':'git -c core.autocrlf=false archive; validate exported bytes before execution',
            'git_version':subprocess.check_output(['git','--version']).decode().strip()}
    out=root/'source_export_integrity.json'
    with out.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,sort_keys=True);f.write('\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':run()
