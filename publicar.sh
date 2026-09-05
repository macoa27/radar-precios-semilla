#!/bin/bash
# Reconstruye el dashboard y lo publica en GitHub Pages, pero solo si el sheet
# se movio. Pensado para correr cada pocos minutos desde launchd: cuando no hay
# filas nuevas termina en una sola llamada HTTP y no toca el repo.
set -uo pipefail
cd "$(dirname "$0")" || exit 1

LOG="$HOME/Library/Logs/radar-precios.log"
log(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }

salida=$(/usr/bin/python3 build.py --si-cambio 2>&1)
estado=$?

if [ $estado -ne 0 ]; then
  log "ERROR build.py: $(echo "$salida" | tail -3 | tr '\n' ' ')"
  exit 1
fi

if echo "$salida" | grep -q '^SIN CAMBIOS'; then
  exit 0
fi

cp dashboard.html docs/index.html
git add -A docs
if git diff --cached --quiet; then
  log "el sheet cambio pero el dashboard quedo igual, no publico"
  exit 0
fi

git commit -q -m "Actualiza dashboard: $(echo "$salida" | grep '^HAY CAMBIOS')"
if git push -q origin main 2>>"$LOG"; then
  log "PUBLICADO  $(echo "$salida" | grep '^OK')"
else
  log "ERROR en git push"
  exit 1
fi
