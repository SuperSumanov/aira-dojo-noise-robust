"""Drive gdrive_backup through rclone's local backend, never the real remote."""

import shutil
import subprocess

import pytest

from src.mle_critic.src.preprocess.download_and_resolve import gdrive_backup


pytestmark = pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone is not installed")


@pytest.fixture(autouse=True)
def remote_root(tmp_path):
    """Point every test at a local rclone remote, never at the real gdrive one.

    The patch lives on its own MonkeyPatch instance so a test calling
    ``monkeypatch.undo()`` cannot restore the production remote mid-run.
    """
    root = f":local:{tmp_path}/remote"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(gdrive_backup, "REMOTE_ROOT", root)
        yield root


def make_task(data_dir, name, splits=("public", "private")):
    task_dir = data_dir / name
    for split in splits:
        split_dir = task_dir / "prepared" / split
        split_dir.mkdir(parents=True)
        (split_dir / "data.txt").write_text(f"{name}-{split}\n" * 100)
    return task_dir


def remote_entries(remote_root):
    result = subprocess.run(
        ["rclone", "lsf", "-R", "--files-only", remote_root],
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(line for line in result.stdout.splitlines() if line.strip())


def explode(message):
    def fail(*args, **kwargs):
        raise AssertionError(message)

    return fail


def test_missing_archives_are_packed_uploaded_and_cleaned_up(tmp_path, remote_root):
    task_dir = make_task(tmp_path / "data", "task-a")

    gdrive_backup.backup_task(task_dir, force=False)

    assert remote_entries(remote_root) == [
        "task-a/prepared/private.tar",
        "task-a/prepared/public.tar",
    ]
    assert not list((task_dir / "prepared").glob("*.tar*"))


def test_existing_remote_archive_is_not_packed_again(tmp_path, remote_root, monkeypatch):
    task_dir = make_task(tmp_path / "data", "task-a")
    gdrive_backup.backup_task(task_dir, force=False)

    # Nothing may be packed or uploaded on the second pass.
    monkeypatch.setattr(gdrive_backup, "make_tarball", explode("unexpectedly packed a tarball"))
    monkeypatch.setattr(gdrive_backup, "run_rclone", explode("unexpectedly ran rclone"))
    gdrive_backup.backup_task(task_dir, force=False)

    assert not list((task_dir / "prepared").glob("*.tar*"))


def test_force_repacks_and_reuploads(tmp_path, remote_root):
    task_dir = make_task(tmp_path / "data", "task-a")
    gdrive_backup.backup_task(task_dir, force=False)
    before = (tmp_path / "remote" / "task-a" / "prepared" / "public.tar").stat().st_mtime_ns

    gdrive_backup.backup_task(task_dir, force=True)

    assert remote_entries(remote_root) == [
        "task-a/prepared/private.tar",
        "task-a/prepared/public.tar",
    ]
    assert (tmp_path / "remote" / "task-a" / "prepared" / "public.tar").stat().st_mtime_ns >= before
    assert not list((task_dir / "prepared").glob("*.tar*"))


def test_leftover_partial_is_replaced_by_a_complete_archive(tmp_path, remote_root):
    task_dir = make_task(tmp_path / "data", "task-a")
    task_dir.joinpath("prepared", "public.tar.partial").write_text("truncated")

    gdrive_backup.backup_task(task_dir, force=False)

    assert remote_entries(remote_root) == [
        "task-a/prepared/private.tar",
        "task-a/prepared/public.tar",
    ]
    assert not list((task_dir / "prepared").glob("*.partial"))


def test_failed_upload_keeps_the_archive_so_a_retry_does_not_repack(
    tmp_path, remote_root, monkeypatch
):
    task_dir = make_task(tmp_path / "data", "task-a")
    real_run_rclone = gdrive_backup.run_rclone

    def fail_upload(*args):
        if args[0] == "copyto":
            raise RuntimeError("simulated upload failure")
        real_run_rclone(*args)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(gdrive_backup, "run_rclone", fail_upload)
        with pytest.raises(RuntimeError, match="simulated upload failure"):
            gdrive_backup.backup_task(task_dir, force=False)
    assert (task_dir / "prepared" / "public.tar").exists()

    real_make_tarball = gdrive_backup.make_tarball

    def fail_if_repacking_public(source, archive):
        assert archive.name != "public.tar", "re-packed an archive that was already kept"
        real_make_tarball(source, archive)

    monkeypatch.setattr(gdrive_backup, "make_tarball", fail_if_repacking_public)
    gdrive_backup.backup_task(task_dir, force=False)
    assert remote_entries(remote_root) == [
        "task-a/prepared/private.tar",
        "task-a/prepared/public.tar",
    ]


def test_missing_split_and_missing_prepared_dir_are_skipped(tmp_path, remote_root):
    data_dir = tmp_path / "data"
    only_public = make_task(data_dir, "task-b", splits=("public",))
    (data_dir / "task-c").mkdir()

    gdrive_backup.backup_task(only_public, force=False)
    gdrive_backup.backup_task(data_dir / "task-c", force=False)

    assert remote_entries(remote_root) == ["task-b/prepared/public.tar"]


def test_rclone_errors_are_not_mistaken_for_a_missing_file():
    with pytest.raises(RuntimeError, match="rclone lsf"):
        gdrive_backup.remote_file_size(":no-such-remote:x/prepared/public.tar")
