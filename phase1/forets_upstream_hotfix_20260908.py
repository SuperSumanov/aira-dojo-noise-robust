"""Proposed hotfix against an exact upstream commit; never modifies its checkout.

The generated patch is an integration aid, not a deployment or effect protocol.
Only Git source blobs are read. No model, corpus, remote call or checkpoint is used.
"""
import difflib
import hashlib
import re
import subprocess
from pathlib import Path

UPSTREAM = '8b621851a87d20382feefe8c8458a7db2a1fabea'
ROOT = Path(__file__).resolve().parents[1]
FORE = 'src/dojo/solvers/fore_ts/fore_ts.py'
CONFIG = 'src/dojo/config_dataclasses/solver/fore_ts.py'
YAML = 'src/dojo/configs/solver/mlebench/fore_ts.yaml'
TASK = 'src/dojo/tasks/mlebench/task.py'
MEMORY = 'src/dojo/core/solvers/operators/memory.py'
MCTS = 'src/dojo/solvers/mcts/mcts.py'
ALLOWED = {FORE, CONFIG, YAML, TASK, MEMORY, MCTS}
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|[?&](?:token|key|api_key|access_token)=[^\s&]+)')


def source(path):
    if path not in ALLOWED:
        raise ValueError('source path not allowed')
    raw = subprocess.check_output(['git', 'show', f'{UPSTREAM}:{path}'], cwd=ROOT)
    if len(raw) > 1024 * 1024 or SECRET.search(raw):
        raise ValueError('source size or credential gate failed')
    return raw.decode('utf-8')


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('exact upstream replacement anchor mismatch')
    return text.replace(before, after, 1)


def revised(path):
    text = source(path)
    if path == FORE:
        text = replace_once(text, 'import random\n', 'import random\nimport math\n')
        text = replace_once(text,
            '        super().__init__(cfg, task_info)\n',
            '        cfg.validate()\n'
            '        task_name = task_info.get("name", task_info.get("competition_id"))\n'
            '        if not isinstance(task_name, str) or not task_name.strip():\n'
            '            raise ValueError("ForeTS requires the actual task name before generation")\n'
            '        super().__init__(cfg, task_info)\n')
        text = replace_once(text,
            '        self.task_name = str(task_info.get("name", task_info.get("competition_id", "")))\n',
            '        self.task_name = task_name\n')
        text = replace_once(text,
            '        num_children_to_create = min(self.cfg.num_children, self.remaining_steps)\n',
            '        num_children_to_create = min(self.cfg.num_children, self.remaining_steps)\n'
            '        if num_children_to_create <= 0:\n'
            '            return state\n')
        text = replace_once(text,
            '        chosen_child_nodes = random.sample(top_k_child_nodes, self.num_children_to_choose)\n',
            '        # Tail batches can contain fewer candidates than the configured count.\n'
            '        choose_count = min(self.num_children_to_choose, len(top_k_child_nodes))\n'
            '        chosen_child_nodes = random.sample(top_k_child_nodes, choose_count)\n')
        text = replace_once(text,
            '        for i in range(self.num_children_to_choose):\n'
            '            child_node = chosen_child_nodes[i]\n',
            '        for child_node in chosen_child_nodes:\n'
            '            # A previous selected child may have consumed steps in debug.\n'
            '            if self.remaining_steps <= 0:\n'
            '                break\n')
        text = replace_once(text, 'if self.state.current_step > self.cfg.step_limit:',
                            'if self.state.current_step >= self.cfg.step_limit:')
        text = replace_once(text, '"task": self._rm_task_name,', '"task": self.task_name,')
        text = replace_once(text,
            '                    value_estimate = float(response_data["score"])\n',
            '                    raw_score = response_data["score"]\n'
            '                    if isinstance(raw_score, bool):\n'
            '                        raise ValueError("critic score must be numeric, not boolean")\n'
            '                    value_estimate = float(raw_score)\n'
            '                    if not math.isfinite(value_estimate):\n'
            '                        raise ValueError("critic score must be finite")\n')
        text = replace_once(text,
            '        for _ in range(self.critic_max_attempts):\n',
            '        for attempt in range(self.critic_max_attempts):\n')
        text = replace_once(text,
            '                self.logger.warning(f"Critic query failed for node {key}: {e}. Retrying...")\n'
            '                await asyncio.sleep(1)  # Wait a bit before retrying\n'
            '                continue\n',
            '                self.logger.warning(\n'
            '                    f"Critic query failed for node {key}: {type(e).__name__}")\n'
            '                if attempt + 1 == self.critic_max_attempts:\n'
            '                    raise RuntimeError("critic attempts exhausted; no selection executed") from None\n'
            '                await asyncio.sleep(1)\n'
            '        raise RuntimeError("critic_max_attempts must be positive")\n')
    elif path == CONFIG:
        text = replace_once(text,
            'class ForeTSSolverConfig(SolverConfig):\n',
            'class ForeTSSolverConfig(SolverConfig):\n'
            '    uct_c: float = field(default=MISSING)\n')
        text = replace_once(text, '        super().validate()\n',
            '        super().validate()\n'
            '        for name in ("num_children", "critic_top_k", "num_children_to_choose", "critic_max_attempts"):\n'
            '            value = getattr(self, name)\n'
            '            if type(value) is not int or value <= 0:\n'
            '                raise ValueError(f"{name} must be a positive integer")\n'
            '        if not self.num_children_to_choose <= self.critic_top_k <= self.num_children:\n'
            '            raise ValueError("require choose <= top_k <= num_children")\n'
            '        import math\n'
            '        if isinstance(self.uct_c, bool) or not isinstance(self.uct_c, (int, float)) or not math.isfinite(self.uct_c) or self.uct_c < 0:\n'
            '            raise ValueError("uct_c must be finite and nonnegative")\n')
    elif path == YAML:
        text = replace_once(text, 'num_children: 5\n', 'num_children: 5\nuct_c: 0.25\n')
    elif path == TASK:
        text = replace_once(text, '        task_info = {\n',
                            '        task_info = {\n            "name": self.cfg.name,\n')
    else:
        raise ValueError('no proposed change to this source')
    return text


def patch_text():
    parts = []
    for path in (FORE, CONFIG, YAML, TASK):
        before, after = source(path), revised(path)
        # Several upstream blobs omit the final LF. Preserve valid Git patch syntax.
        lines = difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                     fromfile='a/' + path, tofile='b/' + path)
        for line in lines:
            if line.endswith('\n'):
                parts.append(line)
            else:
                parts.extend([line + '\n', '\\ No newline at end of file\n'])
    return ''.join(parts)


if __name__ == '__main__':
    print(patch_text(), end='')
