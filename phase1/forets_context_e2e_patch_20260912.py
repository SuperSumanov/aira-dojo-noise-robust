"""Explicit new-release diff; old source, receipts and runs remain unchanged."""
from forets_paid_patch_20260911 import once


def budget_source(text):
    auth=dict(version=7,total=4942593566,incremental_cap=3500000000,run_limit=4000000000,route_limit=4000000000,
        predecessor_authorization='69e6d156ea7ec0f172edf3f46f432661c1da8ca0c1249301212ac59bac209fbe',
        predecessor_accounted=1442593566,predecessor_settled=742593566,predecessor_calls=185,predecessor_unresolved=1,
        experiment='contextual-judge-e2e-seed13',logical_request_cap=100,judge_model='qwen/qwen3-coder-plus',
        judge_reservation=2600000000,accounted_cny_ceiling='43.4948233808')
    text=once(text,'AUTH_RAW = json.dumps(AUTH,','AUTH.update('+repr(auth)+')\nAUTH_RAW = json.dumps(AUTH,')
    text=once(text,'def reserve(path, scope, attempt_id):',
        'def reserve(path, scope, attempt_id, amount=None):\n'
        '    amount = RESERVE if amount is None else amount\n'
        '    if type(amount) is not int or amount not in (700000000,2600000000):\n'
        '        raise BudgetStopped("unapproved request reservation")')
    text=once(text,"        if not cap or total + RESERVE > AUTH['total'] or used + RESERVE > cap[0]:",
        "        count = db.execute('SELECT COUNT(*) FROM calls WHERE scope=?',(scope,)).fetchone()[0]\n"
        "        if not cap or count >= 100 or total + amount > AUTH['total'] or used + amount > cap[0]:")
    text=once(text,"(attempt_id, scope, RESERVE, None, 'unresolved', time.time())",
        "(attempt_id, scope, amount, None, 'unresolved', time.time())")
    text=once(text,'if cost > RESERVE:','if cost > row[0]:')
    text=once(text,'if cost is None or cost > RESERVE:','if cost is None or cost > row[0]:')
    return text


def batch_source(text):
    text=once(text,'from pathlib import Path','from pathlib import Path\nfrom dojo.solvers.fore_ts.contextual_rank import rank_pool')
    old='''            async def score_all():
                for slot, node in enumerate(nodes):
                    if ledger.data['candidates'][slot]['state'] == 'generated':
                        assert_candidate_unchanged(ledger, slot, node)
                        ledger.begin_score(slot)
                        score = await solver._query_critic(node)
                        assert_candidate_unchanged(ledger, slot, node)
                        ledger.scored(slot, score)
            asyncio.run(score_all())'''
    new='''            async def score_all():
                if any(c['state'] != 'generated' for c in ledger.data['candidates']):
                    raise LedgerError('no partial contextual-rank replay')
                for slot, node in enumerate(nodes):
                    assert_candidate_unchanged(ledger, slot, node)
                    ledger.begin_score(slot)
                scores = await rank_pool(solver.task_name, [node.code for node in nodes],
                                         solver.state.current_step, root)
                if len(scores) != len(nodes):
                    raise LedgerError('incomplete contextual rank')
                for slot, node in enumerate(nodes):
                    assert_candidate_unchanged(ledger, slot, node)
                    ledger.scored(slot, scores[slot])
            asyncio.run(score_all())'''
    return once(text,old,new)


NO_SERVICE='''class InWorkerAPICritic:
    """No local reward model or extra GPU: API rankings happen in the worker."""
    def __init__(self,scheduler,directory):
        self.scheduler=scheduler;self.budget=scheduler.budget
        self.directory=directory;self.name='in-worker-api-no-service'
        self.process=None;self.startup_seconds=None;self.started=False
    def start(self):
        if self.started:raise RuntimeError('no repeated start')
        catalog=json.loads((ROOT_FOR_API_CATALOG/'block-1.plus-catalog.json').read_text())
        if catalog.get('model')!='qwen/qwen3-coder-plus' or catalog.get('provider')!='alibaba':
            raise ValueError('fixed API catalog missing')
        self.started=True;self.startup_seconds=0.0
        write_once(self.directory/'api-selector.json',dict(mode='in_worker_contextual_api',local_model_loads=0,
            local_service_gpus=0,model='qwen/qwen3-coder-plus',aggregation='two_order_borda_v1'))
    def alive(self):return self.started


'''


def derive(name,text,new_root):
    if name=='forets_block_controller_20260911.py':text=once(text,'enumerate((12,), 1)','enumerate((13,), 1)')
    if name=='forets_paid_route_20260911.py':text=once(text,"FORETS_PAID_SCOPE='route_s12'","FORETS_PAID_SCOPE='route_s13'")
    if name=='forets_native_run_20260911.py':
        old='''    for name, key in (('bradley_terry_server.py','server_sha256'),
                      ('bradley_terry_evaluation.py','loader_sha256')):
        if hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() != spec[key]:
            raise ValueError('deployed critic input code changed')'''
        text=once(text,old,"    if spec.get('critic_kind')!='in_worker_contextual_api':\n        raise ValueError('wrong selector release')")
        text=once(text,"historical_input_template='unknown_fixed_existing_service'","historical_input_template='not_applicable_contextual_api'")
    if name=='forets_block_runtime_20260911.py':
        for old,new in [("value.get('NumCPUs') != '12'","value.get('NumCPUs') != '6'"),
            ("tres.get('gres/gpu') != '2'","tres.get('gres/gpu') != '1'"),
            ('num_nodes=1,num_cpus=12,','num_nodes=1,num_cpus=6,'),('num_gpus=2,end_time=','num_gpus=1,end_time='),
            ("service=Service(scheduler,record_dir,block,Path(__file__).with_name('forets_e2e_critic_service.py'))",
             'service=InWorkerAPICritic(scheduler,record_dir)')]:text=once(text,old,new)
        text=once(text,'class RuntimePoolControl(BlockPoolControl):',
            'ROOT_FOR_API_CATALOG=Path('+repr(str(new_root))+')\n\n'+NO_SERVICE+'class RuntimePoolControl(BlockPoolControl):')
        text=text.replace('dual-3090 twelve-CPU allocation','single-3090 six-CPU allocation')
    if name=='forets_block_collect_20260911.py':
        text=once(text,"entries.get('gres/gpu')!='2'","entries.get('gres/gpu')!='1'")
        text=once(text,'allocated_gpus=2,service_startup_seconds=None','allocated_gpus=1,service_startup_seconds=None')
    if name=='forets_block_readout_20260911.py':
        text=once(text,'for seed in (12,):','for seed in (13,):')
        text=once(text,"b['allocated_gpus'] != 2","b['allocated_gpus'] != 1")
    return text
