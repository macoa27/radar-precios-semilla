#!/bin/bash
# Instala el vigilante que revisa el sheet cada 2 minutos y publica cuando cambia.
# El plist tiene que vivir en ~/Library/LaunchAgents: si se carga desde otra
# carpeta funciona hasta el proximo reinicio y despues launchd no lo levanta.
set -euo pipefail
cd "$(dirname "$0")"

ETIQUETA="com.martintornimbeni.radar-precios"
DESTINO="$HOME/Library/LaunchAgents/$ETIQUETA.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$ETIQUETA.plist" "$DESTINO"
launchctl bootout "gui/$(id -u)/$ETIQUETA" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DESTINO"

if launchctl list | grep -q "$ETIQUETA"; then
  echo "Vigilante instalado y corriendo. Sobrevive a reinicios."
  echo "Log: ~/Library/Logs/radar-precios.log"
  echo "Para sacarlo:  launchctl bootout gui/\$(id -u)/$ETIQUETA && rm \"$DESTINO\""
else
  echo "No quedo cargado. Revisa ~/Library/Logs/radar-precios.err" >&2
  exit 1
fi
