#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var RTL_FILELIST
require_var PROJECT_ENV
require_var STAGE_WORK_DIR
require_var STAGE_REPORT_DIR
require_var STAGE_REPORT
require_file "${RTL_FILELIST}"
require_file "${PROJECT_ENV}"
require_file "${SCRIPT_DIR}/spyglass.tcl"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
require_cmd spyglass

SPYGLASS_WORK_DIR=${STAGE_WORK_DIR}/spyglass
SPYGLASS_REPORT_DIR=${STAGE_REPORT_DIR}/spyglass
SPYGLASS_PROJECT=${STAGE_WORK_DIR}/spyglass.prj
rm -rf "${SPYGLASS_WORK_DIR}" "${SPYGLASS_REPORT_DIR}"
cp "${SCRIPT_DIR}/spyglass.tcl" "${SPYGLASS_PROJECT}"

command=(
  spyglass
  -project "${SPYGLASS_PROJECT}"
  -goals lint/lint_rtl
  -batch
)
if [[ "${LINT_SPYGLASS_OPTION_COUNT}" -gt 0 ]]; then
  command+=("${LINT_SPYGLASS_OPTIONS[@]}")
fi

export RTL_FILELIST RTL_TOP
set +e
(
  cd "${STAGE_WORK_DIR}"
  "${command[@]}"
)
spyglass_status=$?
set -e

mkdir -p "${SPYGLASS_REPORT_DIR}"
if [[ -d "${SPYGLASS_WORK_DIR}/consolidated_reports" ]]; then
  cp -R "${SPYGLASS_WORK_DIR}/consolidated_reports" "${SPYGLASS_REPORT_DIR}/"
fi
if [[ -d "${SPYGLASS_WORK_DIR}/html_reports" ]]; then
  cp -R "${SPYGLASS_WORK_DIR}/html_reports" "${SPYGLASS_REPORT_DIR}/"
fi

moresimple_report=$(find "${SPYGLASS_WORK_DIR}" \
  -type f -name moresimple.rpt -print -quit 2>/dev/null || true)
if [[ -n "${moresimple_report}" ]]; then
  cp "${moresimple_report}" "${STAGE_REPORT}"
fi

exit "${spyglass_status}"
