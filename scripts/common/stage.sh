#!/usr/bin/env bash

# Stage lifecycle library. Source this file from a stage runner.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "ERROR: source scripts/common/stage.sh; do not execute it" >&2
  exit 2
fi

stage_initialize() {
  require_var PROJECT_ROOT
  require_var PROJECT_ENV
  require_var CONFIG_MANIFEST
  require_var STAGE_NAME
  require_var STAGE_TOOL
  require_var STAGE_BUILD_DIR
  require_var PYTHON
  require_cmd date
  require_cmd tee
  require_file "${PROJECT_ENV}"
  require_file "${CONFIG_MANIFEST}"
  require_file "${PROJECT_ROOT}/scripts/common/write_run_manifest.py"

  STAGE_LOG_DIR=${STAGE_BUILD_DIR}/logs
  STAGE_REPORT_DIR=${STAGE_BUILD_DIR}/reports
  STAGE_RESULT_DIR=${STAGE_BUILD_DIR}/results
  STAGE_WORK_DIR=${STAGE_BUILD_DIR}/work
  STAGE_LOG=${STAGE_LOG_DIR}/run.log
  STAGE_REPORT=${STAGE_REPORT_DIR}/summary.rpt
  STAGE_MANIFEST=${STAGE_BUILD_DIR}/run.json
  STAGE_STAMP=${STAGE_BUILD_DIR}/.done
  STAGE_START_EPOCH=$(date +%s)

  case "${STAGE_BUILD_DIR}" in
    "${PROJECT_ROOT}"/build/*) ;;
    *)
      echo "ERROR: stage build directory is outside the project build directory: ${STAGE_BUILD_DIR}" >&2
      return 1
      ;;
  esac

  rm -rf \
    "${STAGE_LOG_DIR}" \
    "${STAGE_REPORT_DIR}" \
    "${STAGE_RESULT_DIR}" \
    "${STAGE_WORK_DIR}"
  rm -f "${STAGE_MANIFEST}" "${STAGE_STAMP}"
  mkdir -p \
    "${STAGE_LOG_DIR}" \
    "${STAGE_REPORT_DIR}" \
    "${STAGE_RESULT_DIR}" \
    "${STAGE_WORK_DIR}"
  export STAGE_LOG_DIR STAGE_REPORT_DIR STAGE_RESULT_DIR STAGE_WORK_DIR
  export STAGE_LOG STAGE_REPORT STAGE_MANIFEST STAGE_STAMP
}

stage_run() {
  "$@" 2>&1 | tee "${STAGE_LOG}"
  return "${PIPESTATUS[0]}"
}

stage_finalize() {
  local stage_status="$1"
  local manifest_status
  local stage_end_epoch

  stage_end_epoch=$(date +%s)
  if [[ ! -f "${STAGE_REPORT}" && -f "${STAGE_LOG}" ]]; then
    cp "${STAGE_LOG}" "${STAGE_REPORT}"
  fi

  if "${PYTHON}" "${PROJECT_ROOT}/scripts/common/write_run_manifest.py" \
      --stage "${STAGE_NAME}" \
      --tool "${STAGE_TOOL}" \
      --exit-code "${stage_status}" \
      --started "${STAGE_START_EPOCH}" \
      --finished "${stage_end_epoch}" \
      --configuration-digest "${PROJECT_CONFIG_DIGEST}" \
      --project-manifest "${CONFIG_MANIFEST}" \
      --stage-build-dir "${STAGE_BUILD_DIR}" \
      --output "${STAGE_MANIFEST}"; then
    manifest_status=0
  else
    manifest_status=$?
  fi

  if [[ "${manifest_status}" -ne 0 ]]; then
    rm -f "${STAGE_STAMP}"
    return "${manifest_status}"
  fi
  if [[ "${stage_status}" -eq 0 ]]; then
    printf '%s\n' "${PROJECT_CONFIG_DIGEST}" >"${STAGE_STAMP}"
  fi
  return "${stage_status}"
}
