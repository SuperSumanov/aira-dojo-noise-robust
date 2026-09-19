"""Build an isolated default-off source tree, no GPU/model calls or jobs."""
import argparse,hashlib,importlib,json,os,re,signal,sys,tarfile,tempfile
from pathlib import Path,PurePosixPath
import forets_action_incumbent_patch_20260919 as patcher
import local_generator_runtime_20260914 as rt

def main(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    os.umask(0o077);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('CPU preparation deadline')));signal.alarm(180)
    if rt.sha(rt.ASSETS/'source.tar')!=rt.SOURCE_SHA:raise ValueError('original source archive drift')
    original=rt.ASSETS/'source';required=set(patcher.EXPECTED)|set(patcher.EXPECTED_EXTRA)
    replacements=patcher.build({name:(original/name).read_text() for name in required})
    root=Path(tempfile.mkdtemp(prefix='forets-ready-source-20260919-',dir=rt.BASE));tree=root/'source';tree.mkdir()
    originals={};installed={}
    with tarfile.open(rt.ASSETS/'source.tar') as archive:
        for member in archive:
            rel=PurePosixPath(member.name)
            if rel.is_absolute() or '..' in rel.parts or not (member.isdir() or member.isfile()):raise ValueError('archive shape')
            if member.isdir():continue
            raw=archive.extractfile(member).read()
            if rt.SHAPES.search(raw):raise ValueError('credential-shaped source')
            if (original/member.name).is_symlink() or (original/member.name).read_bytes()!=raw:raise ValueError('original extracted source drift')
            target=tree/member.name;target.parent.mkdir(parents=True,exist_ok=True)
            output=replacements.get(member.name,raw)
            with target.open('xb') as handle:handle.write(output)
            originals[member.name]=hashlib.sha256(raw).hexdigest();installed[member.name]=hashlib.sha256(output).hexdigest()
    if not required<=set(installed):raise ValueError('patch files missing from archive')
    changed=sorted(name for name in installed if installed[name]!=originals[name])
    if set(changed)!=required:raise ValueError('unexpected source edits')
    for name in required:compile((tree/name).read_bytes(),str(tree/name),'exec')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LOGGING_DIR=str(root))
    sys.path.insert(0,str(tree/'src'))
    names=['dojo.solvers.fore_ts.fore_ts','dojo.solvers.fore_ts.batch_runtime','dojo.solvers.fore_ts.candidate_ledger','dojo.solvers.fore_ts.wallclock','dojo.solvers.mcts.mcts','dojo.config_dataclasses.solver.fore_ts']
    imports={}
    for name in names:
        module=importlib.import_module(name);path=Path(module.__file__).resolve()
        if tree not in path.parents:raise ValueError('wrong imported source tree')
        imports[name]=rt.sha(path)
    from dojo.config_dataclasses.solver.fore_ts import ForeTSSolverConfig
    if ForeTSSolverConfig.__dataclass_fields__['chosen_batch_order'].default!='native':raise ValueError('not default off')
    result=dict(status='PREPARED_SOURCE_AND_NATIVE_IMPORTS_ONLY',utc=rt.utc(),root=str(root),source_archive_sha256=rt.SOURCE_SHA,
        builder_commit=commit,changed_files=changed,source_file_count=len(installed),installed_sha256=installed,native_imports=imports,
        default_order='native',selection_and_model_unchanged=True,per_action_escrow_common_to_both_arms=True,
        gpu_jobs=0,model_calls=0,paid_api_calls=0,launchable_full_e2e=False,
        remaining='Need a paired full-search worker with explicit model endpoints, clocks, task execution and CPU dispatch preflight; do not launch this source builder as an experiment.')
    rt.write(root/'prepared.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='installed_sha256'}|dict(prepared_sha256=rt.sha(root/'prepared.json')),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--commit',required=True);args=parser.parse_args();main(args.commit)
