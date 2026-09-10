"""Print a deterministic additive patch for the exact failed source-v5 tree."""
import difflib
from pathlib import Path
import subprocess
import sys

TREE = '2ff5277ba17327c6c03326a018b59f704402af6b'
BACKEND = 'src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'
HELPER = 'src/dojo/core/solvers/llm_helpers/backends/bounded_retry.py'
BATCH = 'src/dojo/solvers/fore_ts/batch_runtime.py'


def source(path):
    return subprocess.check_output(['git', 'show', TREE + ':' + path],
                                   cwd=Path(__file__).resolve().parents[1]).decode()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('expected exactly one source anchor')
    return text.replace(old, new)


def revised():
    text = source(BACKEND)
    text = once(text, "            # Never expose provider response/body/credentials in a retry error.\n            raise RuntimeError('bounded API attempt failed: ' + type(exc).__name__) from None\n",
        "            from dojo.core.solvers.llm_helpers.backends.bounded_retry import BoundedAttemptError, safe_failure\n"
        "            event.update(safe_failure(exc, response_received=completion is not None))\n"
        "            event['latency'] = time.monotonic() - start\n"
        "            raise BoundedAttemptError(event) from None\n")
    text = once(text, "        bounded_timeout = model_kwargs.pop('bounded_request_timeout_seconds', 60.)\n",
        "        bounded_timeout = model_kwargs.pop('bounded_request_timeout_seconds', 60.)\n"
        "        bounded_attempts = model_kwargs.pop('bounded_max_attempts', 1)\n"
        "        if type(bounded_attempts) is not int or not 1 <= bounded_attempts <= 3:\n"
        "            raise ValueError('bounded_max_attempts must be an integer in [1, 3]')\n"
        "        if bounded_attempts > 1 and (not bounded or not os.environ.get('FORETS_RUN_BUDGET_PATH')):\n"
        "            raise ValueError('transport retries require bounded transport and the shared run budget')\n")
    text = once(text, "            return await self._query_once_bounded(messages, filtered_kwargs, func_spec,\n                                                   structured_output_mode, bounded_timeout)\n",
        "            from dojo.core.solvers.llm_helpers.backends.bounded_retry import query_with_retries\n"
        "            return await query_with_retries(\n"
        "                lambda: self._query_once_bounded(messages, filtered_kwargs, func_spec,\n"
        "                                                 structured_output_mode, bounded_timeout), bounded_attempts)\n")
    batch = once(source(BATCH), '            return await asyncio.gather(*(obtain(i) for i in range(count)))\n',
        '            results = await asyncio.gather(*(obtain(i) for i in range(count)), return_exceptions=True)\n'
        '            # Preserve completed siblings; never select from a partial pool.\n'
        '            for result in results:\n'
        '                if isinstance(result, BaseException):\n'
        '                    raise result\n'
        '            return results\n')
    helper = Path(__file__).with_name('forets_transport_resilience.py').read_text(encoding='utf-8')
    return {BACKEND: text, BATCH: batch, HELPER: helper}


def patch_text():
    chunks = []
    for path, new in revised().items():
        old = '' if path == HELPER else source(path)
        chunks.append('diff --git a/' + path + ' b/' + path + '\n')
        if path == HELPER:
            chunks.append('new file mode 100644\n')
        chunks.extend(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
            fromfile='/dev/null' if path == HELPER else 'a/' + path, tofile='b/' + path))
    return ''.join(chunks)


if __name__ == '__main__':
    sys.stdout.buffer.write(patch_text().encode())
