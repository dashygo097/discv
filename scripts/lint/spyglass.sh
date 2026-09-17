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
require_file "${SCRIPT_DIR}/spyglass.tcl"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
require_cmd spyglass

SPYGLASS_WORK_DIR=${BUILD_DIR}/work/spyglass
SPYGLASS_REPORT_DIR=${BUILD_DIR}/reports/spyglass
SPYGLASS_PROJECT=${BUILD_DIR}/work/spyglass.prj
rm -rf "${SPYGLASS_WORK_DIR}" "${SPYGLASS_REPORT_DIR}"
cp "${SCRIPT_DIR}/spyglass.tcl" "${SPYGLASS_PROJECT}"

command=(
  spyglass
  -project "${SPYGLASS_PROJECT}"
  -goals lint/lint_rtl
  -batch
)
if [[ "${LINT_OPTION_COUNT}" -gt 0 ]]; then
  command+=("${LINT_OPTIONS[@]}")
fi

export FILELIST RTL_TOP BUILD_DIR
set +e
(
  cd "${BUILD_DIR}/work"
  "${command[@]}"
) 2>&1 | tee "${BUILD_DIR}/logs/lint.log"
spyglass_status=${PIPESTATUS[0]}
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
  cp "${moresimple_report}" "${BUILD_DIR}/reports/lint.rpt"
else
  cp "${BUILD_DIR}/logs/lint.log" "${BUILD_DIR}/reports/lint.rpt"
fi

exit "${spyglass_status}"
