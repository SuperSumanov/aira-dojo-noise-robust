"""Two artificial analyzer fixtures after 13113 closes; no GPU or task scores.

Copy the closed ledger including every unknown liability, then seal old scopes.
At most two new wire attempts, no retries, incremental liability cap USD0.75.
Capture only JSON-schema error paths/types, never response text or credentials.
"""
import argparse
import asyncio
from contextlib import closing, redirect_stdout, redirect_stderr
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

PARENT = Path('/research/d7/spc/yzyang4/forets-env-20260912-edcpizid')
EXPECTED_AUTH = '942afbfc8864bb07dd6580c1d85a71743e35fea47bc1bdc71081666cab32ecb2'
SCOPES = ('fixture_success', 'fixture_failure')
INCREMENT = 750_000_000


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def fork_ledger(parent, output, budget, *, expected_auth, scopes=SCOPES):
    """Caller proves terminal state first; old calls/unknown holds stay identical."""
    if output.exists():
        raise FileExistsError('diagnostic ledger already exists')
    before = budget.snapshot(parent)
    if before['authorization_sha256'] != expected_auth:
        raise ValueError('parent authorization differs')
    with closing(sqlite3.connect(parent.as_uri()+'?mode=rw', uri=True)) as old:
        old.execute('BEGIN IMMEDIATE')
        calls = old.execute('SELECT * FROM calls ORDER BY id').fetchall()
        auth = old.execute('SELECT digest,body,stopped FROM auth').fetchall()
        if len(auth) != 1 or auth[0][0] != expected_auth:
            raise ValueError('parent authorization changed')
        if any(row[1] in scopes for row in calls):
            raise ValueError('diagnostic already represented')
        accounted = sum(row[2] for row in calls)
        settled = sum(row[3] or 0 for row in calls)
        if accounted + INCREMENT > 10_000_000_000:
            raise ValueError('original campaign authorization insufficient')
        old.execute('UPDATE auth SET stopped=1')
        old.commit()
        with closing(sqlite3.connect(output)) as child:
            old.backup(child)
    # These globals are process-local only; frozen deployed source is unchanged.
    budget.AUTH = dict(budget.AUTH, version=3, total=accounted+INCREMENT,
        incremental_cap=INCREMENT, predecessor_authorization=expected_auth,
        predecessor_accounted=accounted, predecessor_settled=settled,
        experiment='artificial-analyzer-diagnostic', logical_request_cap=2,
        accounted_cny_ceiling=str(Decimal(accounted+INCREMENT)/10**9*Decimal('8.8')))
    budget.AUTH_RAW = json.dumps(budget.AUTH, sort_keys=True, separators=(',', ':')).encode()
    budget.AUTH_SHA = hashlib.sha256(budget.AUTH_RAW).hexdigest()
    with closing(sqlite3.connect(output)) as child:
        child.execute('UPDATE auth SET digest=?,body=?,stopped=0',
                      (budget.AUTH_SHA,budget.AUTH_RAW.decode()))
        child.execute('UPDATE scopes SET cap=COALESCE((SELECT SUM(held) FROM calls '
                      'WHERE calls.scope=scopes.scope),0)')
        child.executemany('INSERT INTO scopes VALUES (?,?)', [(s,INCREMENT) for s in scopes])
        child.commit()
        if child.execute('SELECT * FROM calls ORDER BY id').fetchall() != calls:
            raise ValueError('carried calls differ')
    return dict(parent_authorization_sha256=expected_auth, parent_calls=len(calls),
        parent_accounted_nano=accounted, parent_settled_nano=settled,
        parent_unresolved=sum(row[4]=='unresolved' for row in calls),
        new_authorization=budget.AUTH, new_authorization_sha256=budget.AUTH_SHA)


def schema_failure(exc):
    """No values, arbitrary field names or exception strings escape this function."""
    allowed={'is_bug','summary','metric','code','plan','properties','required','type',
             'additionalProperties','items','anyOf','oneOf','allOf'}
    def path(values):
        return [x if type(x) is int or x in allowed else '<other-field>' for x in values]
    value = exc.instance
    required = exc.schema.get('required',[]) if isinstance(exc.schema,dict) else []
    return dict(validator=exc.validator if exc.validator in allowed else '<other-validator>',
        instance_type=type(value).__name__, path=path(exc.absolute_path),
        schema_path=path(exc.absolute_schema_path),
        missing_required=[x if x in allowed else '<other-field>' for x in required
                          if isinstance(value,dict) and x not in value],
        object_field_types={k:type(v).__name__ for k,v in value.items() if k in allowed}
                          if isinstance(value,dict) else None)


def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--mock',action='store_true');mode.add_argument('--resume-unsent',type=Path)
    mode.add_argument('--validate-fix',type=Path)
    parser.add_argument('--setup-repair',type=Path);parser.add_argument('--mock-fix',action='store_true')
    parser.add_argument('--revision',type=int,choices=(1,2),default=1);args=parser.parse_args()
    if args.mock_fix:
        if args.validate_fix or args.resume_unsent or args.setup_repair:raise ValueError('mock only')
        args.mock=True
    if args.setup_repair and not args.validate_fix:raise ValueError('setup repair requires fixed validation')
    os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHON_DOTENV_DISABLED='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        MLE_BENCH_DATA_DIR='/unread',SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    sys.path[:0]=[str(PARENT/'source/src'),str(PARENT/'code')]
    if not args.mock:
        if not (PARENT/'diagnostics.json').is_file():
            raise ValueError('whole development block closeout required')
        from forets_block_collect_20260911 import collect_metadata
        collect_metadata(PARENT,json.loads((PARENT/'prepared.json').read_text()))
        if not args.resume_unsent and not args.validate_fix:
            # A fixed marker also prevents creating a second window after interruption.
            save(PARENT/'analyzer-diagnostic-intent.json',dict(script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                requests=2,incremental_liability_cap_nano=INCREMENT,gpu_jobs=0,task_runs=0))
    root=args.setup_repair or args.resume_unsent or Path(tempfile.mkdtemp(prefix='forets-analyzer-'+('mock-' if args.mock else 'live-'),dir=PARENT.parent))
    scopes=tuple(('compat' if args.revision==1 else 'compat2')+'_'+s for s in ('success','failure')) if args.validate_fix else SCOPES
    if args.validate_fix:
        previous=args.validate_fix.resolve(strict=True)
        if previous.parent!=PARENT.parent or not previous.name.startswith('forets-analyzer-live-'):
            raise ValueError('explicit prior diagnostic root required')
        if args.setup_repair:
            if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-analyzer-live-') or (root/'paid.sqlite').exists():
                raise ValueError('not a pre-ledger setup failure')
            with closing(sqlite3.connect((root/'attempts.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
                if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]:raise ValueError('adapter was attempted')
            save(root/'setup-repair-intent.json',dict(prior_wire_calls=0,reason='class-local return annotation namespace'))
        else:
            save(previous/'compatibility-check-intent.json',dict(requests=2,gpu_jobs=0,output_root=str(root),
                incremental_liability_cap_nano=INCREMENT,old_results_unchanged=True))
    if args.resume_unsent:
        if root.resolve().parent!=PARENT.parent or not root.name.startswith('forets-analyzer-live-'):
            raise ValueError('explicit diagnostic root required')
        prior=json.loads((root/'report.json').read_text())
        if prior['mock'] or any(c.get('error_type')!='BudgetStopped' for c in prior['calls']):
            raise ValueError('not a wholly pre-wire failure')
        with closing(sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute('SELECT COUNT(*) FROM calls WHERE scope IN (?,?)',SCOPES).fetchone()[0]:
                raise ValueError('a request was already dispatched; no repair replay')
        save(root/'unsent-repair-intent.json',dict(reason='credential installed before client construction',
            new_wire_attempt_cap=2,prior_wire_calls=0,ledger_reset=False))
    os.chmod(root,0o700);os.environ['LOGGING_DIR']=str(root)
    captured=io.StringIO();report=dict(mock=args.mock,root=str(root),calls=[],schema_errors=[],
        source_tree='0a587f6b220b1aa0bd154f537f36594bc0690cb3',
        artificial_input_only=True,task_or_score_reads=False,gpu_jobs=0)
    with redirect_stdout(captured),redirect_stderr(captured):
        from dojo.config_dataclasses.run import RunConfig
        from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
        from dojo.core.solvers.operators.analyze import analyze_op
        from dojo.core.solvers.llm_helpers.backends import lite_llm, paid_transport, paid_budget, run_budget
        import jsonschema
        if not args.mock:
            from forets_e2e_campaign import install_process_credential
            install_process_credential()
            credential=os.environ.get('OPENROUTER_API_KEY')
            if not credential:raise RuntimeError('known remote provider credential unavailable')
            os.environ['PRIMARY_KEY']=credential
        cfg=RunConfig.load_from_json(PARENT/'configs/00-leaf-classification-s10-uniform_random.json')
        llm=GenericLLM(cfg.solver.operators['analyze'])
        llm.generation_kwargs['bounded_max_attempts']=1
        llm.generation_kwargs['bounded_request_timeout_seconds']=120
        attempt_path=root/('attempts-setup-repair.sqlite' if args.setup_repair else
                          'attempts-repaired.sqlite' if args.resume_unsent else 'attempts.sqlite')
        run_budget.initialize(attempt_path,2,8192)
        os.environ['FORETS_RUN_BUDGET_PATH']=str(attempt_path)
        original=lite_llm.LiteLLMClient._parse_structured_output
        if args.validate_fix or args.mock_fix:
            import ast
            import importlib.util
            from forets_review_metric_20260912 import patch_parser
            helper=Path(__file__).with_name('forets_review_metric_20260912.py')
            name='dojo.core.solvers.llm_helpers.backends.review_metric'
            spec=importlib.util.spec_from_file_location(name,helper)
            module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
            patched=patch_parser(Path(lite_llm.__file__).read_text())
            # Execute the exact patched method against the production module globals.
            cls=next(x for x in ast.parse(patched).body if isinstance(x,ast.ClassDef) and x.name=='LiteLLMClient')
            method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_parse_structured_output')
            namespace=dict(lite_llm.__dict__,FunctionCallType=lite_llm.LiteLLMClient.FunctionCallType)
            exec(compile(ast.Module(body=[method],type_ignores=[]),'<patched parser>','exec'),namespace)
            original=namespace['_parse_structured_output']
            report['compatibility_patch_sha256']=hashlib.sha256(patched.encode()).hexdigest()
            report['compatibility_helper_sha256']=hashlib.sha256(helper.read_bytes()).hexdigest()
        def inspect_parse(self,completion,spec,transport):
            try:return original(self,completion,spec,transport)
            except jsonschema.ValidationError as exc:
                report['schema_errors'].append(schema_failure(exc));raise
        lite_llm.LiteLLMClient._parse_structured_output=inspect_parse
        if args.mock:
            import litellm
            async def fake_complete(messages,kwargs,timeout,attempt_id):
                failed='deliberate failure' in messages[-1]['content']
                value=dict(is_bug=failed,summary='Artificial fixture.',metric=None if failed else .75)
                if args.mock_fix:value['metric']='not available' if failed else json.dumps(value['metric'])
                return litellm.ModelResponse(choices=[dict(index=0,message=dict(role='assistant',content=None,
                    tool_calls=[dict(id='artificial',type='function',function=dict(name='submit_review',arguments=json.dumps(value)))]),
                    finish_reason='tool_calls')],usage=dict(prompt_tokens=1,completion_tokens=1,total_tokens=2,cost=0))
            paid_transport.complete=fake_complete
        else:
            if args.resume_unsent or args.validate_fix:
                prior_root=args.validate_fix or root
                parent_handover=json.loads((prior_root/'handover.json').read_text())
                paid_budget.AUTH=parent_handover['new_authorization']
                paid_budget.AUTH_RAW=json.dumps(paid_budget.AUTH,sort_keys=True,separators=(',',':')).encode()
                paid_budget.AUTH_SHA=hashlib.sha256(paid_budget.AUTH_RAW).hexdigest()
            if args.resume_unsent:
                report['handover']=json.loads((root/'handover.json').read_text())
                paid_budget.snapshot(root/'paid.sqlite')
            elif args.validate_fix:
                report['handover']=fork_ledger(previous/'paid.sqlite',root/'paid.sqlite',paid_budget,
                    expected_auth=parent_handover['new_authorization_sha256'],scopes=scopes)
                save(root/'handover.json',report['handover'])
            else:
                report['handover']=fork_ledger(PARENT/'paid.sqlite',root/'paid.sqlite',paid_budget,expected_auth=EXPECTED_AUTH)
                save(root/'handover.json',report['handover'])
            os.environ['FORETS_PAID_LEDGER']=str(root/'paid.sqlite')
        async def exercise():
            for scope in scopes:
                os.environ['FORETS_PAID_SCOPE']=scope
                failed=scope.endswith('_failure');row=dict(fixture=scope,accepted=False)
                node=SimpleNamespace(code='raise ValueError("deliberate failure")' if failed else 'print("Validation accuracy: 0.75")',
                    term_out='ValueError: deliberate failure' if failed else 'Validation accuracy: 0.75\nProgram exited successfully.')
                try:
                    value,info=await analyze_op(llm,cfg.solver,'Artificial binary classification fixture; metric accuracy.',node)
                    row.update(accepted=True,is_bug_matches_fixture=value['is_bug'] is failed,
                        metric_matches_fixture=value['metric'] is None if failed else value['metric']==.75)
                except Exception as exc:
                    event=getattr(exc,'event',{})
                    row['error_type']=event.get('error_type',type(exc).__name__)
                report['calls'].append(row)
        asyncio.run(exercise())
        if not args.mock:report['billing']=paid_budget.snapshot(root/'paid.sqlite')
    captured.close()
    report['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save(root/('report-repaired.json' if args.resume_unsent else 'report.json'),report)
    print(json.dumps(report))


if __name__=='__main__':main()
