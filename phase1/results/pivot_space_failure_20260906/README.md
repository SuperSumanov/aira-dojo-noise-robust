# 1.7B/16K engineering preparation stopped by project quota

Source: `ef19d100ac6cb1a747c332eb1b8596051f47a695`. No GPU job was submitted.

Actual Linux preflight completed 160 CPU tests and the runtime/model binding check.
The subsequent non-sparse 64 GiB allocation failed with `EDQUOT` (errno 122):
requested 68,719,476,736 bytes, actual allocated bytes 0. Only the probe inode created
by this preparation was removed. No user checkpoints, environments, caches or
worktrees were deleted. No READY/SUBMISSION_INTENT/SUBMITTED receipt exists.

The eight original files plus SUMMARY are authenticated by MANIFEST:
`6475b8bab8ff24ab4ab48287c5625f6a1944ccd3b1d173355a95afa47d3cc134`.
The transfer archive SHA256 was
`c90bd96190fb3d4d47f7db6d93c83ae65bef1e8e9fa954e1ea5b00a40c755636`.
All ten imported raw files are byte-identical to the remote export. Raw failures
are retained; no log editing or newline normalization is allowed.

The separate tiny ZeRO3 acceptance remains valid. Neither these preflight tests
nor that tiny acceptance establish 1.7B/16K feasibility, source eligibility,
four-fit training, model quality or scaling. Source admission remains empty.

Read-only storage reconnaissance found four clean old ancestor checkouts among
63 candidates, representing 3,123,566,361 tracked Git blob bytes. This is not a
measurement of safely reclaimable disk space and no cleanup followed. Filesystem
free space and the official 1 TB allocation are not evidence of available project
quota. Official storage expiry remains 2026-09-29.

Do not rerun the completed exclusive preparation path or release old job 12535.
Genuine capacity resolution and a separately reviewed successor are required.
