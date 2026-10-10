"""Apply only the tested readiness changes to a pinned upstream source.

Retains newer upstream identity publishing and other unrelated code. This does
not edit the collaborator checkout; callers use a fresh experimental copy.
"""
import ast
from pathlib import Path


def method_source(text, name):
    tree = ast.parse(text)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SingularityJupyterServer')
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ''.join(text.splitlines(keepends=True)[fn.lineno-1:fn.end_lineno])


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('upstream readiness interface changed')
    return text.replace(before, after, 1)


def overlay(original, tested):
    identity_calls = original.count('_publish_container_identity(')
    result = once(original, 'import os\n', 'import os\nimport queue\n')
    result = once(result, 'import select\n', '')
    anchor = '        self._output_thread: threading.Thread | None = None\n'
    result = once(result, anchor, anchor + '        self._startup_lines: queue.Queue[str | None] = queue.Queue()\n        self._startup_done = threading.Event()\n')
    thread_block = '''        self._output_thread = threading.Thread(
            target=self._drain_output,
            name=f"singularity-jupyter-{self._subprocess.pid}",
            daemon=True,
        )
        self._output_thread.start()
'''
    result = once(result, thread_block, '')
    result = once(result, '            self._wait_until_ready(startup_timeout)\n',
                  ''.join('    '+line for line in thread_block.splitlines(keepends=True)) + '            self._wait_until_ready(startup_timeout)\n')
    for name in ('_wait_until_ready', '_drain_output'):
        result = once(result, method_source(result, name), method_source(tested, name))
    result = once(result, '        log.warning("Stopping Singularity Jupyter server...")',
                  '        self._startup_done.set()\n        log.warning("Stopping Singularity Jupyter server...")')
    result = once(result, '            and output_thread is not threading.current_thread()\n',
                  '            and output_thread is not threading.current_thread()\n            and output_thread.is_alive()\n')
    result = once(result, '            output_thread.join(timeout=5)\n',
                  '            output_thread.join(timeout=5)\n        if process.stdout is not None and (output_thread is None or not output_thread.is_alive()):\n            process.stdout.close()\n')
    if result.count('_publish_container_identity(') != identity_calls:
        raise ValueError('identity publication altered')
    compile(result, 'readiness-overlay', 'exec')
    return result


if __name__ == '__main__':
    import sys
    old, tested, out = map(Path, sys.argv[1:])
    value = overlay(old.read_text(), tested.read_text())
    with out.open('x') as f:
        f.write(value)
