#!/usr/bin/env bash
# Atalho para Linux e macOS. Entrega o trabalho para executar.py.
cd "$(dirname "$0")" || exit 1
for p in python3 python; do
  if command -v "$p" >/dev/null 2>&1; then exec "$p" executar.py "$@"; fi
done
echo
echo " Python 3 nao foi encontrado neste computador."
echo " No Ubuntu ou Debian: sudo apt install python3 python3-venv"
echo " No macOS:            brew install python"
echo
exit 1
