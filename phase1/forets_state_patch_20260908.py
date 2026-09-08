"""Build additive 0003 against 0002, without changing either upstream checkout."""
import ast
import difflib

from phase1.forets_upstream_hotfix_20260908 import (
    ROOT, FORE, CONFIG, YAML, MCTS, SECRET, revised as hotfix, source, replace_once,
)

LEDGER = 'src/dojo/solvers/fore_ts/candidate_ledger.py'
BATCH = 'src/dojo/solvers/fore_ts/batch_runtime.py'
PATHS = (FORE, CONFIG, YAML, MCTS, LEDGER, BATCH)


def before(path):
    if path in (FORE, CONFIG, YAML):
        return hotfix(path)
    if path == MCTS:
        return source(path)
    return ''


def replace_method(text, name, replacement):
    tree = ast.parse(text)
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ForeTS')
    method = next(n for n in klass.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    lines = text.splitlines(True)
    return ''.join(lines[:method.lineno - 1]) + replacement + ''.join(lines[method.end_lineno:])


def revised(path):
    if path in (LEDGER, BATCH):
        filename = 'forets_candidate_ledger_20260908.py' if path == LEDGER else 'forets_batch_runtime_20260908.py'
        text = (ROOT / 'phase1' / filename).read_text(encoding='utf-8')
        if SECRET.search(text.encode()):
            raise ValueError('credential gate')
        if path == BATCH:
            text = replace_once(text, 'from phase1.forets_candidate_ledger_20260908 import',
                                'from dojo.solvers.fore_ts.candidate_ledger import')
        return text
    text = before(path)
    if path == FORE:
        text = replace_once(text, 'import math\n',
            'import math\nfrom pathlib import Path\nfrom omegaconf import OmegaConf\n'
            'from dojo.solvers.fore_ts.batch_runtime import expand_batch\n')
        text = replace_method(text, '_expand_leaf_and_backprop',
            '    def _expand_leaf_and_backprop(self, path, state, task):\n'
            '        return expand_batch(self, path, state, task, MCTSNode, extract_code,\n'
            '                            OmegaConf.to_container(OmegaConf.structured(self.cfg), resolve=True))\n')
        text = replace_once(text, 'parents=[parent], operators_used=["draft"]',
                            'parents=[], operators_used=["draft"]')
        text = replace_once(text, 'parents=[parent_node], operators_used=["improve"]',
                            'parents=[], operators_used=["improve"]')
        for method_name in ('_draft', '_improve'):
            tree = ast.parse(text)
            klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ForeTS')
            method = next(n for n in klass.body if isinstance(n, ast.AsyncFunctionDef) and n.name == method_name)
            lines = text.splitlines(True)
            body = ''.join(lines[method.lineno - 1:method.end_lineno])
            offset = body.index('        value_estimate = await self._query_critic(node)')
            text = replace_method(text, method_name, body[:offset] + '        return node\n')
        text += ('\n    def load_checkpoint(self):\n'
                 '        # Parent restore loses MCTS statistics and interpreter state; do not replay.\n'
                 '        root = Path(self.cfg.checkpoint_path)\n'
                 '        if any((root / name).exists() for name in\n'
                 '               ("state.json", "journal.jsonl", "forets-candidates-private")):\n'
                 '            raise RuntimeError("ForeTS full checkpoint reconciliation not implemented")\n'
                 '        return super().load_checkpoint()\n')
    elif path == CONFIG:
        text = replace_once(text, '    uct_c: float = field(default=MISSING)\n',
                            '    uct_c: float = field(default=MISSING)\n    selector_seed: int = field(default=MISSING)\n')
        text = replace_once(text, '        super().validate()\n',
                            '        super().validate()\n        if type(self.selector_seed) is not int:\n'
                            '            raise ValueError("explicit integer selector_seed required")\n')
    elif path == YAML:
        text = replace_once(text, 'uct_c: 0.25\n', 'uct_c: 0.25\nselector_seed: ???  # Must be frozen explicitly in all comparison arms.\n')
    elif path == MCTS:
        text = replace_once(text, 'while self.state.current_step <= self.cfg.step_limit:',
                            'while self.state.current_step < self.cfg.step_limit:')
    else:
        raise ValueError('unexpected patch path')
    return text


def patch_text():
    parts = []
    for path in PATHS:
        old, new = before(path), revised(path)
        for line in difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                fromfile='a/' + path if old else '/dev/null', tofile='b/' + path):
            parts.extend([line] if line.endswith('\n') else [line + '\n', '\\ No newline at end of file\n'])
    return ''.join(parts)


if __name__ == '__main__':
    print(patch_text(), end='')
