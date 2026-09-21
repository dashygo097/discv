#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

require_var PROJECT_ENV
require_var SIM_CONFIG_CMAKE
require_var SIM_MODEL_DIR
require_file "${PROJECT_ENV}"
require_file "${SIM_CONFIG_CMAKE}"
require_cmd cmake

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
configured=false
for tool in "${SIM_TOOLS[@]-}"; do
  if [[ "${tool}" == "verilator" ]]; then
    configured=true
    break
  fi
done
if [[ "${configured}" != true ]]; then
  echo "ERROR: [flow.sim.verilator] is not configured in Project.toml" >&2
  exit 2
fi

cmake \
  -S "${PROJECT_ROOT}/sims" \
  -B "${SIM_MODEL_DIR}" \
  -DPROJECT_CONFIG_CMAKE="${SIM_CONFIG_CMAKE}" \
  -DOBJCACHE_ENABLED=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "${SIM_MODEL_DIR}" --parallel "${BUILD_JOBS}"
