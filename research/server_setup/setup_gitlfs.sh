#!/usr/bin/env bash
# Install git-lfs (standalone binary, no root) and pull mle-bench competition leaderboards
# (LFS-tracked; aira-dojo needs them for is_lower_better + medal thresholds).
set -u
export http_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export https_proxy=http://proxy.cse.cuhk.edu.hk:8000/
export NO_PROXY=localhost,127.0.0.1,.cse.cuhk.edu.hk,.cuhk.edu.hk
BIN=/research/d7/spc/yzyang4/bin
TMP=/research/d7/spc/yzyang4/cache/tmp
mkdir -p "$BIN" "$TMP"
export PATH="$BIN:$PATH"

if [ ! -x "$BIN/git-lfs" ]; then
  echo "=== downloading git-lfs ==="
  curl -LsSf https://github.com/git-lfs/git-lfs/releases/download/v3.5.1/git-lfs-linux-amd64-v3.5.1.tar.gz -o "$TMP/git-lfs.tgz" || { echo "FATAL: git-lfs download failed"; exit 1; }
  tar xzf "$TMP/git-lfs.tgz" -C "$TMP"
  cp "$TMP"/git-lfs-*/git-lfs "$BIN/git-lfs" && chmod +x "$BIN/git-lfs"
fi
"$BIN/git-lfs" version || { echo "FATAL: git-lfs not runnable"; exit 1; }

cd /research/d7/spc/yzyang4/mle-bench || { echo "FATAL: mle-bench missing"; exit 1; }
"$BIN/git-lfs" install --local
echo "=== LFS file count ==="
"$BIN/git-lfs" ls-files | wc -l
echo "=== pulling all competition leaderboards ==="
"$BIN/git-lfs" pull --include="mlebench/competitions/*/leaderboard.csv"
echo "pull_rc=$?"
echo "=== verify spaceship-titanic leaderboard ==="
head -c 200 mlebench/competitions/spaceship-titanic/leaderboard.csv
echo ""
echo "GITLFS_DONE"
