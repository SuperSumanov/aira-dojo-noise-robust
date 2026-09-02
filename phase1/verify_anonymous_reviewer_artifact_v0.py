#!/usr/bin/env python3
"""Independently verify the anonymous reviewer artifact and deterministic ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


CONTRACT_PROTOCOL = "decision-corpus-anonymous-reviewer-artifact-contract-v0"
PACKAGE_PROTOCOL = "decision-corpus-anonymous-reviewer-package-manifest-v0"
STATUS = "ANONYMOUS_AGGREGATE_PREVIEW_NOT_DATASET_RELEASE"
PACKAGE_MANIFEST = "PACKAGE_MANIFEST.json"
HASH_MANIFEST = "MANIFEST.sha256"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_RE = re.compile(r"^([0-9a-f]{64})  \./(.+)$")

CREDENTIAL_PATTERNS = (
    re.compile(rb"sk-(?:or-v1-)?[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE),
)
IDENTITY_PATTERNS = (
    re.compile(rb"/(?:research|uac)/", re.IGNORECASE),
    re.compile(rb"C:\\Users\\", re.IGNORECASE),
    re.compile(rb"\blinux[0-9]+\b", re.IGNORECASE),
    re.compile(rb"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])"),
    re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)


class ArtifactVerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactVerificationError(f"expected JSON object: {path}")
    return value


def canonical_source_payload(path: Path, source: str, policy: dict) -> bytes:
    raw = path.read_bytes()
    if PurePosixPath(source).suffix.lower() in policy["binary_exact_suffixes"]:
        return raw
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactVerificationError(f"non-UTF-8 text resource: {source}") from exc
    if "\x00" in text:
        raise ArtifactVerificationError(f"NUL byte in text resource: {source}")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ArtifactVerificationError("invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise ArtifactVerificationError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def scan_payload(relative: str, payload: bytes) -> None:
    if any(pattern.search(payload) for pattern in CREDENTIAL_PATTERNS):
        raise ArtifactVerificationError(f"credential-shaped bytes: {relative}")
    if any(pattern.search(payload) for pattern in IDENTITY_PATTERNS):
        raise ArtifactVerificationError(f"identity-shaped bytes: {relative}")


def validate_contract(contract: dict) -> tuple[list[dict], set[str]]:
    if contract.get("protocol") != CONTRACT_PROTOCOL or contract.get("status") != STATUS:
        raise ArtifactVerificationError("unexpected contract protocol or status")
    if contract.get("source_byte_policy") != {
        "default": "canonical_lf_utf8_text",
        "binary_exact_suffixes": [".png"],
    }:
        raise ArtifactVerificationError("unexpected source-byte policy")
    security = contract.get("security")
    if not isinstance(security, dict):
        raise ArtifactVerificationError("missing contract security")
    expected_security = {
        "anonymous": True,
        "aggregate_only": True,
        "public_source_commit_included": False,
        "git_history_included": False,
        "prospective_content_included": False,
        "network_required": False,
        "gpu_required": False,
        "paid_api_required": False,
        "model_fit_required": False,
        "base_model_update_required": False,
    }
    if any(security.get(key) is not value for key, value in expected_security.items()):
        raise ArtifactVerificationError("contract security drift")
    resources = contract.get("resources")
    if not isinstance(resources, list) or not resources:
        raise ArtifactVerificationError("empty contract resource list")
    destinations: set[str] = set()
    sources: set[str] = set()
    for item in resources:
        if not isinstance(item, dict):
            raise ArtifactVerificationError("resource entry is not an object")
        source = safe_relative(item.get("source"))
        destination = safe_relative(item.get("destination"))
        if source in sources or destination in destinations:
            raise ArtifactVerificationError("duplicate source or destination")
        if destination in {PACKAGE_MANIFEST, HASH_MANIFEST}:
            raise ArtifactVerificationError("resource collides with generated manifest")
        if SHA256_RE.fullmatch(str(item.get("sha256"))) is None:
            raise ArtifactVerificationError(f"invalid source hash: {source}")
        if not isinstance(item.get("role"), str) or not item["role"]:
            raise ArtifactVerificationError(f"missing role: {source}")
        sources.add(source)
        destinations.add(destination)
    return resources, destinations


def expected_package_manifest(contract: dict, contract_hash: str) -> dict:
    resources = contract["resources"]
    return {
        "protocol": PACKAGE_PROTOCOL,
        "package_name": contract["package_name"],
        "package_version": contract["package_version"],
        "status": STATUS,
        "anonymous": True,
        "aggregate_only": True,
        "public_source_commit_included": False,
        "contract_sha256": contract_hash,
        "resource_files": len(resources),
        "manifest_entries_excluding_hash_manifest": len(resources) + 1,
        "hash_manifest_covers_all_other_files": True,
        "capability_matrix": contract["capability_matrix"],
        "excluded_content": contract["excluded_content"],
        "source_byte_policy": contract["source_byte_policy"],
        "security": contract["security"],
        "files": [
            {
                "path": item["destination"],
                "role": item["role"],
                "sha256": item["sha256"],
            }
            for item in resources
        ],
    }


def parse_hash_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        match = MANIFEST_RE.fullmatch(line)
        if match is None:
            raise ArtifactVerificationError("invalid SHA-256 manifest line")
        relative = safe_relative(match.group(2))
        if relative in entries:
            raise ArtifactVerificationError("duplicate SHA-256 manifest path")
        entries[relative] = match.group(1)
    return entries


def verify_package(
    contract_path: Path, repo_root: Path, package_root: Path
) -> tuple[dict, list[str]]:
    contract = load_object(contract_path)
    resources, destinations = validate_contract(contract)
    expected_files = destinations | {PACKAGE_MANIFEST, HASH_MANIFEST}
    observed_files: set[str] = set()
    for path in package_root.rglob("*"):
        if path.is_symlink():
            raise ArtifactVerificationError("symlink found in package")
        if path.is_file():
            observed_files.add(path.relative_to(package_root).as_posix())
    if observed_files != expected_files:
        missing = sorted(expected_files - observed_files)
        extra = sorted(observed_files - expected_files)
        raise ArtifactVerificationError(f"package file-set mismatch missing={missing} extra={extra}")

    for item in resources:
        source = (repo_root / item["source"]).resolve(strict=True)
        if repo_root not in source.parents or source.is_symlink() or not source.is_file():
            raise ArtifactVerificationError(f"unsafe source: {item['source']}")
        source_payload = canonical_source_payload(
            source, item["source"], contract["source_byte_policy"]
        )
        source_hash = hashlib.sha256(source_payload).hexdigest()
        package_path = package_root / PurePosixPath(item["destination"])
        if source_hash != item["sha256"] or sha256(package_path) != item["sha256"]:
            raise ArtifactVerificationError(f"resource hash mismatch: {item['destination']}")

    package_manifest = load_object(package_root / PACKAGE_MANIFEST)
    expected_manifest = expected_package_manifest(contract, sha256(contract_path))
    if package_manifest != expected_manifest:
        raise ArtifactVerificationError("package manifest differs from contract")

    hash_entries = parse_hash_manifest(package_root / HASH_MANIFEST)
    expected_hashed = observed_files - {HASH_MANIFEST}
    if set(hash_entries) != expected_hashed:
        raise ArtifactVerificationError("SHA-256 manifest file-set mismatch")
    for relative, expected in hash_entries.items():
        if sha256(package_root / PurePosixPath(relative)) != expected:
            raise ArtifactVerificationError(f"SHA-256 manifest mismatch: {relative}")
    for relative in sorted(observed_files):
        scan_payload(relative, (package_root / PurePosixPath(relative)).read_bytes())
    return contract, sorted(observed_files)


def verify_zip(zip_path: Path, package_root: Path, prefix: str, files: list[str]) -> None:
    expected_names = [f"{prefix}/{relative}" for relative in sorted(files)]
    with zipfile.ZipFile(zip_path, mode="r") as archive:
        if archive.comment != b"":
            raise ArtifactVerificationError("ZIP comment must be empty")
        infos = archive.infolist()
        if [info.filename for info in infos] != expected_names:
            raise ArtifactVerificationError("ZIP order or file set mismatch")
        for info, relative in zip(infos, sorted(files)):
            if info.is_dir() or info.date_time != ZIP_TIMESTAMP:
                raise ArtifactVerificationError(f"ZIP timestamp/type drift: {relative}")
            if info.create_system != 3 or info.compress_type != zipfile.ZIP_DEFLATED:
                raise ArtifactVerificationError(f"ZIP platform/compression drift: {relative}")
            if (info.external_attr >> 16) & 0xFFFF != (stat.S_IFREG | 0o644):
                raise ArtifactVerificationError(f"ZIP mode drift: {relative}")
            if info.extra or info.comment:
                raise ArtifactVerificationError(f"ZIP extra metadata: {relative}")
            payload = archive.read(info)
            expected = (package_root / PurePosixPath(relative)).read_bytes()
            if payload != expected:
                raise ArtifactVerificationError(f"ZIP payload mismatch: {relative}")


def main() -> int:
    repo_root_default = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=repo_root_default / "phase1/anonymous_reviewer_artifact_v0.json",
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root_default)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    args = parser.parse_args()
    contract_path = args.contract.resolve(strict=True)
    repo_root = args.repo_root.resolve(strict=True)
    package_root = args.package_root.resolve(strict=True)
    zip_path = args.zip_path.resolve(strict=True)
    contract, files = verify_package(contract_path, repo_root, package_root)
    verify_zip(zip_path, package_root, contract["package_name"], files)
    result = {
        "protocol": "decision-corpus-anonymous-reviewer-artifact-independent-verifier-v0",
        "status": "PASS",
        "package_files": len(files),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
        "credential_identity_hits": 0,
        "prospective_values_or_identities_read": False,
        "network_gpu_paid_api_model_fit_base_update": [0, 0, 0, 0, 0],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
