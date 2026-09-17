#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var PROJECT_ROOT
require_var PROJECT_CONFIG
require_var PROJECT_CONFIG_SCRIPT
require_var GENERATED_DIR
require_var PYTHON
require_dir "${PROJECT_ROOT}"
require_file "${PROJECT_CONFIG}"
require_file "${PROJECT_CONFIG_SCRIPT}"
require_python_version "${PYTHON}" 3 6

exec "${PYTHON}" "${PROJECT_CONFIG_SCRIPT}" generate \
  "${PROJECT_CONFIG}" \
  --project-root "${PROJECT_ROOT}" \
  --output "${GENERATED_DIR}"
