"""Additive 0004: audit actual LLM request boundaries in an isolated source patch.

This does not update either production branch or alter 0002/0003. The guarded
package-order contract must be shared by every future controlled comparison arm.
"""
import difflib
import subprocess

from phase1.forets_state_patch_20260908 import revised as prior, LEDGER, BATCH
from phase1.forets_upstream_hotfix_20260908 import ROOT, UPSTREAM, SECRET, replace_once

GENERIC = 'src/dojo/core/solvers/llm_helpers/generic_llm.py'
DRAFT = 'src/dojo/core/solvers/operators/draft.py'
IMPROVE = 'src/dojo/core/solvers/operators/improve.py'
GUARD = 'src/dojo/solvers/fore_ts/request_guard.py'
PATHS = (LEDGER, BATCH, GENERIC, DRAFT, IMPROVE, GUARD)


def upstream(path):
    if path not in {GENERIC, DRAFT, IMPROVE}:
        raise ValueError('unexpected source')
    raw = subprocess.check_output(['git', 'show', f'{UPSTREAM}:{path}'], cwd=ROOT)
    if len(raw) > 1024 * 1024 or SECRET.search(raw):
        raise ValueError('source security gate')
    return raw.decode()


def before(path):
    if path in (LEDGER, BATCH):
        return prior(path)
    if path == GUARD:
        return ''
    return upstream(path)


def revised(path):
    if path == GUARD:
        return (ROOT / 'phase1/forets_request_guard_20260908.py').read_text(encoding='utf-8')
    if path not in PATHS:
        return prior(path)
    text = before(path)
    if path == LEDGER:
        text = replace_once(text, 'dict(schema=1, binding=', 'dict(schema=2, llm_requests=[], prompt_sha256=None, prompt_snapshot=None, binding=')
        text = replace_once(text, "self.data['schema'] != 1", "self.data['schema'] != 2")
        text += '''
    def begin_llm_request(self, slot, request_hash, request, cap):
        if type(slot) is not int or not 0 <= slot < len(self.data['candidates']):
            raise LedgerError('invalid request slot')
        if digest(request) != request_hash:
            raise LedgerError('request payload hash mismatch')
        if self.data['phase'] != 'collecting' or self.data['candidates'][slot]['state'] != 'generating':
            raise LedgerError('LLM request outside candidate generation')
        calls = self.data['llm_requests']
        if len(calls) >= cap:
            raise LedgerError('logical-call cap exhausted before dispatch')
        if self.data['prompt_sha256'] not in (None, request_hash):
            raise LedgerError('rendered batch prompt or generation kwargs drift before dispatch')
        self.data['prompt_sha256'] = request_hash
        if self.data['prompt_snapshot'] is None:
            self.data['prompt_snapshot'] = json.loads(canonical(request))
        call_id = len(calls)
        calls.append(dict(call_id=call_id, slot=slot, request_sha256=request_hash,
                          state='started', usage=None, error_type=None))
        self._write()
        return call_id

    def finish_llm_request(self, call_id, status, usage, error_type):
        if status not in {'returned', 'ambiguous', 'invalid_usage'}:
            raise LedgerError('invalid LLM completion status')
        call = self.data['llm_requests'][call_id]
        if call['state'] != 'started':
            raise LedgerError('LLM request already finalized')
        frozen = json.loads(canonical(usage))
        call.update(state=status, usage=frozen, error_type=error_type)
        self._write()
'''
    elif path == BATCH:
        text = replace_once(text, 'import copy\n',
                            'import copy\nfrom dojo.solvers.fore_ts.request_guard import BatchRequestGuard\n')
        text = replace_once(text, 'binding = dict(schema=1,', 'binding = dict(schema=2, request_contract="same-rendered-request-v1",')
        text = replace_once(text, '        async def obtain(slot):\n',
                            '        guard = BatchRequestGuard(ledger, count * solver.cfg.max_llm_call_retries)\n\n'
                            '        async def obtain(slot):\n')
        text = replace_once(text,
            '                node = await (solver._draft(parent) if not parent.parents else solver._improve(parent))\n',
            '                with guard.slot(slot):\n'
            '                    node = await (solver._draft(parent) if not parent.parents else solver._improve(parent))\n')
    elif path in (DRAFT, IMPROVE):
        text = replace_once(text, 'import random\n',
            'import random\nfrom dojo.solvers.fore_ts.request_guard import package_order\n')
        text = replace_once(text, '    pkgs = cfg.available_packages\n    random.shuffle(pkgs)\n',
                            '    pkgs = package_order(cfg.available_packages)\n')
    elif path == GENERIC:
        text = replace_once(text, 'import logging\n',
            'import logging\nfrom dojo.solvers.fore_ts.request_guard import audited_query\n')
        if text.count('await self.client.query(\n') != 2:
            raise ValueError('unexpected GenericLLM query sites')
        text = text.replace('await self.client.query(\n', 'await audited_query(self.client,\n')
    return text


def patch_text():
    result = []
    for path in PATHS:
        old, new = before(path), revised(path)
        for line in difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                fromfile='a/' + path if old else '/dev/null', tofile='b/' + path):
            result.extend([line] if line.endswith('\n') else [line + '\n', '\\ No newline at end of file\n'])
    return ''.join(result)


if __name__ == '__main__':
    print(patch_text(), end='')
