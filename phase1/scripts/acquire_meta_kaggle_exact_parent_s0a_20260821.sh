#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u

umask 077
export PYTHONHASHSEED=0

AUDIT_ROOT=/research/d7/spc/yzyang4/external-audits/meta-kaggle-s0a-20260821
RECEIPT_ROOT="$AUDIT_ROOT/receipts/s0a-crlf-v2"
KAGGLE_BIN=/research/d7/spc/yzyang4/venvs/exp/bin/kaggle
mkdir -p "$RECEIPT_ROOT/metadata"

"$KAGGLE_BIN" --version > "$RECEIPT_ROOT/kaggle_cli_version.txt"
"$KAGGLE_BIN" datasets files kaggle/meta-kaggle --page-size 200 --csv \
  > "$RECEIPT_ROOT/dataset_files_before.raw.txt"
tr -d '\r' < "$RECEIPT_ROOT/dataset_files_before.raw.txt" \
  > "$RECEIPT_ROOT/dataset_files_before.csv"
"$KAGGLE_BIN" datasets metadata kaggle/meta-kaggle -p "$RECEIPT_ROOT/metadata" \
  > "$RECEIPT_ROOT/metadata_download.stdout.txt"

grep -Fx 'Competitions.csv,152MB,2026-08-21 05:23:20' "$RECEIPT_ROOT/dataset_files_before.csv"
grep -Fx 'KernelVersionCompetitionSources.csv,163MB,2026-08-21 05:27:29' "$RECEIPT_ROOT/dataset_files_before.csv"
grep -Fx 'KernelVersionKernelSources.csv,51MB,2026-08-21 05:27:26' "$RECEIPT_ROOT/dataset_files_before.csv"
grep -Fx 'Kernels.csv,293MB,2026-08-21 05:27:34' "$RECEIPT_ROOT/dataset_files_before.csv"
grep -Fx 'KernelVersions.csv,5GB,2026-08-21 05:28:49' "$RECEIPT_ROOT/dataset_files_before.csv"
grep -Fx 'Submissions.csv,2GB,2026-08-21 05:28:12' "$RECEIPT_ROOT/dataset_files_before.csv"

if [[ ! -s "$AUDIT_ROOT/Kernels.csv" ]]; then
  "$KAGGLE_BIN" datasets download kaggle/meta-kaggle -f Kernels.csv \
    -p "$AUDIT_ROOT" --unzip
fi
if [[ ! -s "$AUDIT_ROOT/KernelVersions.csv" ]]; then
  "$KAGGLE_BIN" datasets download kaggle/meta-kaggle -f KernelVersions.csv \
    -p "$AUDIT_ROOT" --unzip
fi
if [[ ! -s "$AUDIT_ROOT/Submissions.csv" ]]; then
  "$KAGGLE_BIN" datasets download kaggle/meta-kaggle -f Submissions.csv \
    -p "$AUDIT_ROOT" --unzip
fi

test -s "$AUDIT_ROOT/Competitions.csv"
test -s "$AUDIT_ROOT/KernelVersionCompetitionSources.csv"
test -s "$AUDIT_ROOT/KernelVersionKernelSources.csv"
test -s "$AUDIT_ROOT/Kernels.csv"
test -s "$AUDIT_ROOT/KernelVersions.csv"
test -s "$AUDIT_ROOT/Submissions.csv"

"$KAGGLE_BIN" datasets files kaggle/meta-kaggle --page-size 200 --csv \
  > "$RECEIPT_ROOT/dataset_files_after.raw.txt"
tr -d '\r' < "$RECEIPT_ROOT/dataset_files_after.raw.txt" \
  > "$RECEIPT_ROOT/dataset_files_after.csv"
cmp "$RECEIPT_ROOT/dataset_files_before.csv" "$RECEIPT_ROOT/dataset_files_after.csv"

sha256sum \
  "$AUDIT_ROOT/Competitions.csv" \
  "$AUDIT_ROOT/KernelVersionCompetitionSources.csv" \
  "$AUDIT_ROOT/KernelVersionKernelSources.csv" \
  "$AUDIT_ROOT/Kernels.csv" \
  "$AUDIT_ROOT/KernelVersions.csv" \
  "$AUDIT_ROOT/Submissions.csv" \
  "$RECEIPT_ROOT/metadata/dataset-metadata.json" \
  > "$RECEIPT_ROOT/input_sha256.txt"

wc -c \
  "$AUDIT_ROOT/Competitions.csv" \
  "$AUDIT_ROOT/KernelVersionCompetitionSources.csv" \
  "$AUDIT_ROOT/KernelVersionKernelSources.csv" \
  "$AUDIT_ROOT/Kernels.csv" \
  "$AUDIT_ROOT/KernelVersions.csv" \
  "$AUDIT_ROOT/Submissions.csv" \
  > "$RECEIPT_ROOT/input_bytes.txt"

head -n 1 "$AUDIT_ROOT/Competitions.csv" > "$RECEIPT_ROOT/header_Competitions.txt"
head -n 1 "$AUDIT_ROOT/KernelVersionCompetitionSources.csv" > "$RECEIPT_ROOT/header_KernelVersionCompetitionSources.txt"
head -n 1 "$AUDIT_ROOT/KernelVersionKernelSources.csv" > "$RECEIPT_ROOT/header_KernelVersionKernelSources.txt"
head -n 1 "$AUDIT_ROOT/Kernels.csv" > "$RECEIPT_ROOT/header_Kernels.txt"
head -n 1 "$AUDIT_ROOT/KernelVersions.csv" > "$RECEIPT_ROOT/header_KernelVersions.txt"
head -n 1 "$AUDIT_ROOT/Submissions.csv" > "$RECEIPT_ROOT/header_Submissions.txt"

printf '%s\n' 'META_KAGGLE_EXACT_PARENT_S0A_COMPLETE_NO_DATA_ROWS_OPENED' \
  > "$RECEIPT_ROOT/COMPLETE_S0A"
chmod -R go-rwx "$AUDIT_ROOT"
