#!/usr/bin/env bash
set -eo pipefail
source ~/env_setup.sh
set -u
umask 077

CONTROL_REPO=/research/d7/spc/yzyang4/worktrees/prospective_control_1cf55e8_nosmudge
AUDIT_REPO=/research/d7/spc/yzyang4/worktrees/archive_task_audit_5ee342f
AUDIT_COMMIT=5ee342f549311ece7bc111ddd0cb7ff08b740210
ARCHIVE=/research/d7/spc/yzyang4/external/senior_data/mle/0818/multi-modal-gesture-recognition-8seeds.tar.gz
ARCHIVE_SHA=300e602a694075d05b1634d0126a660b0c2f44508cb7ae618732b95f39843d74
OUT_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1/diagnostics/multi_modal_0818_task_identity_20260820
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python

test -d "${CONTROL_REPO}"
test -d "${AUDIT_REPO}"
test "$(git -C "${AUDIT_REPO}" rev-parse HEAD)" = "${AUDIT_COMMIT}"
test -z "$(git -C "${AUDIT_REPO}" status --porcelain --untracked-files=all)"
test "$(sha256sum "${ARCHIVE}" | awk '{print $1}')" = "${ARCHIVE_SHA}"
test ! -e "${OUT_ROOT}"
mkdir -p "${OUT_ROOT}"

cd "${AUDIT_REPO}"
"${PYTHON}" -m phase1.audit_archive_task_identity \
  --archive "${ARCHIVE}" \
  --expect-archive-sha256 "${ARCHIVE_SHA}" \
  --source-commit "${AUDIT_COMMIT}" \
  --output "${OUT_ROOT}/diagnostic_a.json" > "${OUT_ROOT}/run_a.log"
"${PYTHON}" -m phase1.audit_archive_task_identity \
  --archive "${ARCHIVE}" \
  --expect-archive-sha256 "${ARCHIVE_SHA}" \
  --source-commit "${AUDIT_COMMIT}" \
  --output "${OUT_ROOT}/diagnostic_b.json" > "${OUT_ROOT}/run_b.log"
cmp "${OUT_ROOT}/diagnostic_a.json" "${OUT_ROOT}/diagnostic_b.json"
sha256sum "${OUT_ROOT}/diagnostic_a.json"
printf '%s\n' MULTI_MODAL_0818_TASK_IDENTITY_AUDIT_DOUBLE_REPRODUCED
