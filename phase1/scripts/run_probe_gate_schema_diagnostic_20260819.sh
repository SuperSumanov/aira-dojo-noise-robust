#!/usr/bin/env bash
set -eo pipefail

source ~/env_setup.sh
set -u

SOURCE_ROOT=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
DIAGNOSTIC_ROOT=${SOURCE_ROOT}/resume_sharded_20260819/postoutcome_gate_schema_diagnostic_v2
FROZEN_VERIFIER=${SOURCE_ROOT}/prereg/verify_probe_contract_ab_v2_independent.py
DIAGNOSTIC_BUILDER=/tmp/probe_contract_ab_gate_schema_diagnostic.py
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
GRADER=/research/d7/spc/yzyang4/venvs/exp/bin/mlebench
DATA_DIR=/research/d7/spc/yzyang4/mle-bench-data

"${PYTHON}" "${DIAGNOSTIC_BUILDER}" \
  --source-root "${SOURCE_ROOT}" \
  --diagnostic-root "${DIAGNOSTIC_ROOT}"

"${PYTHON}" "${FROZEN_VERIFIER}" \
  --root "${DIAGNOSTIC_ROOT}" \
  --data-dir "${DATA_DIR}" \
  --grader "${GRADER}" \
  --output "${DIAGNOSTIC_ROOT}/independent_probe_contract_ab_result.json"

printf '%s\n' POSTOUTCOME_GATE_SCHEMA_DIAGNOSTIC_COMPLETE
