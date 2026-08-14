"""Inside-container preflight for the E1 public-only, networkless execution boundary."""

from __future__ import annotations

import csv
import importlib
import json
import os
import pathlib
import socket
import sys


def main() -> int:
    required_packages = ("numpy", "pandas", "sklearn", "lightgbm", "catboost")
    versions = {}
    for package in required_packages:
        module = importlib.import_module(package)
        versions[package] = str(getattr(module, "__version__", "unknown"))
    data = pathlib.Path("/workspace/data")
    train = data / "train.csv"
    if not train.is_file() or data.is_symlink():
        print("CAPABILITY_PROBE_ERROR: public train mount differs", file=sys.stderr)
        return 2
    with train.open("r", encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))
    write_blocked = False
    probe = data / ".e1-write-probe"
    try:
        probe.write_bytes(b"must not be writable")
    except OSError:
        write_blocked = True
    finally:
        if probe.exists():
            probe.unlink()
    if not write_blocked:
        print("CAPABILITY_PROBE_ERROR: public data mount is writable", file=sys.stderr)
        return 3
    network_blocked = False
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=1.0):
            pass
    except OSError:
        network_blocked = True
    if not network_blocked:
        print("CAPABILITY_PROBE_ERROR: external network is reachable", file=sys.stderr)
        return 4
    forbidden_environment = sorted(
        key for key in os.environ
        if key.startswith(("PRIMARY_KEY", "SINGULARITYENV_", "APPTAINERENV_"))
    )
    if forbidden_environment:
        print("CAPABILITY_PROBE_ERROR: provider environment reached candidate", file=sys.stderr)
        return 5
    if pathlib.Path("/research/d7/spc/yzyang4").exists():
        print("CAPABILITY_PROBE_ERROR: host research filesystem is visible", file=sys.stderr)
        return 6
    result = {
        "status": "E1_CONTAINER_CAPABILITY_PASS",
        "public_train_readable": True,
        "public_header_columns": len(header),
        "public_mount_write_blocked": True,
        "external_network_blocked": True,
        "provider_environment_variables_visible": 0,
        "host_research_filesystem_visible": False,
        "required_package_versions": versions,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
