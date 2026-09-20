"""Async client with node-wide flock slots and deterministic namespace cleanup."""
import asyncio
import json
import os
import re
import shutil
import signal
import time
from pathlib import Path
from uuid import uuid4

from src.dojo.core.interpreters.linux_sandbox import UidLease, chown_tree_no_follow, ensure_runtime_base
from .common import public_path

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class ChrootBashSandbox:
    def __init__(self, config, sample_uuid, task, solution_a, solution_b):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sample_uuid):
            raise ValueError("Invalid sample UUID")
        self.config = dict(config)
        self.public = public_path(config["mlebench_data_root"], task)
        self.sample_uuid = sample_uuid
        self.trajectory_uuid = uuid4().hex
        self.codes = (solution_a, solution_b)
        if any(not isinstance(code, str) for code in self.codes):
            raise ValueError("Solutions must be strings")
        self.base = Path(config.get("runtime_base", "/tmp/mle-agent-sandboxes"))
        self.path = self.base / sample_uuid / self.trajectory_uuid
        self.lease = None
        self.proc = None
        self.lock = asyncio.Lock()
        self.deadline = None
        self.started = None
        self.setup_s = 0

    async def start(self):
        start = time.monotonic()
        ensure_runtime_base(self.base)
        limit = int(self.config.get("max_concurrent_sandboxes", 32))
        if not 1 <= limit <= 256:
            raise ValueError("max_concurrent_sandboxes must be in [1,256]")
        # Same root and UID pool across all Ray workers; a lease is also a node slot.
        while self.lease is None:
            try:
                self.lease = UidLease.acquire(self.base, 300000, 300000 + limit - 1)
            except RuntimeError:
                if time.monotonic() - start > self.config.get("slot_timeout_s", 3600):
                    raise TimeoutError("Timed out waiting for sandbox slot")
                await asyncio.sleep(1.0)
        self.path.mkdir(parents=True, mode=0o700)
        workspace = self.path / "workspace_agent"
        workspace.mkdir()
        (self.path / "root").mkdir()
        for name, code in zip(("candidate_A", "candidate_B"), self.codes):
            folder = workspace / name
            folder.mkdir()
            with (folder / "solution.py").open("x", encoding="utf-8", newline="") as file:
                file.write(code)
            (folder / "data").symlink_to("/mnt/data")
        (workspace / "data").symlink_to("/mnt/data")
        (workspace / "scratch").mkdir()
        chown_tree_no_follow(workspace, self.lease.uid, self.lease.gid)
        cpus = sorted(os.sched_getaffinity(0))
        count = min(int(self.config.get("cpu_cores_per_sandbox", 2)), len(cpus))
        if count < 1:
            raise ValueError("cpu_cores_per_sandbox must be positive")
        offset = (self.lease.uid - 300000) * count
        assigned = [cpus[(offset + i) % len(cpus)] for i in range(count)]
        server_config = {
            "root": str(self.path / "root"), "workspace": str(workspace), "public": str(self.public),
            "uid": self.lease.uid, "cpus": assigned,
            "conda_roots": list(self.config.get("conda_roots", [])),
            "max_output_bytes": self.config.get("max_output_bytes", 65536),
        }
        self.proc = await asyncio.create_subprocess_exec(
            "/usr/bin/python3", "-m", "src.mle_critic.src.agentic.sandbox_server",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=PROJECT_ROOT, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(PROJECT_ROOT)},
            start_new_session=True, limit=2**20,
        )
        self.proc.stdin.write((json.dumps(server_config) + "\n").encode())
        await self.proc.stdin.drain()
        ready = await asyncio.wait_for(self.proc.stdout.readline(), 60)
        if not ready:
            error = await self.proc.stderr.read(16000)
            raise RuntimeError(f"Sandbox startup failed: {error.decode(errors='replace')}")
        if json.loads(ready) != {"ready": True}:
            raise RuntimeError(f"Invalid sandbox handshake: {ready!r}")
        self.started = time.monotonic()
        self.deadline = self.started + self.config.get("trajectory_timeout_s", 600)
        self.setup_s = self.started - start
        return self

    async def call(self, operation, arguments):
        if operation not in ("bash", "text_editor") or not isinstance(arguments, dict):
            raise ValueError("Unknown tool or non-object arguments")
        allowed = {"command"} if operation == "bash" else {
            "command", "path", "old_str", "new_str", "insert_line", "file_text"}
        if set(arguments) - allowed or not isinstance(arguments.get("command"), str):
            raise ValueError("Invalid tool arguments")
        for key, value in arguments.items():
            if key == "insert_line":
                if type(value) is not int:
                    raise ValueError("insert_line must be an integer")
            elif not isinstance(value, str) or "\0" in value:
                raise ValueError(f"{key} must be a NUL-free string")
        if len(json.dumps(arguments).encode()) > 131072:
            raise ValueError("Tool arguments exceed 128 KiB")
        async with self.lock:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Trajectory time budget exhausted")
            request = {"id": uuid4().hex, "operation": operation, "arguments": arguments,
                       "timeout_s": min(remaining, self.config.get("command_timeout_s", 120))}
            self.proc.stdin.write((json.dumps(request) + "\n").encode())
            await self.proc.stdin.drain()
            response = await asyncio.wait_for(self.proc.stdout.readline(), request["timeout_s"] + 5)
            if not response:
                raise RuntimeError("Sandbox command server exited")
            result = json.loads(response)
            if result.get("id") != request["id"]:
                raise RuntimeError("Sandbox response ID mismatch")
            return result

    async def close(self):
        if self.proc is not None:
            try:
                # Killing namespace PID 1 kills all descendants, including double forks.
                self.proc.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self.proc.wait(), 5)
            except asyncio.TimeoutError:
                os.killpg(self.proc.pid, signal.SIGKILL)
                await self.proc.wait()
            self.proc = None
        if self.path.exists():
            shutil.rmtree(self.path)
            try:
                self.path.parent.rmdir()
            except OSError:
                pass
        if self.lease is not None:
            self.lease.release()
            self.lease = None

    async def __aenter__(self):
        try:
            return await self.start()
        except BaseException:
            await self.close()
            raise

    async def __aexit__(self, *exc):
        await asyncio.shield(self.close())
