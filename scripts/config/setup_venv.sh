#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/../.." && pwd)
source "${PROJECT_ROOT}/scripts/common/check_env.sh"

PYTHON_BIN=${PYTHON_BIN:-python3}
VENV_DIR=${PROJECT_VENV_DIR:-${PROJECT_ROOT}/build/.venv}
REQUIREMENTS=${SCRIPT_DIR}/requirements.txt

require_python_version "${PYTHON_BIN}" 3 6
require_file "${REQUIREMENTS}"

if [[ -e "${VENV_DIR}" && ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "ERROR: path exists but is not a Python virtual environment: ${VENV_DIR}" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "[VENV] Creating ${VENV_DIR}"
  mkdir -p "$(dirname "${VENV_DIR}")"
  if ! "${PYTHON_BIN}" -m venv "${VENV_DIR}"; then
    echo "ERROR: failed to create the virtual environment" >&2
    echo "Install the venv module for ${PYTHON_BIN}, or install virtualenv." >&2
    exit 1
  fi
else
  echo "[VENV] Reusing ${VENV_DIR}"
fi

VENV_PYTHON=${VENV_DIR}/bin/python

if ! "${VENV_PYTHON}" -m pip --version >/dev/null 2>&1; then
  echo "[VENV] Installing pip with ensurepip"
  "${VENV_PYTHON}" -m ensurepip
fi

echo "[VENV] Installing ${REQUIREMENTS}"
"${VENV_PYTHON}" -m pip install \
  --disable-pip-version-check \
  --requirement "${REQUIREMENTS}"

echo "[VENV] Ready"
echo "[VENV] Python: $("${VENV_PYTHON}" --version 2>&1)"
echo "[VENV] Path: ${VENV_DIR}"
