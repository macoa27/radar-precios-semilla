# Radar de Precios de Semilla

Dashboard de gestión del relevamiento de precios de semilla de maíz. Lee el Google
Sheet del sistema, recalcula el comparativo contra el histórico de mercado y genera
una página estática.

**Fuente:** [Google Sheet del relevamiento](https://docs.google.com/spreadsheets/d/1-MwnygZ4vQ190jHYPsAZQzTH5QJ_Z0hujyfl4GaGICI/edit)
· hojas `HISTORICO_BAYER`, `MAESTRO_HIBRIDOS`, `MAESTRO_RV`, `RELEVAMIENTOS_RV`, `ANALISIS`.

## Qué muestra

- **KPIs** — precio de mercado ponderado por volumen, con variación contra el período
  previo y contra el mismo período del año anterior; dispersión, volumen, actividad
  del equipo y relevamientos fuera de línea.
- **Cómo se movió el precio** — media móvil de 7 días con banda P25–P75 y los
  relevamientos del equipo superpuestos.
- **Este año contra el anterior** — variación mes a mes contra el mismo mes del año previo.
- **Cuánto se mueve cada híbrido** — mín/P25/mediana/P75/máx por híbrido, ordenado por
  dispersión. Es la vara para saber si un desvío es señal o ruido.
- **Precio por marca** y **qué se paga por financiar** (brecha contado/financiado).
- **Mapa de calor por zona**, conmutable entre marca e híbrido.
- **Actividad del equipo** y **últimos relevamientos** con la interpretación de la IA.
- **Chequeos de calidad** sobre el sheet, recalculados en cada corrida.

Filtros de región, marca, condición, ventana (7 d a todo el histórico) y una fecha de
corte para pararse en cualquier día de la serie.

## Uso

    python3 build.py              # baja el sheet y reconstruye dashboard.html
    python3 build.py --si-cambio  # igual, pero corta si el sheet no se movió

No necesita credenciales ni dependencias: sólo la librería estándar de Python 3
(probado en 3.9 y 3.14). El sheet se lee por el endpoint público `gviz/tq?tqx=out:csv`.

`publicar.sh` encadena todo: si el sheet cambió y hay remoto de git configurado,
reconstruye y publica en GitHub Pages; si no hay remoto, avisa con una notificación
de macOS para actualizar a mano. Cuando no hay cambios termina en silencio.

Para que corra sola cada 2 minutos:

    launchctl load -w "$PWD/com.martintornimbeni.radar-precios.plist"

El log queda en `~/Library/Logs/radar-precios.log`.

## Archivos

| Archivo | Qué es |
|---|---|
| `build.py` | Descarga, normalización, cálculo del comparativo y chequeos de calidad. |
| `template.html` | El dashboard. Contiene el placeholder `/*__DATOS__*/null` que `build.py` reemplaza por el JSON. |
| `docs/index.html` | Lo que sirve GitHub Pages. Se regenera; no editar a mano. |
| `publicar.sh` | Detección de cambios + publicación o aviso. |
| `com.martintornimbeni.radar-precios.plist` | Agente de launchd que corre `publicar.sh`. |

`dashboard.html` y `.huella` no se versionan: son salida del build.

## Cómo compara un relevamiento

Igual que el flujo de Zapier: mismo híbrido, misma región, zona y condición, dentro de
los 30 días previos a la fecha de negocio. Si eso no devuelve ni un antecedente, afloja
el criterio en cascada — sale de la zona, después de la región y por último compara sólo
por híbrido. La columna **Comp.** dice cuántos antecedentes entraron y el tooltip con
qué criterio.

Umbrales ajustables en `build.py`:

- `RANGO_MIN` / `RANGO_MAX` (20 / 1000 US$ por bolsa): fuera de ese rango el relevamiento
  se marca inválido y no entra en ningún cálculo.
- `senal()`: en línea hasta 3% de desvío, atención hasta 7%, desvío por encima de 7%.
- `NIVELES`: la cascada de criterios, del más estricto al más laxo.

## Publicar en GitHub Pages

    gh auth login --web --git-protocol https
    gh repo create radar-precios-semilla --public --source=. --remote=origin --push
    gh api -X POST repos/:owner/radar-precios-semilla/pages -f build_type=legacy \
      -f 'source[branch]=main' -f 'source[path]=/docs'

La URL queda en `https://<usuario>.github.io/radar-precios-semilla/`. A partir de ahí
`publicar.sh` la actualiza solo cada vez que el sheet cambia.
