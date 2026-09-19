"""CPU control-flow tests of actual source methods; not a live kernel test."""
import ast
import dataclasses
import logging
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

SRC = Path(__file__).resolve().parents[1] / 'src/dojo/core/interpreters'


def definition(path, name, namespace, method=None):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    if method:
        node = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == method)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)
    return namespace[method or name]


class TimeoutPhaseTests(unittest.TestCase):
    def setUp(self):
        namespace = dict(dataclass=dataclasses.dataclass, DataClassJsonMixin=object, Any=Any)
        self.Result = definition(SRC/'base.py', 'ExecutionResult', namespace)
        self.execute = definition(SRC/'jupyter/jupyter_code_executor.py', 'JupyterCodeExecutor',
                                  dict(ExecutionResult=self.Result, time=time, log=logging.getLogger('test')), 'execute_code')
        self.executor = SimpleNamespace(_wait_timeout=120, _timeout=7200,
                                        _jupyter_kernel_client=Mock(), _jupyter_client=Mock(), _kernel_id='unit-test')
        self.executor._jupyter_kernel_client.wait_for_ready.return_value = True
        self.run = definition(SRC/'jupyter/jupyter_interpreter.py', 'JupyterInterpreter',
                              dict(ExecutionResult=self.Result, JupyterCodeExecutor=Mock, log=logging.getLogger('test'),
                                   humanize=SimpleNamespace(naturaldelta=lambda seconds: f'{seconds} seconds')), 'run')

    def wrapped(self, result):
        executor = Mock()
        executor.execute_code.return_value = result
        interpreter = SimpleNamespace(code_executor=executor, timeout=7200, cleanup_line=lambda line: line)
        return self.run(interpreter, 'candidate()', reset_session=False)

    def test_readiness_does_not_execute_or_retry(self):
        self.executor._jupyter_kernel_client.wait_for_ready.return_value = False
        result = self.execute(self.executor, 'candidate()')
        self.assertTrue(result.timed_out)
        self.assertEqual(result.timeout_phase, 'kernel_readiness')
        self.executor._jupyter_kernel_client.execute.assert_not_called()
        self.executor._jupyter_kernel_client.wait_for_ready.assert_called_once_with(timeout_seconds=120)
        self.executor._jupyter_client.interrupt_kernel.assert_not_called()
        wrapped = self.wrapped(result)
        self.assertEqual(wrapped.timeout_phase, 'kernel_readiness')
        self.assertIn('before candidate execution began', '\n'.join(wrapped.term_out))
        self.assertNotIn('Execution exceeded', '\n'.join(wrapped.term_out))
        self.assertNotIn('7200', '\n'.join(wrapped.term_out))

    def test_execution_timeout_still_interrupts(self):
        self.executor._jupyter_kernel_client.execute.return_value = SimpleNamespace(timed_out=True, is_ok=False, output=['slow'])
        result = self.execute(self.executor, 'candidate()')
        self.assertEqual(result.timeout_phase, 'code_execution')
        self.executor._jupyter_kernel_client.execute.assert_called_once_with('candidate()', timeout_seconds=7200)
        self.executor._jupyter_client.interrupt_kernel.assert_called_once_with('unit-test')
        wrapped = self.wrapped(result)
        self.assertIn('Execution exceeded the time limit of 7200 seconds', '\n'.join(wrapped.term_out))
        self.assertEqual(wrapped.timeout_phase, 'code_execution')

    def test_success_unchanged(self):
        self.executor._jupyter_kernel_client.execute.return_value = SimpleNamespace(timed_out=False, is_ok=True, output=['ok'], data_items=[])
        result = self.execute(self.executor, 'candidate()')
        wrapped = self.wrapped(result)
        self.assertEqual(wrapped.exit_code, 0)
        self.assertFalse(wrapped.timed_out)
        self.assertIsNone(wrapped.timeout_phase)
        self.assertEqual(wrapped.term_out[0], 'ok')
        self.executor._jupyter_client.interrupt_kernel.assert_not_called()

    def test_ordinary_failure_is_not_timeout(self):
        self.executor._jupyter_kernel_client.execute.return_value = SimpleNamespace(timed_out=False, is_ok=False, output=['TypeError'])
        result = self.execute(self.executor, 'candidate()')
        self.assertEqual(result.exit_code, 1)
        self.assertFalse(result.timed_out)
        self.assertIsNone(result.timeout_phase)
        self.assertNotIn('TimeoutError', '\n'.join(self.wrapped(result).term_out))

    def test_legacy_default_keeps_previous_message(self):
        result = self.Result(term_out=[], exec_time=7200, exit_code=1, timed_out=True)
        self.assertIsNone(result.timeout_phase)
        self.assertIn('Execution exceeded', '\n'.join(self.wrapped(result).term_out))
        self.assertIsNone(self.Result.get_empty().timeout_phase)


if __name__ == '__main__':
    unittest.main()
