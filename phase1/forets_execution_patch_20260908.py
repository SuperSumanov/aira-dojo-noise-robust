"""0006 adds task-call receipts after standalone 0005 on exact upstream 54929.

No production checkout is changed. An explicit cache can replace Git blob reads
for a bounded isolated Linux test, but must carry the same tree and blob hashes.
"""
import difflib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = '54929de4ac92cb1a1a2fd75e31843a223c10c859'
BASE_TREE = '08d78ba2b0cf71c44cbd9eda34df15ae60049409'
LEDGER = 'src/dojo/solvers/fore_ts/candidate_ledger.py'
BATCH = 'src/dojo/solvers/fore_ts/batch_runtime.py'
WITNESS = 'src/dojo/solvers/fore_ts/execution_witness.py'
PATHS = (LEDGER, BATCH, WITNESS)
EXTRA = ('src/dojo/core/interpreters/python.py', 'src/dojo/core/interpreters/base.py',
         'src/dojo/solvers/mcts/mcts.py', 'src/dojo/core/tasks/constants.py')
SECRET = re.compile(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|'
                    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def source(path):
    if path not in (LEDGER, BATCH, *EXTRA):
        raise ValueError('source outside fixed whitelist')
    cache_path = os.environ.get('FORETS_EXECUTION_CACHE')
    if cache_path:
        cache = json.loads(Path(cache_path).read_bytes())
        if cache['tree'] != BASE_TREE or cache['upstream'] != UPSTREAM:
            raise ValueError('wrong source cache version')
        item = cache['sources'][path]
        raw = item['text'].encode()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('source cache hash drift')
    else:
        raw = subprocess.check_output(['git', 'show', BASE_TREE + ':' + path], cwd=ROOT)
    if len(raw) > 1024 * 1024 or SECRET.search(raw):
        raise ValueError('source security gate')
    return raw.decode()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('source anchor mismatch')
    return text.replace(before, after, 1)


def revised(path):
    if path == WITNESS:
        return (ROOT / 'phase1/forets_execution_witness_20260908.py').read_text(encoding='utf-8')
    text = source(path)
    if path == BATCH:
        text = replace_once(text, 'import copy\n',
            'import copy\nfrom dojo.solvers.fore_ts.execution_witness import ExecutionWitness\n'
            'from dojo.core.tasks.constants import EXECUTION_OUTPUT\n')
        text = replace_once(text, 'binding = dict(schema=2,',
                            'binding = dict(schema=3, execution_contract="task-return-receipt-v1",')
        text = replace_once(text, '        async def obtain(slot):\n',
            '        witness = ExecutionWitness(ledger, task, solver.remaining_steps,\n'
            '                                   solver.cfg.execution_timeout, EXECUTION_OUTPUT)\n\n'
            '        async def obtain(slot):\n')
        text = replace_once(text, 'state, eval_result = task.step_task(state, extract_code(child.code))',
                            'state, eval_result = witness.task_for(slot, "candidate").step_task(state, extract_code(child.code))')
        text = replace_once(text, 'solver.debug_cycle(state, task, child)',
                            'solver.debug_cycle(state, witness.task_for(slot, "debug"), child)')
    elif path == LEDGER:
        text = replace_once(text, 'dict(schema=2, llm_requests=', 'dict(schema=3, task_calls=[], llm_requests=')
        text = replace_once(text, "self.data['schema'] != 2", "self.data['schema'] != 3")
        text = replace_once(text, "        self._transition(slot, 'executing', 'completed')",
            "        calls = [c for c in self.data['task_calls'] if c['slot'] == slot]\n"
            "        if not calls or any(c['state'] != 'returned' for c in calls):\n"
            "            raise LedgerError('task return receipts incomplete')\n"
            "        self._transition(slot, 'executing', 'completed')")
        text += '''
    def begin_task_call(self, slot, intent, cap):
        if (type(slot) is not int or not 0 <= slot < len(self.data['candidates']) or
                self.data['phase'] != 'executing' or slot not in self.data['selected'] or
                self.data['candidates'][slot]['state'] != 'executing'):
            raise LedgerError('task call outside selected execution')
        calls = self.data['task_calls']
        if type(cap) is not int or cap <= 0 or len(calls) >= cap:
            raise LedgerError('execution-call cap exhausted before dispatch')
        if any(c['state'] != 'returned' for c in calls):
            raise LedgerError('unknown previous task call; no retry')
        same_slot = [c for c in calls if c['slot'] == slot]
        expected_role = 'debug' if same_slot else 'candidate'
        if intent['role'] != expected_role:
            raise LedgerError('candidate/debug task order mismatch')
        frozen = json.loads(canonical(intent))
        call_id = len(calls)
        calls.append(dict(call_id=call_id, slot=slot, intent=frozen, state='started',
                          task_wall_ns=None, execution_metadata=None, error_type=None))
        self._write()
        return call_id

    def finish_task_call(self, call_id, status, elapsed_ns, metadata, error_type):
        calls = self.data['task_calls']
        if type(call_id) is not int or not 0 <= call_id < len(calls):
            raise LedgerError('invalid task call id')
        call = calls[call_id]
        if (call['state'] != 'started' or status not in {'returned', 'raised', 'invalid_return'} or
                type(elapsed_ns) is not int or elapsed_ns < 0):
            raise LedgerError('invalid task completion')
        call.update(state=status, task_wall_ns=elapsed_ns,
                    execution_metadata=json.loads(canonical(metadata)), error_type=error_type)
        self._write()
'''
    else:
        raise ValueError('unexpected patch path')
    return text


def patch_text():
    parts = []
    for path in PATHS:
        old = '' if path == WITNESS else source(path)
        new = revised(path)
        parts.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
            fromfile='a/' + path if old else '/dev/null', tofile='b/' + path))
    return ''.join(parts)


if __name__ == '__main__':
    print(patch_text(), end='')
