"""Run the real cleanup method source with injected transport failures.

No heavyweight Dojo imports, kernels, data or fake performance measurements.
"""
import ast
import logging
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]


def method(relative, cls, name):
    tree = ast.parse((ROOT / relative).read_text(encoding='utf-8'))
    c = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in c.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {'log': logging.getLogger('cleanup-test')}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(relative), 'exec'), scope)
    return scope[name]


class CleanupTests(unittest.TestCase):
    def test_interpreter_stops_server_when_kernel_delete_raises(self):
        calls = []
        def fail():
            calls.append('kernel');raise RuntimeError('synthetic deletion failure')
        obj = types.SimpleNamespace(cleanup_session=fail,
                    jupyter_server=types.SimpleNamespace(stop=lambda: calls.append('server')))
        close = method('src/dojo/core/interpreters/jupyter/jupyter_interpreter.py', 'JupyterInterpreter', 'close')
        with self.assertRaisesRegex(RuntimeError, 'synthetic deletion failure'):
            close(obj)
        self.assertEqual(calls, ['kernel', 'server'])

    def test_interpreter_normal_cleanup_once(self):
        calls = []
        obj = types.SimpleNamespace(cleanup_session=lambda: calls.append('kernel'),
                    jupyter_server=types.SimpleNamespace(stop=lambda: calls.append('server')))
        method('src/dojo/core/interpreters/jupyter/jupyter_interpreter.py', 'JupyterInterpreter', 'close')(obj)
        self.assertEqual(calls, ['kernel', 'server'])

    def test_executor_attempts_delete_when_socket_close_raises(self):
        calls = []
        def fail():
            calls.append('socket');raise RuntimeError('synthetic socket failure')
        obj = types.SimpleNamespace(_kernel_id='synthetic-kernel',
             _jupyter_kernel_client=types.SimpleNamespace(stop=fail),
             _jupyter_client=types.SimpleNamespace(delete_kernel=lambda k: calls.append(('delete', k))))
        stop = method('src/dojo/core/interpreters/jupyter/jupyter_code_executor.py', 'JupyterCodeExecutor', 'stop')
        with self.assertRaisesRegex(RuntimeError, 'synthetic socket failure'):
            stop(obj)
        self.assertEqual(calls, ['socket', ('delete', 'synthetic-kernel')])


if __name__ == '__main__':
    unittest.main()
