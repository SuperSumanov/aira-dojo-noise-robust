"""Export minimal patches against exact f7; never edit either branch/worktree.

A: buffered readiness + guaranteed cleanup attempts. B: lost-kernel reporting;
B requires the separately validated, version-pinned gateway shutdown guard.
These are reliability fixes, not an asserted fix for historical OpenBLAS EAGAIN.
"""
import ast,difflib,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from gateway_readiness_overlay import overlay as readiness
from kernel_restart_guard import overlay as restart

BASE='f7ccd79323112b10ccc82d8e9ec9d6cf089df607'
TESTED='600a994dfb420b362f048daf0e0e002a6130110a'
PREFIX='src/dojo/core/interpreters/jupyter/'
FILES=('singularity_jupyter_server.py','jupyter_code_executor.py','jupyter_interpreter.py','jupyter_client.py')

def git(repo,*args,env=None):
    return subprocess.check_output(['git','-C',str(repo),*args],env=env)

def once(text,old,new):
    assert text.count(old)==1,'upstream interface drift'
    return text.replace(old,new,1)

def definitions(text):
    tree=ast.parse(text);items={}
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):items[node.name]=ast.dump(node,include_attributes=False)
        if isinstance(node,ast.ClassDef):
            for method in node.body:
                if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    items[node.name+'.'+method.name]=ast.dump(method,include_attributes=False)
    return items

def sources(repo):
    old={n:git(repo,'show',BASE+':'+PREFIX+n).decode() for n in FILES}
    fixed=dict(old)
    tested=git(repo,'show',TESTED+':'+PREFIX+FILES[0]).decode()
    fixed[FILES[0]]=readiness(old[FILES[0]],tested)
    fixed[FILES[1]]=once(old[FILES[1]],'''        self._jupyter_kernel_client.stop()
        log.warning(f"Deleting kernel {self._kernel_id}")
        self._jupyter_client.delete_kernel(self._kernel_id)
''','''        try:
            self._jupyter_kernel_client.stop()
        finally:
            # A WebSocket error does not prove that the kernel has exited.
            log.warning(f"Deleting kernel {self._kernel_id}")
            self._jupyter_client.delete_kernel(self._kernel_id)
''')
    fixed[FILES[2]]=once(old[FILES[2]],'''        self.cleanup_session()
        self.jupyter_server.stop()
''','''        try:
            self.cleanup_session()
        finally:
            # Failed kernel deletion must not skip enclosing server cleanup.
            self.jupyter_server.stop()
''')
    fixed[FILES[3]]=restart(old[FILES[3]])
    allowed={FILES[0]:{'SingularityJupyterServer.'+m for m in ('__init__','_wait_until_ready','_drain_output','stop')},
        FILES[1]:{'JupyterCodeExecutor.stop'},FILES[2]:{'JupyterInterpreter.close'},FILES[3]:{'JupyterKernelClient.execute'}}
    for name in FILES:
        compile(fixed[name],name,'exec')
        before=definitions(old[name]);after=definitions(fixed[name]);assert before.keys()==after.keys()
        assert {n for n in before if before[n]!=after[n]}==allowed[name]
    # In particular no reversal of senior GPU environment, identity or port logic.
    for name,symbols in ((FILES[0],('_build_container_environment','_publish_container_identity','_build_singularity_command')),
                         (FILES[2],('_gateway_port',))):
        for symbol in symbols:assert definitions(old[name])[symbol]==definitions(fixed[name])[symbol]
    return old,fixed

def patch(old,fixed,names):
    return ''.join(''.join(difflib.unified_diff(old[n].splitlines(True),fixed[n].splitlines(True),
        fromfile='a/'+PREFIX+n,tofile='b/'+PREFIX+n)) for n in names)

def export(repo,out):
    out.mkdir();old,fixed=sources(repo)
    pa=patch(old,fixed,FILES[:3]);pb=patch(old,fixed,FILES[3:])
    secret=re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{20,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,})')
    assert not secret.search(pa+pb)
    for name,text in (('A-readiness-cleanup.patch',pa),('B-lost-kernel-reporting.patch',pb)):
        with (out/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    with tempfile.TemporaryDirectory(prefix='patch-check-',dir=out) as tmp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'))
        git(repo,'read-tree',BASE,env=env)
        for n in ('A-readiness-cleanup.patch','B-lost-kernel-reporting.patch'):
            git(repo,'apply','--cached','--check',str(out/n),env=env)
            git(repo,'apply','--cached',str(out/n),env=env)
        names=git(repo,'diff','--cached','--name-only',BASE,env=env).decode().splitlines()
        assert set(names)=={PREFIX+n for n in FILES}
        for n in FILES:assert git(repo,'show',':'+PREFIX+n,env=env)==fixed[n].encode()
    receipt=dict(base_commit=BASE,tested_reference=TESTED,isolated_index_apply_check=True,branches_changed=False,
        modified_methods={n:sorted(k for k in definitions(old[n]) if definitions(old[n])[k]!=definitions(fixed[n])[k]) for n in FILES},
        files={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ('A-readiness-cleanup.patch','B-lost-kernel-reporting.patch')},
        source_sha256={n:dict(before=hashlib.sha256(old[n].encode()).hexdigest(),after=hashlib.sha256(fixed[n].encode()).hexdigest()) for n in FILES},
        boundary='B is NOT standalone: requires pinned kernel_shutdown_guard inside the gateway. Neither patch proves historical EAGAIN prevention. No candidate retry,timeout,source,image,GPU mapping or global limit changes.')
    with (out/'patch-receipt.json').open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True)
    print(json.dumps(receipt))

if __name__=='__main__':
    import sys
    export(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve())
