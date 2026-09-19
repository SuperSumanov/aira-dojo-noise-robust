"""Default-off ordering adapter for the actual b7f8 deployed runtime.

Returns source bytes only. No remote mutation, training, ranking change, or
automatic post-execution recovery. The search cutoff/escrow still needs its
separate common integration before this is a launchable full-E2E experiment.
"""
import ast,hashlib,textwrap
from forets_ready_batch_patch_20260919 import once

CONFIG='src/dojo/config_dataclasses/solver/fore_ts.py'
RUNTIME='src/dojo/solvers/fore_ts/batch_runtime.py'
LEDGER='src/dojo/solvers/fore_ts/candidate_ledger.py'
EXPECTED={CONFIG:'f2831edf76d68f9c0ddd27707eaed5a40a2724e55c510c3217b914d7cc222d57',
          RUNTIME:'6de4b10fdbac7002acf1e7cb038753d824e8aa98acfb89f6401cdaa683812019',
          LEDGER:'f0bba9b9887f03197fd3def8e5c479d4c8b98f160398c46ae1d6ce7ba109e4eb'}

DEFER_METHODS='''
def defer_debug(self, slot):
    if self.data['binding'].get('chosen_batch_order') != 'ready_first':
        raise LedgerError('deferred debug requires the explicit ordering arm')
    calls = [c for c in self.data['task_calls'] if c['slot'] == slot]
    if len(calls) != 1 or calls[0]['intent']['role'] != 'candidate' or calls[0]['state'] != 'returned':
        raise LedgerError('only a known completed candidate can defer its repair')
    self._transition(slot, 'executing', 'debug_deferred')

def begin_deferred_debug(self, slot):
    if self.data['binding'].get('chosen_batch_order') != 'ready_first':
        raise LedgerError('deferred debug arm mismatch')
    pending = [i for i in self.data['selected'] if self.data['candidates'][i]['state'] == 'debug_deferred']
    if (self.data['phase'] != 'executing' or not pending or pending[0] != slot or
            any(self.data['candidates'][i]['state'] in {self.ready_state(), 'executing'} for i in self.data['selected']) or
            any(c['state'] != 'returned' for c in self.data['task_calls'])):
        raise LedgerError('ready candidates, ordered repairs, and known task completion required')
    self._transition(slot, 'debug_deferred', 'executing')

def skip_deferred_debug_budget(self, slot):
    if self.data['binding'].get('chosen_batch_order') != 'ready_first':
        raise LedgerError('deferred debug arm mismatch')
    self._transition(slot, 'debug_deferred', 'completed', debug_skipped_budget=True)
'''

def patched_sources(sources):
    if set(sources)!=set(EXPECTED):raise ValueError('exact source set required')
    text={k:v.replace('\r\n','\n') for k,v in sources.items()}
    for path,value in text.items():
        if hashlib.sha256(value.encode()).hexdigest()!=EXPECTED[path]:raise ValueError('unreviewed deployed source')
    text[CONFIG]=once(text[CONFIG],'    def validate(self) -> None:\n',
        '    chosen_batch_order: str = "native"\n\n    def validate(self) -> None:\n')
    text[CONFIG]=once(text[CONFIG],'        super().validate()\n',
        '        super().validate()\n        if self.chosen_batch_order not in ("native", "ready_first"):\n            raise ValueError("chosen batch order")\n')
    runtime=text[RUNTIME]
    runtime=once(runtime,'    parent = path[-1]\n',
        '    batch_order = getattr(solver.cfg, "chosen_batch_order", "native")\n'
        '    if batch_order not in ("native", "ready_first"):\n'
        '        raise LedgerError("chosen batch order before generation")\n'
        '    parent = path[-1]\n')
    runtime=once(runtime,"    if bootstrap:\n        binding['common_start']", 
        "    if batch_order != 'native':\n        binding['chosen_batch_order'] = batch_order\n"
        "    if bootstrap:\n        binding['common_start']")
    runtime=once(runtime,"        for slot in ledger.data['selected']:\n", 
        "        pending_debug = []\n        for slot in ledger.data['selected']:\n")
    runtime=once(runtime,'            else:\n                state, debug_path, fixed_metric = solver.debug_cycle',
        '            elif batch_order == "ready_first":\n'
        '                ledger.defer_debug(slot)\n'
        '                pending_debug.append((slot, child))\n'
        '                continue\n'
        '            else:\n                state, debug_path, fixed_metric = solver.debug_cycle')
    runtime=once(runtime,'        ledger.finish()\n',
        '        for slot, child in pending_debug:\n'
        '            if solver.remaining_steps <= 0:\n'
        '                ledger.skip_deferred_debug_budget(slot)\n'
        '                continue\n'
        '            ledger.begin_deferred_debug(slot)\n'
        '            state, debug_path, fixed_metric = solver.debug_cycle(state, witness.task_for(slot, "debug"), child)\n'
        '            if fixed_metric is not None:\n'
        '                solver._backprop_step(path=path + debug_path, value_estimate=fixed_metric)\n'
        '                solver.set_global_q_values(fixed_metric)\n'
        '            ledger.execution_completed(slot)\n'
        '        ledger.finish()\n')
    text[RUNTIME]=runtime
    text[LEDGER]=once(text[LEDGER],'    def finish(self):\n',textwrap.indent(DEFER_METHODS.strip()+'\n\n','    ')+'    def finish(self):\n')
    for value in text.values():ast.parse(value)
    return {path:value.encode() for path,value in text.items()}
