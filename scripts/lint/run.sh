#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var PROJECT_ROOT
require_var FILELIST
require_var PROJECT_ENV
require_var BUILD_DIR
require_file "${FILELIST}"
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
check_generated_environment

if [[ "${LINT_ENABLED}" != "1" ]]; then
  echo "ERROR: lint is disabled in Project.toml" >&2
  exit 1
fi

require_cmd "${LINT_TOOL}"
mkdir -p "${BUILD_DIR}/logs" "${BUILD_DIR}/reports" "${BUILD_DIR}/work"

case "${LINT_TOOL}" in
  sg|sg_shell|spyglass)
    ;;
  verilator)
    if [[ "${LINT_OPTION_COUNT}" -eq 0 ]]; then
      "${LINT_TOOL}" \
        --lint-only \
        --top-module "${RTL_TOP}" \
        --Mdir "${BUILD_DIR}/work" \
        -f "${FILELIST}" \
        2>&1 | tee "${BUILD_DIR}/logs/lint.log"
    else
      "${LINT_TOOL}" \
        --lint-only \
        --top-module "${RTL_TOP}" \
        --Mdir "${BUILD_DIR}/work" \
        "${LINT_OPTIONS[@]}" \
        -f "${FILELIST}" \
        2>&1 | tee "${BUILD_DIR}/logs/lint.log"
    fi
    ;;
  *)
    echo "ERROR: unsupported lint tool: ${LINT_TOOL}" >&2
    exit 1
    ;;
esac

cp "${BUILD_DIR}/logs/lint.log" "${BUILD_DIR}/reports/lint.rpt"
