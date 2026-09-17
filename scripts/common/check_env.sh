#!/usr/bin/env bash

# This file is a function library and must be sourced by stage scripts.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "ERROR: source scripts/common/check_env.sh; do not execute it" >&2
  exit 2
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1" >&2
    return 1
  fi
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "ERROR: required environment variable not set: ${name}" >&2
    return 1
  fi
}

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "ERROR: required file not found: $1" >&2
    return 1
  fi
}

require_dir() {
  if [[ ! -d "$1" ]]; then
    echo "ERROR: required directory not found: $1" >&2
    return 1
  fi
}

require_python_version() {
  local python_bin="$1"
  local major="$2"
  local minor="$3"

  require_cmd "${python_bin}" || return 1
  if ! "${python_bin}" -c \
    "import sys; raise SystemExit(sys.version_info < (${major}, ${minor}))"; then
    echo "ERROR: ${python_bin} ${major}.${minor} or newer is required" >&2
    "${python_bin}" --version >&2 || true
    return 1
  fi
}

check_generated_environment() {
  local command_name
  local variable_name

  for command_name in "${PROJECT_REQUIRED_COMMANDS[@]-}"; do
    [[ -n "${command_name}" ]] && require_cmd "${command_name}"
  done
  for variable_name in "${PROJECT_REQUIRED_VARIABLES[@]-}"; do
    [[ -n "${variable_name}" ]] && require_var "${variable_name}"
  done
  return 0
}
