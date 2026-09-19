#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

for variable in \
  PROJECT_ENV \
  RTL_TCL \
  CONSTRAINTS_SDC \
  SYNTH_DC_CONFIG \
  STAGE_WORK_DIR \
  STAGE_REPORT_DIR \
  STAGE_RESULT_DIR; do
  require_var "${variable}"
done

require_file "${PROJECT_ENV}"
require_file "${RTL_TCL}"
require_file "${CONSTRAINTS_SDC}"
require_file "${SYNTH_DC_CONFIG}"
require_file "${SCRIPT_DIR}/dc.tcl"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
require_cmd dc_shell

dc_shell -version >"${STAGE_WORK_DIR}/tool-version.txt" 2>&1 || true

command=(dc_shell)
if [[ "${SYNTH_DC_OPTION_COUNT}" -gt 0 ]]; then
  command+=("${SYNTH_DC_OPTIONS[@]}")
fi
command+=(-f "${SCRIPT_DIR}/dc.tcl")

export RTL_TCL CONSTRAINTS_SDC SYNTH_DC_CONFIG
export STAGE_WORK_DIR STAGE_REPORT_DIR STAGE_RESULT_DIR
export BUILD_JOBS RTL_TOP

set +e
(
  cd "${STAGE_WORK_DIR}"
  "${command[@]}"
)
dc_status=$?
set -e

if [[ "${dc_status}" -eq 0 ]]; then
  for result in \
    "${STAGE_RESULT_DIR}/${RTL_TOP}.ddc" \
    "${STAGE_RESULT_DIR}/${RTL_TOP}.v" \
    "${STAGE_RESULT_DIR}/${RTL_TOP}.sdc" \
    "${STAGE_RESULT_DIR}/${RTL_TOP}.svf"; do
    if [[ ! -f "${result}" ]]; then
      echo "ERROR: Design Compiler did not create required result: ${result}" >&2
      dc_status=1
    fi
  done
fi

exit "${dc_status}"
