"""Actual OS-pipe tests for the real gateway startup methods; no containers/GPU.

GATEWAY_SOURCE can point at a frozen upstream source for the before-patch run.
"""
import ast
import logging
import os
from pathlib import Path
import queue
import re
import select
import subprocess
import sys
import threading
import time
import types
import unittest


def load_methods():
    path = Path(os.environ.get('GATEWAY_SOURCE',
                str(Path(__file__).resolve().parents[2] / 'src/dojo/core/interpreters/jupyter/singularity_jupyter_server.py')))
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SingularityJupyterServer')
    wanted = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('_wait_until_ready', '_drain_output')]
    constants = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_READY_PATTERN' for t in n.targets)]
    scope = dict(re=re, queue=queue, time=time, select=select, log=logging.getLogger('pipe-test'))
    exec(compile(ast.Module(body=constants + wanted, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class PipeReadiness(unittest.TestCase):
    def run_pipe(self, child, timeout, expected):
        methods = load_methods()
        proc = subprocess.Popen([sys.executable, '-u', '-c', child], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        obj = types.SimpleNamespace(_subprocess=proc, _startup_lines=queue.Queue(), _startup_done=threading.Event())
        reader = None
        # Queue-based implementation must start draining before waiting. Old
        # implementation is tested exactly as it was (reader only after ready).
        if '_startup_lines' in methods['_wait_until_ready'].__code__.co_names:
            reader = threading.Thread(target=methods['_drain_output'], args=(obj,), daemon=True)
            reader.start()
        start = time.monotonic()
        try:
            if expected is None:
                methods['_wait_until_ready'](obj, timeout)
                self.assertEqual((obj.ip, obj.port), ('127.0.0.1', 19999))
            else:
                with self.assertRaises(expected):
                    methods['_wait_until_ready'](obj, timeout)
            self.assertLess(time.monotonic()-start, timeout+1.0)
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=5)
            if reader:
                reader.join(timeout=5)
                self.assertFalse(reader.is_alive())
            proc.stdout.close()

    def test_burst_contains_noise_and_ready_before_next_write(self):
        self.run_pipe("import os,time;os.write(1,b'noise\\nis available at http://127.0.0.1:19999\\n');time.sleep(2)", .5, None)

    def test_ready_split_across_writes(self):
        self.run_pipe("import os,time;os.write(1,b'is available at http://127.');time.sleep(.03);os.write(1,b'0.0.1:19999\\n');time.sleep(2)", .5, None)

    def test_no_ready_has_bounded_timeout(self):
        self.run_pipe("import os,time;os.write(1,b'noise\\n');time.sleep(2)", .2, TimeoutError)

    def test_early_exit_is_not_readiness(self):
        self.run_pipe("print('failure',flush=True)", .5, RuntimeError)

    def test_partial_line_does_not_escape_timeout(self):
        self.run_pipe("import os,time;os.write(1,b'partial');time.sleep(2)", .2, TimeoutError)


if __name__ == '__main__':
    unittest.main()
