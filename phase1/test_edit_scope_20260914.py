import ast
import sys
import types
import unittest
from unittest.mock import patch
from forets_edit_scope_20260914 import assemble, module_node, code_for, process


class EditTests(unittest.TestCase):
    TEMPLATE = 'import os\ndef build_model(X):\n return 1\nmodel = build_model(data)\nprint(model)\n'

    def test_only_function_changes(self):
        code, r = assemble(self.TEMPLATE, 'def build_model(X):\n import math\n return 2\n')
        self.assertTrue(r['interface_accepted'])
        a, b = ast.parse(self.TEMPLATE), ast.parse(code)
        self.assertEqual(ast.dump(a.body[0]), ast.dump(b.body[0]))
        self.assertEqual(ast.dump(a.body[2]), ast.dump(b.body[2]))

    def test_failures_not_baseline_fallback(self):
        for code in ('print(1)', 'def f(X):\n return 1', 'def build_model(X):\n return 1\nprint(2)',
                     'def build_model(X=side_effect()):\n return 1', '@other\ndef build_model(X):\n return 1', 'bad syntax!'):
            full, receipt = assemble(self.TEMPLATE, code)
            self.assertFalse(receipt['interface_accepted'])
            self.assertIn('raise RuntimeError', full)

    def test_nested_flexibility(self):
        module_node('def build_model(X):\n class Model:\n  pass\n def helper():\n  return Model()\n return helper()')

    def test_whole_program_unchanged(self):
        s = types.SimpleNamespace(cfg=types.SimpleNamespace(edit_scope='whole_program'))
        self.assertEqual(process(s, 'anything', {'x': 1}), ('anything', {'x': 1}))

    def test_original_start_preserved_except_builder(self):
        import forets_common_start_20260913 as old
        mock = types.ModuleType('dojo.solvers.fore_ts')
        mock.common_start = types.SimpleNamespace(original_code_for=old.code_for)
        with patch.dict(sys.modules, {'dojo.solvers.fore_ts': mock}):
            for task in ('leaf-classification', 'spaceship-titanic'):
                old_code, new_code = old.code_for(task), code_for(task)
                old_tree, new_tree = ast.parse(old_code), ast.parse(new_code)
                builder = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef))
                self.assertEqual(builder.name, 'build_model')
                # Explicit source-level assurance: I/O, split, fit, metric and
                # submit suffix are byte-identical prior to common formatting.
                suffix = 'X_train, X_valid, y_train, y_valid = '
                self.assertEqual(old_code[old_code.index(suffix):], new_code[new_code.index(suffix):])
                self.assertEqual([ast.dump(n) for n in old_tree.body[:10]], [ast.dump(n) for n in new_tree.body[:10]])


if __name__ == '__main__': unittest.main()
