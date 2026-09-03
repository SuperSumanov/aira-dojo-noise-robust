"""Bounded CPU runner with retained return-code receipt; no shell command chain."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


ROOT = Path("/tmp/gl-accelerate-20260904-XmQYTa")
PYTHON = "/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260903-selective/bin/python"
OUTPUT = ROOT / "resume-r1"


def main():
    if not ROOT.is_dir() or ROOT.is_symlink() or OUTPUT.exists():
        raise RuntimeError("output_or_package_precondition_failed")
    overrides = {
        "CUDA_VISIBLE_DEVICES": "", "ACCELERATE_USE_CPU": "true", "GLOO_SOCKET_IFNAME": "lo",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(ROOT), "TOKENIZERS_PARALLELISM": "false",
        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_OFFLINE": "1", "WANDB_DISABLED": "true",
        "TMPDIR": str(ROOT / "tmp"), "TRITON_CACHE_DIR": str(ROOT / "triton"),
    }
    environment = dict(os.environ, **overrides)
    command = [PYTHON, "-B", str(ROOT / "phase1/global_local_accelerate_resume_validation.py"),
               "--output", str(OUTPUT)]
    receipt_path = ROOT / "resume-r1-exit.json"
    if receipt_path.exists():
        raise RuntimeError("exit_receipt_already_exists")
    start = time.monotonic()
    with (ROOT / "resume-r1.log").open("x") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps({"started_pid": process.pid, "cpu_only": True, "max_seconds": 1200}), flush=True)
        timed_out = False
        try:
            result = process.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.getpgid(process.pid) != process.pid:
                raise RuntimeError("unexpected_child_process_group")
            os.killpg(process.pid, signal.SIGTERM)
            try:
                result = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                result = process.wait(timeout=10)
    receipt = {"command": command, "environment_overrides": overrides, "returncode": result,
               "timed_out": timed_out, "elapsed_seconds": time.monotonic() - start,
               "GPU": 0, "paid_API": 0, "research_model_fits": 0}
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(receipt), flush=True)
    raise SystemExit(124 if timed_out else result)


if __name__ == "__main__":
    main()
