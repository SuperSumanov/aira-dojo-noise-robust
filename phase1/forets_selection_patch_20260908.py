"""0007 after 0005+0006: true no-critic baseline and pre-score pool freeze."""
import difflib
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = '54929de4ac92cb1a1a2fd75e31843a223c10c859'
BASE_TREE = 'a999d8aaf8e9278e4e1eab57e5e45d2b0f87aa48'
LEDGER = 'src/dojo/solvers/fore_ts/candidate_ledger.py'
BATCH = 'src/dojo/solvers/fore_ts/batch_runtime.py'
SELECTOR = 'src/dojo/solvers/fore_ts/selection.py'
CONFIG = 'src/dojo/config_dataclasses/solver/fore_ts.py'
YAML = 'src/dojo/configs/solver/mlebench/fore_ts.yaml'
PATHS = (LEDGER, BATCH, SELECTOR, CONFIG, YAML)
SECRET = re.compile(rb'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|'
                    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def source(path):
    if path not in (LEDGER, BATCH, CONFIG, YAML):
        raise ValueError('source outside fixed whitelist')
    cache_path = os.environ.get('FORETS_SELECTION_CACHE')
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
        raise ValueError('source anchor mismatch: ' + before[:70])
    return text.replace(before, after, 1)


def revised(path):
    if path == SELECTOR:
        return (ROOT / 'phase1/forets_selection_20260908.py').read_text(encoding='utf-8')
    text = source(path)
    if path == CONFIG:
        text = replace_once(text, '    selector_seed: int = field(default=MISSING)\n',
                            '    selector_seed: int = field(default=MISSING)\n'
                            '    selection_policy: str = field(default=MISSING)\n')
        text = replace_once(text, '        super().validate()\n',
            '        super().validate()\n'
            '        if self.selection_policy not in ("uniform_random", "critic_topk_random"):\n'
            '            raise ValueError("explicit supported selection_policy required")\n')
    elif path == YAML:
        text = replace_once(text, 'selector_seed: ???  # Must be frozen explicitly in all comparison arms.\n',
            'selector_seed: ???  # Must be frozen explicitly in all comparison arms.\n'
            'selection_policy: ???  # uniform_random or critic_topk_random; freeze before running.\n')
    elif path == BATCH:
        text = replace_once(text, 'import random\n',
            'from dojo.solvers.fore_ts.selection import POLICIES, choose_slots\n')
        text = replace_once(text, '    parent = path[-1]\n',
            '    policy = solver.cfg.selection_policy\n'
            '    if policy not in POLICIES:\n'
            '        raise LedgerError("explicit selection policy required before generation")\n'
            '    parent = path[-1]\n')
        text = replace_once(text, 'binding = dict(schema=3,',
                            'binding = dict(schema=4, selection_policy=policy,')
        text = replace_once(text, 'def expand_batch(solver, path, state, task, node_type, extract_code, config_snapshot):\n',
            'def assert_candidate_unchanged(ledger, slot, node):\n'
            '    record = {k: getattr(node, k) for k in\n'
            '              ("id", "ctime", "code", "plan", "operators_used", "operators_metrics")}\n'
            '    if (digest(record) != digest(ledger.data["candidates"][slot]["node"]) or\n'
            '            node.parents or node.children or node.metric is not None or node.is_buggy is not None):\n'
            '        raise LedgerError("candidate changed after generation freeze")\n\n\n'
            'def expand_batch(solver, path, state, task, node_type, extract_code, config_snapshot):\n')
        text = replace_once(text,
            "            if c['state'] == 'generated':\n"
            '                ledger.begin_score(slot)\n'
            '                ledger.scored(slot, await solver._query_critic(node))\n', '')
        start = text.index('        nodes = asyncio.run(gather())\n')
        end = text.index("        for slot in ledger.data['selected']:\n", start)
        text = text[:start] + '''        nodes = asyncio.run(gather())
        for slot, node in enumerate(nodes):
            assert_candidate_unchanged(ledger, slot, node)
        ledger.freeze_pool()  # All generation finishes before ANY critic request.
        if policy == 'critic_topk_random':
            async def score_all():
                for slot, node in enumerate(nodes):
                    if ledger.data['candidates'][slot]['state'] == 'generated':
                        assert_candidate_unchanged(ledger, slot, node)
                        ledger.begin_score(slot)
                        score = await solver._query_critic(node)
                        assert_candidate_unchanged(ledger, slot, node)
                        ledger.scored(slot, score)
            asyncio.run(score_all())
        if ledger.data['selected'] is None:
            scores = ([c['score'] for c in ledger.data['candidates']]
                      if policy == 'critic_topk_random' else None)
            ledger.select(choose_slots(count, solver.critic_top_k, solver.num_children_to_choose,
                          policy, solver.cfg.selector_seed, solver.task_name,
                          solver.state.current_step, scores))

''' + text[end:]
        text = replace_once(text, '            child = nodes[slot]\n',
            '            child = nodes[slot]\n            assert_candidate_unchanged(ledger, slot, child)\n')
    elif path == LEDGER:
        text = replace_once(text, "        self.path = Path(path)\n",
            "        if binding.get('selection_policy') not in ('uniform_random', 'critic_topk_random'):\n"
            "            raise LedgerError('selection policy missing from ledger binding')\n"
            "        self.path = Path(path)\n")
        text = replace_once(text, 'dict(schema=3, task_calls=',
                            'dict(schema=4, pool_sha256=None, task_calls=')
        text = replace_once(text, "self.data['schema'] != 3", "self.data['schema'] != 4")
        text = replace_once(text, "    def begin_score(self, slot):\n",
            "    def begin_score(self, slot):\n"
            "        if self.data['binding']['selection_policy'] != 'critic_topk_random' or self.data['pool_sha256'] is None:\n"
            "            raise LedgerError('critic request outside frozen ranked pool')\n")
        text = replace_once(text, "or any(c['state'] != 'scored' for c in self.data['candidates'])",
                            "or self.data['pool_sha256'] is None\n"
                            "                or any(c['state'] != self.ready_state() for c in self.data['candidates'])")
        text = replace_once(text, "if self.data['candidates'][i]['state'] == 'scored']",
                            "if self.data['candidates'][i]['state'] == self.ready_state()]")
        text = replace_once(text, "self._transition(slot, 'scored', 'executing')",
                            "self._transition(slot, self.ready_state(), 'executing')")
        text = replace_once(text, "if c['state'] not in {'scored', 'completed'}:",
                            "if c['state'] not in {self.ready_state(), 'completed'}:")
        text = replace_once(text, "if self.data['candidates'][i]['state'] == 'scored':",
                            "if self.data['candidates'][i]['state'] == self.ready_state():")
        text += '''
    def ready_state(self):
        return 'generated' if self.data['binding']['selection_policy'] == 'uniform_random' else 'scored'

    def freeze_pool(self):
        if any(c['state'] not in {'generated', 'scored'} for c in self.data['candidates']):
            raise LedgerError('complete known candidate pool required')
        current = digest([c['node'] for c in self.data['candidates']])
        saved = self.data['pool_sha256']
        if saved is None:
            if any(c['state'] != 'generated' for c in self.data['candidates']):
                raise LedgerError('pool must be frozen before scoring')
            self.data['pool_sha256'] = current
            self._write()
        elif saved != current:
            raise LedgerError('frozen candidate pool drift')
'''
    else:
        raise ValueError('unexpected patch path')
    return text


def patch_text():
    parts = []
    for path in PATHS:
        old = '' if path == SELECTOR else source(path)
        parts.extend(difflib.unified_diff(old.splitlines(True), revised(path).splitlines(True),
            fromfile='a/' + path if old else '/dev/null', tofile='b/' + path))
    return ''.join(parts)


if __name__ == '__main__':
    print(patch_text(), end='')
