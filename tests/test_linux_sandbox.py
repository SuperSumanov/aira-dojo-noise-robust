from pathlib import Path

import pytest

from dojo.core.interpreters.linux_sandbox import UidLease, parse_mountinfo, validate_workspace_path


def test_parse_mountinfo_tracks_writable_mounts_and_escaped_paths() -> None:
    mounts = parse_mountinfo(
        "36 25 0:32 / / rw,relatime shared:1 - overlay overlay rw,lowerdir=/lower\n"
        "37 36 0:33 / /space\\040dir ro,nosuid - tmpfs tmpfs ro,size=1024k\n"
    )

    assert mounts[0].mount_point == Path("/")
    assert mounts[0].writable
    assert mounts[1].mount_point == Path("/space dir")
    assert not mounts[1].writable


def test_validate_workspace_requires_dedicated_default_name(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"

    with pytest.raises(ValueError, match="workspace_agent"):
        validate_workspace_path(tmp_path / "work", None, runtime)

    assert (
        validate_workspace_path(tmp_path / "workspace_agent", None, runtime).name
        == "workspace_agent"
    )


def test_validate_workspace_rejects_filesystem_root_allowlist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="narrower"):
        validate_workspace_path(tmp_path / "workspace_agent", "/", tmp_path / "runtime")


def test_validate_workspace_rejects_symlink(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "workspace_agent"
    link.symlink_to(actual, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        validate_workspace_path(link, None, tmp_path / "runtime")


def test_uid_leases_do_not_collide(tmp_path: Path) -> None:
    first = UidLease.acquire(tmp_path, 250000, 250001)
    second = UidLease.acquire(tmp_path, 250000, 250001)
    try:
        assert first.uid != second.uid
        with pytest.raises(RuntimeError, match="No free sandbox UID"):
            UidLease.acquire(tmp_path, 250000, 250001)
    finally:
        second.release()
        first.release()
