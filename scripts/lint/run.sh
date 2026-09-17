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

mkdir -p "${BUILD_DIR}/logs" "${BUILD_DIR}/reports" "${BUILD_DIR}/work"

TOOL_RUNNER=${SCRIPT_DIR}/${LINT_TOOL}.sh
require_file "${TOOL_RUNNER}"

exec "${TOOL_RUNNER}"
