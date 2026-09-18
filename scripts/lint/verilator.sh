#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var RTL_FILELIST
require_var PROJECT_ENV
require_var STAGE_WORK_DIR
require_file "${RTL_FILELIST}"
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
require_cmd verilator
verilator --version >"${STAGE_WORK_DIR}/tool-version.txt" 2>/dev/null || true

command=(
  verilator
  --lint-only
  --top-module "${RTL_TOP}"
  --Mdir "${STAGE_WORK_DIR}/verilator"
)
if [[ "${LINT_OPTION_COUNT}" -gt 0 ]]; then
  command+=("${LINT_OPTIONS[@]}")
fi
command+=(-f "${RTL_FILELIST}")

"${command[@]}"
