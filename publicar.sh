#!/bin/bash
# Chequea si el sheet se movio. Si hay novedades:
#   - con remoto de git configurado: reconstruye y publica en GitHub Pages
#   - sin remoto: avisa por notificacion de macOS para actualizar a mano
# Cuando no hay cambios termina en una sola llamada y no toca nada.
set -uo pipefail
cd "$(dirname "$0")" || exit 1

LOG="$HOME/Library/Logs/radar-precios.log"
log(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }
avisar(){ /usr/bin/osascript -e "display notification \"$1\" with title \"Radar de Precios\" sound name \"Ping\"" >/dev/null 2>&1; }

salida=$(/usr/bin/python3 build.py --si-cambio 2>&1)
if [ $? -ne 0 ]; then
  log "ERROR build.py: $(echo "$salida" | tail -3 | tr '\n' ' ')"
  exit 1
fi

if echo "$salida" | grep -q '^SIN CAMBIOS'; then
  exit 0
fi

detalle=$(echo "$salida" | grep '^HAY CAMBIOS' | sed 's/^HAY CAMBIOS  //')
resumen=$(echo "$salida" | grep '^OK' | sed 's/^OK  //')

if ! git remote get-url origin >/dev/null 2>&1; then
  log "NOVEDADES (sin remoto, aviso solamente)  $detalle"
  avisar "Hay datos nuevos en el sheet. $detalle"
  exit 0
fi

cp dashboard.html docs/index.html
cp version.json docs/version.json
git add -A docs
if git diff --cached --quiet; then
  log "el sheet cambio pero el dashboard quedo igual, no publico"
  exit 0
fi

git commit -q -m "Actualiza dashboard: $detalle"
if git push -q origin main 2>>"$LOG"; then
  log "PUBLICADO  $resumen"
  avisar "Dashboard actualizado. $detalle"
else
  log "ERROR en git push"
  avisar "Hay datos nuevos pero fallo el push a GitHub."
  exit 1
fi
