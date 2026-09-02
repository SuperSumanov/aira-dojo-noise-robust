#!/usr/bin/env python3
"""Build a deterministic, anonymous, aggregate-only reviewer artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


PROTOCOL = "decision-corpus-anonymous-reviewer-artifact-contract-v0"
STATUS = "ANONYMOUS_AGGREGATE_PREVIEW_NOT_DATASET_RELEASE"
PACKAGE_MANIFEST = "PACKAGE_MANIFEST.json"
HASH_MANIFEST = "MANIFEST.sha256"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

CREDENTIAL_PATTERNS = {
    "openai_compatible_key": re.compile(
        rb"sk-(?:or-v1-)?[A-Za-z0-9._-]{20,}", re.IGNORECASE
    ),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(rb"ghp_[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "private_key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE
    ),
}
IDENTITY_PATTERNS = {
    "private_unix_path": re.compile(rb"/(?:research|uac)/", re.IGNORECASE),
    "private_windows_path": re.compile(rb"C:\\Users\\", re.IGNORECASE),
    "private_host_alias": re.compile(rb"\blinux[0-9]+\b", re.IGNORECASE),
    "ipv4_address": re.compile(
        rb"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])"
    ),
    "email_address": re.compile(
        rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    ),
}


class ArtifactBuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_source_payload(path: Path, source: str, policy: dict) -> bytes:
    raw = path.read_bytes()
    suffix = PurePosixPath(source).suffix.lower()
    binary_suffixes = policy["binary_exact_suffixes"]
    if suffix in binary_suffixes:
        return raw
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactBuildError(f"non-UTF-8 text resource: {source}") from exc
    if "\x00" in text:
        raise ArtifactBuildError(f"NUL byte in text resource: {source}")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def safe_relative(value: str, *, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ArtifactBuildError(f"invalid {field} path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArtifactBuildError(f"unsafe {field} path: {value!r}")
    if any(part == ".git" for part in path.parts):
        raise ArtifactBuildError(f"Git metadata cannot be packaged: {value!r}")
    return path


def scan_bytes(relative: str, payload: bytes) -> None:
    hits = [
        f"credential:{name}"
        for name, pattern in CREDENTIAL_PATTERNS.items()
        if pattern.search(payload)
    ]
    hits.extend(
        f"identity:{name}"
        for name, pattern in IDENTITY_PATTERNS.items()
        if pattern.search(payload)
    )
    if hits:
        raise ArtifactBuildError(
            f"security scan failed for {relative}: {','.join(sorted(hits))}"
        )


def load_contract(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactBuildError(f"cannot read contract: {exc}") from exc
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise ArtifactBuildError("unexpected artifact contract protocol")
    if value.get("status") != STATUS:
        raise ArtifactBuildError("unexpected artifact status")
    policy = value.get("source_byte_policy")
    if policy != {
        "default": "canonical_lf_utf8_text",
        "binary_exact_suffixes": [".png"],
    }:
        raise ArtifactBuildError("unexpected source-byte policy")
    security = value.get("security")
    required_false = (
        "public_source_commit_included",
        "git_history_included",
        "prospective_content_included",
        "network_required",
        "gpu_required",
        "paid_api_required",
        "model_fit_required",
        "base_model_update_required",
    )
    if not isinstance(security, dict):
        raise ArtifactBuildError("missing security contract")
    if security.get("anonymous") is not True or security.get("aggregate_only") is not True:
        raise ArtifactBuildError("artifact must remain anonymous and aggregate-only")
    if any(security.get(key) is not False for key in required_false):
        raise ArtifactBuildError("security contract authorizes a forbidden capability")
    resources = value.get("resources")
    if not isinstance(resources, list) or not resources:
        raise ArtifactBuildError("artifact resource allowlist is empty")
    sources: set[str] = set()
    destinations: set[str] = set()
    for item in resources:
        if not isinstance(item, dict):
            raise ArtifactBuildError("resource entries must be objects")
        source = safe_relative(item.get("source"), field="source").as_posix()
        destination = safe_relative(
            item.get("destination"), field="destination"
        ).as_posix()
        expected = item.get("sha256")
        role = item.get("role")
        if source in sources or destination in destinations:
            raise ArtifactBuildError("duplicate source or destination in allowlist")
        if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
            raise ArtifactBuildError(f"invalid source hash: {source}")
        if not isinstance(role, str) or not role:
            raise ArtifactBuildError(f"missing resource role: {source}")
        if destination in {PACKAGE_MANIFEST, HASH_MANIFEST}:
            raise ArtifactBuildError("resource collides with generated manifest")
        sources.add(source)
        destinations.add(destination)
    return value


def package_manifest(contract: dict, contract_sha256: str) -> dict:
    resources = contract["resources"]
    return {
        "protocol": "decision-corpus-anonymous-reviewer-package-manifest-v0",
        "package_name": contract["package_name"],
        "package_version": contract["package_version"],
        "status": STATUS,
        "anonymous": True,
        "aggregate_only": True,
        "public_source_commit_included": False,
        "contract_sha256": contract_sha256,
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


def make_hash_manifest(package_root: Path) -> None:
    files = sorted(
        (
            path
            for path in package_root.rglob("*")
            if path.is_file() and path.name != HASH_MANIFEST
        ),
        key=lambda path: path.relative_to(package_root).as_posix(),
    )
    lines = [
        f"{sha256(path)}  ./{path.relative_to(package_root).as_posix()}"
        for path in files
    ]
    (package_root / HASH_MANIFEST).write_text(
        "\n".join(lines) + "\n", encoding="ascii", newline="\n"
    )


def make_deterministic_zip(package_root: Path, zip_path: Path, prefix: str) -> None:
    files = sorted(
        (path for path in package_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(package_root).as_posix(),
    )
    with zipfile.ZipFile(
        zip_path,
        mode="x",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for path in files:
            relative = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", date_time=ZIP_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def build(contract_path: Path, repo_root: Path, package_root: Path, zip_path: Path) -> dict:
    contract_path = contract_path.resolve(strict=True)
    repo_root = repo_root.resolve(strict=True)
    package_root = package_root.resolve(strict=False)
    zip_path = zip_path.resolve(strict=False)
    contract = load_contract(contract_path)
    if package_root.exists() or zip_path.exists():
        raise ArtifactBuildError("refusing to overwrite artifact output")
    if package_root == repo_root or repo_root in package_root.parents:
        # Outputs under the repository are allowed, but never at a source path.
        source_paths = {
            (repo_root / item["source"]).resolve(strict=True)
            for item in contract["resources"]
        }
        if package_root in source_paths or any(package_root in path.parents for path in source_paths):
            raise ArtifactBuildError("package output would contain or overwrite sources")
    if package_root == zip_path or package_root in zip_path.parents:
        raise ArtifactBuildError("ZIP must be outside the package directory")

    validated: list[tuple[dict, bytes]] = []
    for item in contract["resources"]:
        source = (repo_root / item["source"]).resolve(strict=True)
        if repo_root not in source.parents or source.is_symlink() or not source.is_file():
            raise ArtifactBuildError(f"unsafe source file: {item['source']}")
        payload = canonical_source_payload(
            source, item["source"], contract["source_byte_policy"]
        )
        actual = hashlib.sha256(payload).hexdigest()
        if actual != item["sha256"]:
            raise ArtifactBuildError(
                f"source hash drift: {item['source']} expected={item['sha256']} actual={actual}"
            )
        scan_bytes(item["destination"], payload)
        validated.append((item, payload))

    package_root.mkdir(parents=True, mode=0o755)
    copied: list[dict] = []
    for item, payload in validated:
        destination = package_root / PurePosixPath(item["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        os.chmod(destination, 0o644)
        copied.append(
            {
                "path": item["destination"],
                "bytes": len(payload),
                "sha256": actual,
            }
        )

    manifest_value = package_manifest(contract, sha256(contract_path))
    write_json(package_root / PACKAGE_MANIFEST, manifest_value)
    scan_bytes(PACKAGE_MANIFEST, (package_root / PACKAGE_MANIFEST).read_bytes())
    make_hash_manifest(package_root)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    make_deterministic_zip(package_root, zip_path, contract["package_name"])
    return {
        "protocol": "decision-corpus-anonymous-reviewer-artifact-build-v0",
        "status": "PASS",
        "package_root": str(package_root),
        "resource_files": len(copied),
        "package_files": sum(1 for path in package_root.rglob("*") if path.is_file()),
        "resource_bytes": sum(item["bytes"] for item in copied),
        "zip_path": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
        "credential_identity_hits": 0,
        "prospective_values_or_identities_read": False,
        "network_gpu_paid_api_model_fit_base_update": [0, 0, 0, 0, 0],
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contract",
        type=Path,
        default=repo_root / "phase1/anonymous_reviewer_artifact_v0.json",
    )
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.contract, args.repo_root, args.package_root, args.zip_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
