# Refresco del dashboard de precios

**Artifact publicado:** https://claude.ai/code/artifact/16bdc66d-d84a-4496-a8ad-7cf9087c5d02
**Sheet de origen:** https://docs.google.com/spreadsheets/d/1-MwnygZ4vQ190jHYPsAZQzTH5QJ_Z0hujyfl4GaGICI/edit

## Cómo se actualiza

    python3 /Users/martintornimbeni/claude/dashboard-precios/build.py

`build.py` baja las 5 hojas del sheet (gviz CSV, no necesita credenciales porque
el sheet es público), normaliza, recalcula el comparativo y reescribe
`dashboard.html` a partir de `template.html`.

Después se republica con la herramienta Artifact, **pasando la URL de arriba como
`url`** para que conserve el mismo link:

    Artifact(file_path="/Users/martintornimbeni/claude/dashboard-precios/dashboard.html",
             url="https://claude.ai/code/artifact/16bdc66d-d84a-4496-a8ad-7cf9087c5d02")

Antes de republicar hay que leer el artifact (`action:"read"` con esa `url`),
porque una publicación sobre un artifact que la sesión no leyó se rechaza.

## Archivos

- `build.py` — descarga + cálculo. Acá se tocan los umbrales y las alertas.
- `template.html` — el dashboard. Contiene el placeholder `/*__DATOS__*/null`
  que `build.py` reemplaza por el JSON de datos.
- `dashboard.html` — generado. **No editar a mano**, se pisa en cada corrida.

## Umbrales que se pueden ajustar (en `build.py`)

- `RANGO_MIN`, `RANGO_MAX` (20 / 1000 US$ por bolsa): fuera de eso el
  relevamiento se marca inválido y no entra en ningún cálculo.
- `senal()`: en línea hasta 3% de desvío, atención hasta 7%, desvío arriba de 7%.
- `NIVELES`: la cascada de criterios de comparación, del más estricto al más laxo.
