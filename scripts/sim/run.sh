#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=${PROJECT_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}
source "${PROJECT_ROOT}/scripts/common/check_env.sh"
source "${PROJECT_ROOT}/scripts/common/stage.sh"

require_var PROJECT_ENV
require_var SIM_EXECUTABLE
require_file "${PROJECT_ENV}"
require_file "${SIM_EXECUTABLE}"

# shellcheck source=/dev/null
source "${PROJECT_ENV}"
if [[ "${SIM_TOOL_COUNT}" -ne 1 || "${SIM_TOOLS[0]}" != "verilator" ]]; then
  echo "ERROR: sim currently requires exactly [flow.sim.verilator]" >&2
  exit 2
fi

PROGRAM=${PROGRAM:-}
if [[ -z "${PROGRAM}" ]]; then
  echo "ERROR: PROGRAM is required; run make sim-run PROGRAM=path/to/program.bin" >&2
  exit 2
fi
require_file "${PROGRAM}"
PROGRAM=$(cd "$(dirname "${PROGRAM}")" && pwd)/$(basename "${PROGRAM}")

SIM_ARGS=${SIM_ARGS:-}
sim_args=()
if [[ -n "${SIM_ARGS}" ]]; then
  read -r -a sim_args <<<"${SIM_ARGS}"
fi

STAGE_TOOL=verilator
export STAGE_TOOL
stage_initialize
check_generated_environment

command=(
  "${SIM_EXECUTABLE}"
  --cycles "${SIM_MAX_CYCLES}"
  --reset-cycles "${SIM_RESET_CYCLES}"
)
if [[ "${SIM_TRACE}" == true ]]; then
  command+=(--trace)
fi
if (( ${#sim_args[@]} > 0 )); then
  command+=("${sim_args[@]}")
fi
command+=("${PROGRAM}")

cd "${STAGE_WORK_DIR}"
set +e
stage_run "${command[@]}"
tool_status=$?
stage_finalize "${tool_status}"
stage_status=$?
set -e

exit "${stage_status}"
