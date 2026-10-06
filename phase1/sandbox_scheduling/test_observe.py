"""Fixture tests plus a bounded Linux own-process smoke (no GPU/API/data access)."""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import observe as ob


GPU = "GPU-12345678-1234-5678-abcd-123456789abc"
BOOT = "12345678-1234-5678-abcd-123456789abc"
COMMIT = "e5e83b6e4eed842197f7de924ae4734003e8965a"


def stat(*, pid=123, start=777, cpu=23, comm="private ) name", rss=4):
    fields = ["0"] * 50
    fields[0], fields[1], fields[2], fields[3] = "S", "12", "123", "123"
    fields[11], fields[12], fields[17], fields[19], fields[21] = str(cpu), "2", "3", str(start), str(rss)
    return f"{pid} ({comm}) " + " ".join(fields)


def args(output="unused.jsonl", **updates):
    values = dict(pid=["123:777"], boot_id=BOOT, source_commit=COMMIT,
                  gpu_uuid=[], interval=1.0, samples=2, output=output)
    return argparse.Namespace(**(values | updates))


def gpu_text(util="0", used="100", total="24576", gpu=GPU):
    return f"{gpu}, 535.104.05, {util}, {used}, {total}\n"


def reads(*texts):
    """Three reads: stat, IO counters, stat. Raw process name must not escape."""
    stack = ExitStack()
    stack.enter_context(patch.object(Path, "stat", return_value=argparse.Namespace(st_uid=42)))
    stack.enter_context(patch.object(Path, "read_text", side_effect=texts))
    return stack


def process():
    return ob.sample_process(123, 777, proc=Path("fixture_proc"), uid=42, page_size=4096)


IO = "rchar: 9999\nread_bytes: 0\nwrite_bytes: 12\ncancelled_write_bytes: 0\n"


class ObserverTests(unittest.TestCase):
    def test_stat_fields_and_redaction(self):
        result = ob.parse_stat(stat())
        self.assertEqual(result["cpu_ticks"], 25)
        self.assertEqual(result["start_ticks"], 777)
        self.assertEqual(result["rss_pages"], 4)
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(result["threads"], 3)

    def test_bad_stat_rejected(self):
        for text in ["", "private", "1 (x) S", stat(rss=-1), stat(pid=0)]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                ob.parse_stat(text)

    def test_io_allowlist(self):
        self.assertEqual(ob.parse_io(IO), dict(read_bytes=0, write_bytes=12, cancelled_write_bytes=0))
        with self.assertRaises(KeyError):
            ob.parse_io("read_bytes: 0")
        with self.assertRaises(ValueError):
            ob.parse_io(IO.replace("12", "-12"))

    def test_process_identity_and_zero_io(self):
        with reads(stat(), IO, stat(cpu=24)):
            row = process()
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["storage_io"]["read_bytes"], 0)
        self.assertEqual(row["stat"]["rss_bytes_approx"], 16384)
        self.assertEqual(row["scope"], "explicit_pid_only")

    def test_io_denied_is_unknown_not_zero(self):
        with reads(stat(), PermissionError("private detail"), stat()):
            row = process()
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["io_status"], "denied")
        self.assertIsNone(row["storage_io"])
        self.assertNotIn("private", json.dumps(row))

    def test_pid_reuse_rejected_before_and_during(self):
        for inputs, status in [((stat(start=888),), "identity_mismatch"),
                               ((stat(), IO, stat(start=888)), "identity_changed_during_sample")]:
            with self.subTest(status=status), reads(*inputs):
                row = process()
            self.assertEqual(row["status"], status)
            self.assertIsNone(row["stat"])
            self.assertIsNone(row["storage_io"])

    def test_disappeared_process(self):
        with reads(stat(), IO, FileNotFoundError()):
            row = process()
        self.assertEqual(row["status"], "missing")
        self.assertIsNone(row["stat"])

    def test_exited_not_reported_as_idle(self):
        with reads(stat(), IO, stat().replace(") S ", ") Z ")):
            row = process()
        self.assertEqual(row["status"], "exited")
        self.assertIsNone(row["stat"])

    def test_other_user_not_read(self):
        with patch.object(Path, "stat", return_value=argparse.Namespace(st_uid=99)), \
                patch.object(Path, "read_text") as read:
            self.assertEqual(process()["status"], "owner_mismatch")
            read.assert_not_called()

    def test_counter_regression_within_sample(self):
        with reads(stat(cpu=24), IO, stat(cpu=23)):
            self.assertEqual(process()["status"], "counter_regressed_during_sample")

    def test_delta_identity_and_missingness(self):
        a = dict(status="ok", stat=ob.parse_stat(stat()))
        b = dict(status="ok", stat=ob.parse_stat(stat(cpu=33)))
        self.assertEqual(ob.cpu_delta(a, b, 100), dict(status="ok", cpu_seconds=0.1))
        self.assertEqual(ob.cpu_delta(b, a, 100)["status"], "counter_regression")
        for other in [dict(status="missing"), dict(status="ok", stat=ob.parse_stat(stat(start=888)))]:
            self.assertIsNone(ob.cpu_delta(a, other, 100)["cpu_seconds"])

    def test_gpu_na_distinct_from_measured_zero(self):
        data = ob.parse_gpu(gpu_text("N/A"), GPU)
        self.assertIsNone(data["metrics"]["utilization_percent"])
        self.assertEqual(data["field_status"]["utilization_percent"], "unsupported")
        self.assertEqual(ob.parse_gpu(gpu_text("0"), GPU)["metrics"]["utilization_percent"], 0)

    def test_gpu_identity_shape_and_values(self):
        bad = [gpu_text(gpu="GPU-other"), gpu_text("nan"), gpu_text("101"),
               gpu_text("-1"), gpu_text(used="30000"), gpu_text() * 2, ""]
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                ob.parse_gpu(text, GPU)

    def test_gpu_read_only_scoped_command(self):
        with patch.object(subprocess, "run", return_value=argparse.Namespace(returncode=0, stdout=gpu_text())) as run:
            result = ob.sample_gpu(GPU)
        self.assertEqual(result["scope"], "whole_device_not_candidate")
        self.assertEqual(result["status"], "ok")
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["nvidia-smi", "-i", GPU])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(run.call_args.kwargs["timeout"], 2)

    def test_gpu_timeout_no_raw_error(self):
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("private", 2)):
            row = ob.sample_gpu(GPU)
        self.assertEqual(row["status"], "timeout")
        self.assertNotIn("private", json.dumps(row))
        self.assertIsNone(row["data"])

    def test_invalid_target_uuid_rejected_before_query(self):
        with patch.object(subprocess, "run") as run, self.assertRaises(ValueError):
            ob.sample_gpu("0;malicious")
        run.assert_not_called()
        for value in ["0:1", "-1:0", "123", "123:4/../../", "123:-1"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ob.target(value)

    def test_limits_and_duplicate_identity(self):
        ob.validate(args())
        bad = [dict(interval=float("nan")), dict(interval=0), dict(samples=0), dict(samples=601),
               dict(interval=30, samples=600), dict(pid=["123:777", "123:888"]), dict(pid=[]),
               dict(gpu_uuid=[GPU, GPU]), dict(source_commit="short"), dict(boot_id="no-boot")]
        for update in bad:
            with self.subTest(update=update), self.assertRaises(ValueError):
                ob.validate(args(**update))

    def fake_host(self, boot=BOOT):
        stack = ExitStack()
        stack.enter_context(patch.object(platform, "system", return_value="Linux"))
        stack.enter_context(patch.object(Path, "read_text", return_value=boot))
        stack.enter_context(patch.object(os, "getuid", return_value=42, create=True))
        stack.enter_context(patch.object(os, "sysconf", side_effect=[100, 4096], create=True))
        stack.enter_context(patch.object(time, "sleep"))
        return stack

    def test_record_contract_and_no_gpu_query_by_default(self):
        row = dict(status="ok", stat=ob.parse_stat(stat()), io_status="denied", storage_io=None)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.jsonl"
            with self.fake_host(), patch.object(ob, "sample_process", return_value=row), \
                    patch.object(ob, "sample_gpu") as gpu:
                self.assertEqual(ob.record(args(str(output))), 0)
                gpu.assert_not_called()
            records = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual([r["kind"] for r in records], ["header", "sample", "sample", "footer"])
        self.assertFalse(records[0]["candidate_scope_complete"])
        self.assertEqual(records[-1]["status"], "complete")
        self.assertEqual(records[1]["processes"][0]["io_status"], "denied")

    def test_record_stops_on_identity_loss(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.jsonl"
            with self.fake_host(), patch.object(ob, "sample_process", return_value=dict(status="identity_mismatch")):
                self.assertEqual(ob.record(args(str(output))), 2)
            records = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(records[-1]["written_samples"], 1)
        self.assertEqual(records[-1]["status"], "incomplete_observation")

    def test_record_stops_on_gpu_query_failure(self):
        row = dict(status="ok", stat=ob.parse_stat(stat()))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.jsonl"
            with self.fake_host(), patch.object(ob, "sample_process", return_value=row), \
                    patch.object(ob, "sample_gpu", return_value=dict(status="timeout", data=None)):
                self.assertEqual(ob.record(args(str(output), gpu_uuid=[GPU])), 2)
            records = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(records[-1]["written_samples"], 1)
        self.assertIsNone(records[1]["devices"][0]["data"])

    def test_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.jsonl"
            output.write_text("previous receipt")
            with self.fake_host(), self.assertRaises(FileExistsError):
                ob.record(args(str(output)))
            self.assertEqual(output.read_text(), "previous receipt")

    def test_wrong_boot_creates_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "trace.jsonl"
            with self.fake_host(boot="different"), self.assertRaises(ValueError):
                ob.record(args(str(output)))
            self.assertFalse(output.exists())

    @unittest.skipUnless(platform.system() == "Linux", "requires real Linux /proc; not mocked")
    def test_linux_own_process_smoke(self):
        proc, pid = Path("/proc"), os.getpid()
        identity = ob.parse_stat((proc / str(pid) / "stat").read_text())["start_ticks"]
        boot = (proc / "sys/kernel/random/boot_id").read_text().strip()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "live.jsonl"
            config = args(str(output), pid=[f"{pid}:{identity}"], boot_id=boot)
            self.assertEqual(ob.record(config), 0)
            records = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertTrue(all(r["identity_query_ok"] for r in records if r["kind"] == "sample"))
        self.assertGreater(records[1]["processes"][0]["stat"]["rss_bytes_approx"], 0)
        self.assertGreaterEqual(records[2]["processes"][0]["cpu_delta"]["cpu_seconds"], 0)
        self.assertEqual(records[-1]["written_samples"], 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", help="optional new test summary JSON (exclusive create)")
    options = parser.parse_args()
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ObserverTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = dict(kind="engineering_validation_not_research_result", schema="observer-test-v0",
                   tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   skipped=len(result.skipped), success=result.wasSuccessful(),
                   python=platform.python_version(), platform=platform.system(),
                   elapsed_seconds=time.monotonic() - started, utc_unix_ns=time.time_ns(),
                   source_commit=COMMIT, gpu_queried=False, candidate_executions=0,
                   recorder_sha256=hashlib.sha256(Path(ob.__file__).read_bytes()).hexdigest(),
                   tests_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if options.receipt:
        with Path(options.receipt).open("x", encoding="utf-8") as file:
            json.dump(receipt, file, indent=2, sort_keys=True)
            file.write("\n")
    print(json.dumps(receipt, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
