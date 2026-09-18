#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"
source "${PROJECT_ROOT}/scripts/common/stage.sh"

require_var PROJECT_ENV
require_var LINT_TOOL
require_file "${PROJECT_ENV}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
configured=false
for tool in "${LINT_TOOLS[@]-}"; do
  if [[ "${tool}" == "${LINT_TOOL}" ]]; then
    configured=true
    break
  fi
done
if [[ "${configured}" != true ]]; then
  echo "ERROR: linter is not configured in Project.toml: ${LINT_TOOL}" >&2
  exit 2
fi

STAGE_TOOL=${LINT_TOOL}
export STAGE_TOOL
stage_initialize
check_generated_environment

TOOL_RUNNER=${SCRIPT_DIR}/${LINT_TOOL}.sh
require_file "${TOOL_RUNNER}"

set +e
stage_run "${TOOL_RUNNER}"
tool_status=$?
stage_finalize "${tool_status}"
stage_status=$?
set -e

exit "${stage_status}"
