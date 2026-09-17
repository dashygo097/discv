#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var PROJECT_ROOT
require_var PROJECT_ENV
require_var MAKE_BIN
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
check_generated_environment

if [[ "${WORKFLOW_STAGE_COUNT}" -eq 0 ]]; then
  echo "[WORKFLOW] No stages configured"
  exit 0
fi

for stage in "${WORKFLOW_STAGES[@]}"; do
  echo "[WORKFLOW] Running ${stage}"
  "${MAKE_BIN}" --no-print-directory -j "${BUILD_JOBS}" -C "${PROJECT_ROOT}" "${stage}"
done
