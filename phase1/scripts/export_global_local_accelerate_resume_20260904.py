"""Export only verified synthetic receipts, never framework binary checkpoints."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


PACKAGE = Path("/tmp/gl-accelerate-20260904-XmQYTa")
ROOT = PACKAGE / "resume-r1"
OUTPUT = PACKAGE / "resume-public-r1"


def main():
    if OUTPUT.exists():
        raise RuntimeError("exclusive_export_required")
    execution = json.loads((PACKAGE / "resume-r1-exit.json").read_text())
    if execution["returncode"] != 0 or execution["timed_out"]:
        raise RuntimeError("execution_incomplete")
    summary_path = ROOT / "summary.json"
    summary_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    result = subprocess.run([sys.executable, "-B", str(PACKAGE / "phase1/verify_global_local_accelerate_resume.py"),
                             "--root", str(ROOT), "--summary-sha", summary_sha], text=True,
                            capture_output=True, timeout=180)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError("independent_binary_verifier_failed")
    receipt = json.loads(result.stdout)
    OUTPUT.mkdir(mode=0o700)
    for name in ("summary.json", "preflight.json", "runs.csv"):
        shutil.copyfile(ROOT / name, OUTPUT / name)
    shutil.copyfile(PACKAGE / "resume-r1-exit.json", OUTPUT / "execution_exit.json")
    shutil.copyfile(PACKAGE / "resume-r1.log", OUTPUT / "execution.log")
    (OUTPUT / "independent_binary_receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    summary = json.loads(summary_path.read_text())
    for trial in summary["trials"]:
        source = ROOT / trial["name"]
        target = OUTPUT / trial["name"]
        target.mkdir(mode=0o700)
        shutil.copyfile(source / "trajectory.json", target / "trajectory.json")
        trajectory = json.loads((source / "trajectory.json").read_text())
        for saved in trajectory["saved"]:
            name = f"checkpoint-{saved['step']}"
            (target / name).mkdir(mode=0o700)
            for file in ["manifest.json"] + [f"observed_{r}.json" for r in range(trial["world"])]:
                shutil.copyfile(source / name / file, target / name / file)
    checked = subprocess.run([sys.executable, "-B", str(PACKAGE / "phase1/verify_global_local_accelerate_resume.py"),
                              "--root", str(OUTPUT), "--summary-sha", summary_sha, "--receipt-only"],
                             capture_output=True, text=True, timeout=60)
    if checked.returncode:
        print(checked.stderr, file=sys.stderr)
        raise RuntimeError("receipt_export_verification_failed")
    (OUTPUT / "independent_export_receipt.json").write_text(checked.stdout)
    files = sorted(p for p in OUTPUT.rglob("*") if p.is_file())
    for path in files:
        if path.suffix not in (".json", ".csv", ".log") or path.is_symlink():
            raise RuntimeError("unapproved_export_type")
        if re.search(rb"sk-[A-Za-z0-9_.-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}", path.read_bytes()):
            raise RuntimeError("credential_shape_hit")
    archive = PACKAGE / "resume-public-r1.tar.gz"
    with tarfile.open(archive, "x:gz") as stream:
        for path in files:
            stream.add(path, arcname=str(path.relative_to(OUTPUT)), recursive=False)
    print(json.dumps({"summary_sha256": summary_sha, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "export_files": len(files), "uncompressed_bytes": sum(p.stat().st_size for p in files),
        "binary_verification": receipt, "credential_shape_hits": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
