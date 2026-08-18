#!/usr/bin/env bash
set -eo pipefail
source ~/env_setup.sh
set -u
umask 077

CONTROL_REPO=/research/d7/spc/yzyang4/worktrees/prospective_control_df00f26_nosmudge
AUDIT_REPO=/research/d7/spc/yzyang4/worktrees/archive_task_audit_5ee342f
AUDIT_COMMIT=5ee342f549311ece7bc111ddd0cb7ff08b740210
ARCHIVE=/research/d7/spc/yzyang4/external/senior_data/mle/0817/lmsys-chatbot-arena-8seeds.tar.gz
ARCHIVE_SHA=c73582b32c98cb2ba2731dd867515a8624163998a3b3335a0f21e846ce4a3ffe
OUT_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1/diagnostics/lmsys_0817_task_identity_20260819
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python

if [[ ! -d "${AUDIT_REPO}/.git" && ! -f "${AUDIT_REPO}/.git" ]]; then
  GIT_LFS_SKIP_SMUDGE=1 git -C "${CONTROL_REPO}" worktree add --detach "${AUDIT_REPO}" "${AUDIT_COMMIT}"
fi
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
printf '%s\n' LMSYS_0817_TASK_IDENTITY_AUDIT_DOUBLE_REPRODUCED
