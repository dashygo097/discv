#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"
source "${PROJECT_ROOT}/scripts/common/stage.sh"

require_var PROJECT_ENV
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
STAGE_TOOL=${LINT_TOOL:-none}
export STAGE_TOOL
stage_initialize
check_generated_environment

if [[ "${LINT_ENABLED}" != "1" ]]; then
  echo "ERROR: lint is disabled in Project.toml" 2>&1 | tee "${STAGE_LOG}"
  set +e
  stage_finalize 2
  set -e
  exit 2
fi

TOOL_RUNNER=${SCRIPT_DIR}/${LINT_TOOL}.sh
require_file "${TOOL_RUNNER}"

set +e
stage_run "${TOOL_RUNNER}"
tool_status=$?
stage_finalize "${tool_status}"
stage_status=$?
set -e

exit "${stage_status}"
