#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var FILELIST
require_var PROJECT_ENV
require_var BUILD_DIR
require_file "${FILELIST}"
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
require_cmd verilator

command=(
  verilator
  --lint-only
  --top-module "${RTL_TOP}"
  --Mdir "${BUILD_DIR}/work"
)
if [[ "${LINT_OPTION_COUNT}" -gt 0 ]]; then
  command+=("${LINT_OPTIONS[@]}")
fi
command+=(-f "${FILELIST}")

"${command[@]}" 2>&1 | tee "${BUILD_DIR}/logs/lint.log"
cp "${BUILD_DIR}/logs/lint.log" "${BUILD_DIR}/reports/lint.rpt"
