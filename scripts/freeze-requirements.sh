#!/usr/bin/env bash
# ==============================================================================
# scripts/freeze-requirements.sh - Pin Backend Requirements in a Clean Env
# ==============================================================================
# Creates an isolated Python 3.12 virtualenv with full network access to PyPI,
# installs backend/requirements.txt, and generates backend/requirements.lock.txt.
#
# Requirements:
# - Python 3.12 installed on host
# - Active internet connectivity to PyPI (https://pypi.org)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

VENV_DIR="${ROOT_DIR}/.venv-freeze"
LOCK_FILE="${ROOT_DIR}/backend/requirements.lock.txt"

echo "======================================================================"
echo "MOD-SA Dependency Pinning"
echo "Creating isolated Python 3.12 virtual environment at ${VENV_DIR}..."
echo "======================================================================"

rm -rf "${VENV_DIR}"
python3.12 -m venv "${VENV_DIR}" || python3 -m venv "${VENV_DIR}"

# Determine activate script path
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    source "${VENV_DIR}/bin/activate"
elif [[ -f "${VENV_DIR}/Scripts/activate" ]]; then
    source "${VENV_DIR}/Scripts/activate"
else
    echo "ERROR: Unable to locate virtualenv activate script." >&2
    exit 1
fi

echo "Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

echo "Installing backend/requirements.txt..."
pip install -r "${ROOT_DIR}/backend/requirements.txt"

echo "Generating ${LOCK_FILE} via pip freeze..."
pip freeze > "${LOCK_FILE}"

echo "======================================================================"
echo "Successfully generated ${LOCK_FILE}!"
echo "Resolved key package versions:"
grep -E '^(chromadb|langchain|fastapi|uvicorn|pydantic)==' "${LOCK_FILE}" || true
echo "======================================================================"

echo "Cleaning up temporary freeze virtualenv..."
deactivate || true
rm -rf "${VENV_DIR}"
