# 09-03 source drop: bounded append-only synchronization

Before download, direct shared-Drive metadata (not the cached mirror) showed 9 archives
in 0903, all absent locally. 0901/0902 each had 10 matching names. The root contained
43 folders, including 37 plain date names, four dated Chinese descriptive names, and
`checkpoint`/`mlebench`; newest date was 0903. Neither non-corpus subtree is in scope.
Name equality does not prove remote/local byte equality. Senior Git b8d0951 is unchanged.

The first recursive metadata attempt stopped at its 80-request cap with no payload
download. A second attempt rejected descriptive folder names before fetching children.
The narrower successful check queried only 0901/0902/0903, three pages, no payloads.
Private manifest SHA: d9e28b413b64c9fff05af15015060e977fbc467365e7f7a10b8ae1e7f7f5ea08.

## Fixed download scope and acceptance

- Exactly the nine 0903 archives from that hash-bound manifest. No model checkpoints,
  competition data, repository change, API credential, cookie-file read or paid API.
- Existing gdown 5.2.0; download.py SHA
  25a72cbed857190c010762291c7484f1e9fb7d9df17d7bf74bb26a14cd48ed56.
- New mode-0700 private staging directory; exclusive file creation; per-file cap 128 MiB,
  aggregate cap 1 GiB, at most 100 HTTP requests and 30 minutes. No automatic retry after
  failure. HTTPS certificate verification stays on; only Google-owned download hosts.
- Check 1 GiB allocation in the destination filesystem first, then remove only that
  newly created reservation after checking its inode/device/owner. This is not a claim
  about the account's total quota or a permanent space guarantee.
- Stream to already-open bounded files, not gdown filename mode. This deliberately keeps
  download-time mtimes; no inherited/backdated HTTP Last-Modified timestamps. The frozen
  six-hour age plus three observations/ten-minute stable-span gates remain intact.
- No decompression, member inspection, archive-value parsing, or local payload copying.
  Only gzip signature and two independent compressed-byte SHA passes; remote staging
  can contain raw credentials and is therefore private and excluded from Git.
- Re-list 0903 metadata and require exactly the same file IDs/names before promotion.
  Atomic directory rename to an absent 0903 directory, on the same filesystem; never
  overwrite or rename existing user data. The old 316 archives remain untouched.
- Save full private manifest/HTTP facts remotely and an aggregate public receipt. Failures
  retain private staged files and exit receipts. No change to scientific/control sources,
  rejection registry, scorer, frozen cohort, approved G0, or training budget.

Promotion is download completion, NOT intake acceptance or an increase in eligible runs.
New files may not mature inside this six-hour conversation window; do not fabricate
older mtimes to force admission. Subsequent intake must use the original gates.
