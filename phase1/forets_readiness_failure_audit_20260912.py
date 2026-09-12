"""Post-closeout execution-stage correction; no rescoring or retry of programs."""
import argparse
import ast
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import os
from types import SimpleNamespace as NS

BASE = Path('/research/d7/spc/yzyang4')
ROOTS = [('forets-repeat-20260912-x3pkniqp', '13124', 14),
         ('forets-repeat-20260912-3no2iopd', '13128', 15)]
SECRET = re.compile(r'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def classification(lines, exit_code):
    text = '\n'.join(lines)
    if exit_code == 0:
        if 'Kernel did not become ready in time.' in text:
            raise ValueError('contradictory successful readiness failure')
        return 'exit_zero'
    if 'Kernel did not become ready in time.' in text:
        return 'kernel_readiness_failure_before_candidate_dispatch'
    if 'TimeoutError: Execution exceeded' in text:
        return 'reported_execution_timeout_after_readiness'
    return 'candidate_code_error'


def bound_method(path, clsname, method, namespace):
    tree = ast.parse(path.read_text())
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == clsname]
    if len(classes) != 1: raise ValueError('source class mismatch')
    found = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == method]
    if len(found) != 1: raise ValueError('source method mismatch')
    module = ast.Module(body=found, type_ignores=[])
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace[method]


def prove_source(source):
    """Run only actual Python control-flow methods with a synthetic NOT-ready kernel."""
    class NotReady:
        execute_calls = 0
        def wait_for_ready(self, timeout_seconds):
            if timeout_seconds != 120: raise ValueError('wrong readiness cap')
            return False
        def execute(self, *args, **kwargs):
            self.execute_calls += 1
            raise AssertionError('candidate must not be dispatched')
    kernel = NotReady()
    times = iter([0., 120.])
    env = dict(ExecutionResult=NS, log=NS(warning=lambda *a: None),
               time=NS(monotonic=lambda: next(times)))
    executor_path = source/'jupyter_code_executor.py'
    execute = bound_method(executor_path, 'JupyterCodeExecutor', 'execute_code', env)
    result = execute(NS(_jupyter_kernel_client=kernel, _wait_timeout=120, _timeout=300), 'unused_candidate()')
    if kernel.execute_calls != 0 or result.exec_time != 120 or not result.timed_out:
        raise ValueError('readiness source reproduction differs')
    env2 = dict(ExecutionResult=NS, JupyterCodeExecutor=NS, log=NS(info=lambda *a: None),
                humanize=NS(naturaldelta=lambda s: '5 minutes' if s == 300 else str(s)))
    interpreter_path = source/'jupyter_interpreter.py'
    run = bound_method(interpreter_path, 'JupyterInterpreter', 'run', env2)
    result.eval_return = None
    runner = NS(code_executor=NS(execute_code=lambda code: result), timeout=300, cleanup_line=lambda s:s)
    wrapped = run(runner, 'unused_candidate()', reset_session=False)
    if classification(wrapped.term_out, wrapped.exit_code) != 'kernel_readiness_failure_before_candidate_dispatch':
        raise ValueError('source reproduction not recognized')
    if not any('Execution exceeded' in s for s in wrapped.term_out):
        raise ValueError('expected misleading outer timeout absent')
    return dict(actual_source_control_flow_reproduced=True, candidate_dispatch_calls=kernel.execute_calls,
                fake_readiness_seconds=120, configured_candidate_seconds=300,
                outer_code_timeout_message_is_misleading=True,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (executor_path,interpreter_path)})


def audit(output):
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    totals=Counter(); rows=[]; evidence={}; proofs=[]
    for name,job,seed in ROOTS:
        root=BASE/name
        state=subprocess.check_output(['sacct','-X','-j',job,'-nP','--format=JobIDRaw,State'],text=True,timeout=25).strip()
        if state != job+'|COMPLETED': raise ValueError('closed group required')
        proof=json.loads((root/'independent-context-verification.json').read_text())
        if proof['verification']!='passed' or proof['job']!=job: raise ValueError('numeric receipt missing')
        source=root/'source/src/dojo/core/interpreters/jupyter'
        proofs.append(dict(job=job,source_tree=proof['source_tree'],**prove_source(source)))
        manifest=json.loads((root/'runtime-manifest.json').read_text())
        if len(manifest['runs'])!=4: raise ValueError('incomplete group')
        for run in manifest['runs']:
            path=root/run['run_dir']/'checkpoint/journal.jsonl'
            raw=path.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
            nodes=[json.loads(s) for s in SECRET.sub('[REDACTED]',raw.decode()).splitlines() if s.strip()][1:]
            if len(nodes)!=5: raise ValueError('unexpected invocation count')
            kinds=Counter()
            for index,node in enumerate(nodes):
                kind=classification(node['_term_out'],node['exit_code']); kinds[kind]+=1
                rows.append(dict(job=job,seed=seed,task=run['task'],arm=run['arm'],
                                 invocation_index=index,stage=kind,reported_seconds=node['exec_time']))
            totals.update(kinds)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('journal changed')
            evidence[name+'/'+run['run_dir']+'/checkpoint/journal.jsonl']=digest
    result=dict(role='additive_failure_stage_correction_not_rescoring',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                invocations=len(rows),totals=dict(totals),rows=rows,source_proofs=proofs,evidence_sha256=evidence,
                candidate_reruns=0,new_api_calls=0,gpu_jobs=0,protected_cohort_read=False,
                limitations=['Readiness failure cause remains undiagnosed; source reproduction is not a live GPU fix.',
                    'Final submissions and numeric scores are unchanged; trajectories may be affected asymmetrically.',
                    'Prior execution_timeout totals included readiness failures and are not pure candidate-runtime failures.',
                    'Do not remove affected runs, impute scores or replay failed slots.'])
    with Path(output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','evidence_sha256')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();audit(a.output)
