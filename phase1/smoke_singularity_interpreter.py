#!/usr/bin/env python3
"""No-LLM compute-node smoke for the production Singularity Jupyter interpreter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
from dojo.core.interpreters.jupyter.jupyter_interpreter import JupyterInterpreter


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.workdir.exists() or args.out.exists():
        raise RuntimeError("refusing existing smoke workdir/output")
    if not args.data_dir.is_dir():
        raise RuntimeError(f"public data missing: {args.data_dir}")
    image_dir = Path("/research/d7/spc/yzyang4/aira-dojo/build/superimage")
    image = image_dir / "superimage.root.2026-07-macos-v1.sif"
    if not image.is_file():
        raise RuntimeError(f"image missing: {image}")
    runtime = shutil.which("singularity")
    if not runtime:
        raise RuntimeError("singularity missing from compute-node PATH")

    args.workdir.mkdir(parents=True)
    cfg = JupyterInterpreterConfig(
        working_dir=str(args.workdir),
        timeout=90,
        container_runtime="singularity",
        superimage_directory=str(image_dir),
        superimage_version="2026-07-macos-v1",
        read_only_overlays=[],
        read_only_binds={},
        env={"HF_HUB_OFFLINE": "1", "NLTK_DATA": "/root/.nltk_data"},
    )
    started = time.monotonic()
    interpreter = None
    result = None
    try:
        interpreter = JupyterInterpreter(cfg, data_dir=args.data_dir)
        result = interpreter.run(
            "from pathlib import Path\n"
            "print('SCHEMA_JUPYTER_EXEC_PASS')\n"
            "print('PUBLIC_TRAIN_VISIBLE', Path('data/train.csv').is_file())\n"
            "Path('host_roundtrip.txt').write_text('roundtrip-pass\\n')\n",
            reset_session=True,
        )
    finally:
        if interpreter is not None:
            interpreter.close()
    wall_s = time.monotonic() - started
    if result is None:
        raise RuntimeError("interpreter returned no result")
    output = "\n".join(result.term_out)
    roundtrip = args.workdir / "host_roundtrip.txt"
    payload = {
        "schema_version": 1,
        "runtime_path": runtime,
        "runtime_version": os.popen(f"{runtime} --version").read().strip(),
        "image": str(image),
        "image_sha256": sha256_file(image),
        "public_data": str(args.data_dir),
        "public_data_is_dir": args.data_dir.is_dir(),
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "wall_s": round(wall_s, 6),
        "term_out": result.term_out,
        "marker_present": "SCHEMA_JUPYTER_EXEC_PASS" in output,
        "public_train_visible": "PUBLIC_TRAIN_VISIBLE True" in output,
        "host_roundtrip": roundtrip.read_text(encoding="utf-8") if roundtrip.is_file() else None,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", ""),
        "slurm_step_id": os.environ.get("SLURM_STEP_ID", ""),
        "hostname": os.uname().nodename,
    }
    with args.out.open("x", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if not (
        result.exit_code == 0
        and not result.timed_out
        and payload["marker_present"]
        and payload["public_train_visible"]
        and payload["host_roundtrip"] == "roundtrip-pass\n"
    ):
        raise RuntimeError(f"Singularity Jupyter smoke failed: {payload}")
    print(
        "SCHEMA_SINGULARITY_INTERPRETER_SMOKE_PASS "
        f"wall_s={payload['wall_s']} image_sha256={payload['image_sha256']}"
    )


if __name__ == "__main__":
    main()
