"""Real Linux isolation checks. Run as root on the training node."""
import asyncio
from pathlib import Path
import shlex
import tempfile

import pytest

from src.mle_critic.src.agentic.common import final_answer, public_path
from src.mle_critic.src.agentic.sandbox import ChrootBashSandbox, PROJECT_ROOT


def config(tmp_path, **extra):
    return {"runtime_base": str(tmp_path / "runtime"),
            "mlebench_data_root": str(PROJECT_ROOT / "data/mlebench"),
            "conda_roots": ["/public/hk-research/users/jiqian/miniconda3"], **extra}


def sandbox(cfg, sample="sample"):
    return ChrootBashSandbox(cfg, sample, "spooky-author-identification", "print('A')\n", "print('B')\n")


@pytest.mark.parametrize("text,expected", [
    (r"reason \boxed{A}", "A"), (r"\boxed{B}", "B"), ("A", None),
    (r"\boxed{A} or \boxed{B}", None), (r"\boxed{C}", None),
    (r"\boxed{A} \boxed{bad}", None), (r"<tool_call>echo '\boxed{A}'</tool_call>", None),
])
def test_answer(text, expected):
    assert final_answer(text) == expected


def test_paths(tmp_path):
    with pytest.raises(ValueError):
        sandbox(config(tmp_path), "../escape")
    with pytest.raises(ValueError):
        public_path(PROJECT_ROOT / "data/mlebench", "../private")


def test_isolation_and_editor(tmp_path):
    async def run():
        with tempfile.NamedTemporaryFile(prefix="mle-host-secret-") as secret:
            async with sandbox(config(tmp_path)) as s:
                probe = f'''
import os, pathlib, socket
p = pathlib.Path
assert p('candidate_A/solution.py').read_bytes() == b"print('A')\\n"
assert p('candidate_B/solution.py').read_bytes() == b"print('B')\\n"
assert p('/mnt/data/train.csv').is_file()
for path in [{str(PROJECT_ROOT)!r}, {secret.name!r}, '/mnt/data/../private', '/run/secrets', '/root', '/home']:
    assert not p(path).exists(), path
for path in ['/mnt/data/new-file', '/usr/mle-test-file']:
    try:
        p(path).write_text('x')
    except OSError:
        pass
    else:
        raise AssertionError(path)
assert not list(p('/dev').glob('nvidia*'))
assert len(os.sched_getaffinity(0)) == 2
assert os.getuid() >= 300000
s = socket.socket(); s.settimeout(.2)
assert s.connect_ex(('1.1.1.1', 80)) != 0
p('scratch/escape').symlink_to({secret.name!r})
assert not p('scratch/escape').exists()
try:
    os.link('/mnt/data/train.csv', 'scratch/hardlink')
except OSError:
    pass
else:
    raise AssertionError('hardlink escaped')
for fd in p('/proc/self/fd').iterdir():
    try:
        target = os.readlink(fd)
    except FileNotFoundError:
        continue
    assert 'mle-host-secret' not in target
print('isolation ok')
'''
                result = await s.call("bash", {"command": "/usr/bin/python3 -c " + shlex.quote(probe)})
                assert result["exit_code"] == 0, result
                for args in [
                    {"command": "create", "path": "scratch/test.py", "file_text": "first\nsecond\n"},
                    {"command": "str_replace", "path": "scratch/test.py", "old_str": "first", "new_str": "changed"},
                    {"command": "insert", "path": "scratch/test.py", "insert_line": 1, "new_str": "middle"},
                ]:
                    assert (await s.call("text_editor", args))["exit_code"] == 0
                assert "middle" in (await s.call("text_editor", {"command": "view", "path": "scratch/test.py"}))["stdout"]
                result = await s.call("text_editor", {"command": "str_replace", "path": "scratch/test.py", "old_str": "absent", "new_str": "x"})
                assert result["exit_code"] == 1
                result = await s.call("text_editor", {"command": "view", "path": "../mnt/data/train.csv"})
                assert result["exit_code"] == 1
                result = await s.call("bash", {"command": "source /public/hk-research/users/jiqian/miniconda3/etc/profile.d/conda.sh && conda activate aira-dojo && python -c 'import numpy,pandas; print(pandas.read_csv(\"/mnt/data/train.csv\",nrows=2).shape)'"})
                assert result["exit_code"] == 0, result
            assert not s.path.exists()
    asyncio.run(run())


def test_limits_cleanup_concurrency(tmp_path):
    async def run():
        cfg = config(tmp_path, max_concurrent_sandboxes=2, command_timeout_s=1, max_output_bytes=1024)
        async with sandbox(cfg) as a, sandbox(cfg) as b:
            assert a.path != b.path and a.lease.uid != b.lease.uid
            result = await a.call("bash", {"command": "python3 -c 'import os; os.write(1,b\"a\"*100000); os.write(2,b\"\\xff\"*100000)'"})
            assert len(result["stdout"]) == 1024 and result["truncated_bytes"] > 0
            assert result["exit_code"] == 0
            result = await a.call("bash", {"command": "sleep 30"})
            assert result["timed_out"]
            assert (await a.call("bash", {"command": "echo alive"}))["exit_code"] == 0
            await a.call("bash", {"command": "setsid bash -c 'sleep 100' >/dev/null 2>&1 &"})
            uid = a.lease.uid
            # An additional sandbox waits asynchronously; cancelling it must not leak a lease.
            c = sandbox(cfg)
            task = asyncio.create_task(c.__aenter__())
            await asyncio.sleep(.2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await asyncio.sleep(.1)
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    assert entry.stat().st_uid != uid
                except FileNotFoundError:
                    pass
        async with sandbox(cfg) as d:
            assert d.lease.uid == uid
    asyncio.run(run())


def test_cancel_and_start_failure(tmp_path):
    async def run():
        cfg = config(tmp_path)
        s = sandbox(cfg)
        async def work():
            async with s:
                await s.call("bash", {"command": "sleep 30"})
        task = asyncio.create_task(work())
        while s.deadline is None:
            await asyncio.sleep(.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert s.lease is None and not s.path.exists()
        bad = sandbox(config(tmp_path, conda_roots=["/nonexistent-conda-root"]))
        with pytest.raises(RuntimeError):
            async with bad:
                pass
        assert bad.lease is None and not bad.path.exists()
    asyncio.run(run())
