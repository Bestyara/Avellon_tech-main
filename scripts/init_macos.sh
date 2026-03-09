#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Ошибка: не найден python3. Установите Python 3.8+ и повторите."
  exit 1
fi

VENV_DIR="${VENV_DIR:-venv}"
REQ_FILE="${REQ_FILE:-requirements.txt}"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

python3 -m pip install --upgrade pip setuptools wheel

if [[ -f "$REQ_FILE" ]]; then
  TMP_REQ="$(mktemp)"
  python3 - "$REQ_FILE" "$TMP_REQ" <<'PY'
import re
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])

skip = re.compile(r"^\s*sqlite3(\s*(==|>=|<=|~=).*)?\s*$", re.IGNORECASE)

out_lines = []
for raw in src.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if skip.match(line):
        continue
    out_lines.append(line)

dst.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
PY

  if [[ -s "$TMP_REQ" ]]; then
    python3 -m pip install -r "$TMP_REQ"
  else
    echo "requirements.txt найден, но после фильтрации он пуст — пропускаю установку зависимостей."
  fi
  rm -f "$TMP_REQ"
else
  echo "Не найден $REQ_FILE — пропускаю установку зависимостей."
fi

mkdir -p projects projects/test_1 save_data data __avellon_cache__

echo "Готово."
echo "Для запуска:"
echo "  ./scripts/run_macos.sh"
