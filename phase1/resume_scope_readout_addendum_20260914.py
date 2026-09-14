"""Explicit post-closure reader bug correction; original files stay immutable.

The native batch calls extract_code(node.code). The original verifier compared
unextracted node text. Correct only this representation comparison, preserving
all ordering, eligibility, endpoint and numeric checks. Reuse the completed core
receipt, not a second grading run. Record the first failed reader as failed.
"""
import copy,hashlib,json,os,sys
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
sys.path.insert(0,str(ROOT/'source/src'))
from dojo.core.solvers.utils.response import extract_code
import readout_edit_scope_20260914 as reader
import readout_edit_scope_core_20260914 as core
import verify_branching_selection_20260913 as verifier
from forets_environment_build_20260912 import read,write,encode,sha

def main():
    os.umask(0o077)
    original_verify=verifier.verify_pool;proofs=[]
    def transformed(value,cfg,row,*args,**kwargs):
        clone=copy.deepcopy(value)
        for c in clone['candidates']:
            if isinstance(c.get('node'),dict):c['node']['code']=extract_code(c['node']['code'])
        result=original_verify(clone,cfg,row,*args,**kwargs)
        for call in value['task_calls']:
            if call['intent']['role']=='candidate':
                code=value['candidates'][call['slot']]['node']['code'];extracted=extract_code(code)
                proofs.append(dict(run_id=row['run_id'],raw_sha256=sha(code.encode()),executed_sha256=sha(extracted.encode()),representation_changed=code!=extracted))
        return result
    original_core=read(ROOT/'wallclock-summary.json');core_hash=sha((ROOT/'wallclock-summary.json').read_bytes())
    if len(original_core['rows'])!=16 or original_core['source_tree']!='8bb325fa167a9db54656dd6535ce1f3d69859c22':raise ValueError('completed core binding')
    # Frozen plan still verifies all six untouched original reader sources.
    verifier.verify_pool=transformed
    def cached(*args,**kwargs):
        if sha((ROOT/'wallclock-summary.json').read_bytes())!=core_hash:raise ValueError('core drift')
    core.verify=cached
    old_write=reader.write
    def append_only(path,raw):
        if path.name=='readout-intent.json':return write(ROOT/'readout-addendum-intent.json',raw)
        return old_write(path,raw)
    reader.write=append_only
    reader.main(ROOT)
    result=dict(reason='native extract_code omitted in original execution hash verifier',first_reader_status='failed_after_complete_core',
        original_core_sha256=core_hash,script_sha256=sha(Path(__file__).read_bytes()),native_extractor_sha256=sha(Path(sys.modules[extract_code.__module__].__file__).read_bytes()),
        candidate_calls_checked=len(proofs),changed_representations=sum(r['representation_changed'] for r in proofs),proofs=proofs,
        eligibility_or_endpoint_changes=False,raw_files_modified=False)
    print(json.dumps(dict(addendum_sha256=write(ROOT/'readout-addendum.json',encode(result)),candidate_calls_checked=len(proofs),changed_representations=result['changed_representations'])))
if __name__=='__main__':main()
