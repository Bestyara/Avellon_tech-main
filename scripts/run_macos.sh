#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-venv}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Не найдено виртуальное окружение: $VENV_DIR"
  echo "Сначала выполните:"
  echo "  ./scripts/init_macos.sh"
  exit 1
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

exec python3 Main.py
