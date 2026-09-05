#!/usr/bin/env python3
"""
Construye el dashboard de relevamiento de precios a partir del Google Sheet.
Descarga las 5 hojas, normaliza, calcula el analisis comparativo (misma logica
que Zapier) e inyecta los datos en dashboard.html.
"""
import csv, hashlib, io, json, re, sys, datetime, statistics, urllib.request, collections, os

SHEET_ID = "1-MwnygZ4vQ190jHYPsAZQzTH5QJ_Z0hujyfl4GaGICI"
HOJAS = ["HISTORICO_BAYER", "MAESTRO_HIBRIDOS", "MAESTRO_RV", "RELEVAMIENTOS_RV", "ANALISIS"]
BASE = os.path.dirname(os.path.abspath(__file__))


def bajar(hoja):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}"
    with urllib.request.urlopen(url, timeout=60) as r:
        txt = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(txt)))


def num(s):
    """Numeros del sheet: coma decimal, punto de miles, o formato ingles."""
    if s is None:
        return None
    s = str(s).strip().replace("%", "").replace("$", "").replace(" ", "")
    if not s or s.upper() in ("N/A", "NA", "-"):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fecha(s):
    if not s:
        return None
    s = str(s).strip().split(" ")[0]
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def zona_norm(z):
    """MAESTRO_RV guarda '1', el historico 'Zona 1'."""
    z = str(z or "").strip()
    if not z:
        return ""
    m = re.search(r"(\d+)", z)
    return f"Zona {m.group(1)}" if m else z


# ---------------------------------------------------------------- descarga
datos = {h: bajar(h) for h in HOJAS}

# Huella del contenido de las hojas. Con --si-cambio el script corta aca cuando
# el sheet no se movio, para no republicar el artifact al pedo.
HUELLA = os.path.join(BASE, ".huella")
crudo = json.dumps(datos, ensure_ascii=False, sort_keys=True).encode("utf-8")
huella = hashlib.sha256(crudo).hexdigest()
n_analisis = sum(1 for r in datos["ANALISIS"] if any((v or "").strip() for v in r.values()))
n_relev = sum(1 for r in datos["RELEVAMIENTOS_RV"] if (r.get("RV") or "").strip())

if "--si-cambio" in sys.argv:
    previa = ""
    if os.path.exists(HUELLA):
        previa = open(HUELLA, encoding="utf-8").read().split("\n")[0].strip()
    if previa == huella:
        print(f"SIN CAMBIOS  ANALISIS={n_analisis} filas  RELEVAMIENTOS_RV={n_relev} filas")
        sys.exit(0)
    print(f"HAY CAMBIOS  ANALISIS={n_analisis} filas  RELEVAMIENTOS_RV={n_relev} filas")

alertas = []

# ---------------------------------------------------------------- historico
hist = []
for r in datos["HISTORICO_BAYER"]:
    d, p, v = fecha(r.get("Fecha_Negocio")), num(r.get("Precio_Bolsa")), num(r.get("Volumen_Bolsas"))
    if not (d and p and v):
        continue
    hist.append(dict(d=d, region=r["Region"].strip(), zona=zona_norm(r["Zona_Venta"]),
                     marca=r["Marca"].strip(), hibrido=r["Hibrido"].strip(),
                     cond=r["Condicion_Venta"].strip(), p=p, v=v))
hist.sort(key=lambda r: r["d"])
HOY = datetime.date.today()
fin_hist = max(r["d"] for r in hist)
futuras = sum(1 for r in hist if r["d"] > HOY)
if futuras:
    alertas.append({
        "nivel": "warning",
        "titulo": f"{futuras} registros del historico tienen fecha posterior a hoy",
        "detalle": f"El historico llega hasta el {fin_hist.strftime('%d/%m/%Y')} y hoy es "
                   f"{HOY.strftime('%d/%m/%Y')}. Las ventanas de 30 dias se calculan contra la fecha "
                   f"de negocio de cada relevamiento, asi que el calculo es correcto, pero conviene "
                   f"revisar el anonimizado del historico antes de presentarlo."})

# ---------------------------------------------------------------- maestros
maestro_rv = {}
for r in datos["MAESTRO_RV"]:
    if not r.get("RV"):
        continue
    maestro_rv[r["RV"].strip()] = dict(email=(r.get("Email_RV") or "").strip().lower(),
                                       zona=zona_norm(r.get("Zona_Venta")))
maestro_hib = collections.defaultdict(list)
for r in datos["MAESTRO_HIBRIDOS"]:
    if r.get("Hibrido"):
        maestro_hib[r["Marca"].strip()].append(r["Hibrido"].strip())

# ---------------------------------------------------------------- relevamientos
relev = []
for r in datos["RELEVAMIENTOS_RV"]:
    d, p, v = fecha(r.get("Fecha_Negocio")), num(r.get("Precio_Bolsa")), num(r.get("Volumen_Bolsas"))
    if not (d and p):
        continue
    relev.append(dict(ts=(r.get("Fecha_Hora_Relevamiento") or "").strip(),
                      d=d, rv=r["RV"].strip(), email=(r.get("Email_RV") or "").strip().lower(),
                      region=r["Region"].strip(), zona=zona_norm(r["Zona_Venta"]),
                      marca=r["Marca"].strip(), hibrido=r["Hibrido"].strip(),
                      cond=r["Condicion_Venta"].strip(), p=p, v=v or 0))
relev.sort(key=lambda r: r["ts"])

# interpretaciones que ya escribio Zapier, indexadas por la clave del negocio
interp = {}
for r in datos["ANALISIS"]:
    txt = (r.get("Interpretacion_IA") or "").strip()
    if not txt:
        continue
    k = (fecha(r.get("Fecha_Negocio")), (r.get("Email_RV") or "").strip().lower(),
         (r.get("Hibrido") or "").strip(), num(r.get("Precio_Relevado")))
    interp[k] = txt

# ---------------------------------------------------------------- analisis comparativo
NIVELES = [
    ("region + zona + marca + hibrido + condicion", ("region", "zona", "marca", "hibrido", "cond")),
    ("region + marca + hibrido + condicion",        ("region", "marca", "hibrido", "cond")),
    ("marca + hibrido + condicion",                 ("marca", "hibrido", "cond")),
    ("hibrido",                                     ("hibrido",)),
]


def comparables(rel, claves, dias=30):
    desde = rel["d"] - datetime.timedelta(days=dias)
    return [h for h in hist if desde <= h["d"] <= rel["d"]
            and all(h[c] == rel[c] for c in claves)]


def senal(dif):
    if dif is None:
        return "sin_datos"
    a = abs(dif)
    return "alineado" if a <= 3 else ("atencion" if a <= 7 else "desvio")


RANGO_MIN, RANGO_MAX = 20, 1000
for rel in relev:
    rel["ok"] = RANGO_MIN <= rel["p"] <= RANGO_MAX
    rel["niveles"] = []
    if not rel["ok"]:
        rel.update(n_comp=0, criterio="precio fuera de rango", prom=None, prom_pond=None, med=None,
                   pmin=None, pmax=None, dif_prom=None, dif_med=None, pos=None,
                   niveles=[0, 0, 0, 0], senal="invalido", interp="")
        continue
    elegido = None
    for nombre, claves in NIVELES:
        c = comparables(rel, claves)
        rel["niveles"].append(len(c))
        if elegido is None and len(c) >= 1:
            elegido = (nombre, c)
    if elegido:
        nombre, c = elegido
        ps = sorted(x["p"] for x in c)
        vol = sum(x["v"] for x in c)
        prom_pond = sum(x["p"] * x["v"] for x in c) / vol if vol else statistics.fmean(ps)
        med = statistics.median(ps)
        rel.update(n_comp=len(c), criterio=nombre, prom=statistics.fmean(ps),
                   prom_pond=prom_pond, med=med, pmin=ps[0], pmax=ps[-1],
                   dif_prom=(rel["p"] / statistics.fmean(ps) - 1) * 100,
                   dif_med=(rel["p"] / med - 1) * 100,
                   pos=None if ps[-1] == ps[0] else (rel["p"] - ps[0]) / (ps[-1] - ps[0]) * 100)
    else:
        rel.update(n_comp=0, criterio="sin comparables", prom=None, prom_pond=None, med=None,
                   pmin=None, pmax=None, dif_prom=None, dif_med=None, pos=None)
    rel["senal"] = senal(rel.get("dif_med"))
    rel["interp"] = interp.get((rel["d"], rel["email"], rel["hibrido"], rel["p"]), "")

# ---------------------------------------------------------------- control de calidad
outliers = [r for r in relev if not r["ok"]]
if outliers:
    alertas.append({"nivel": "critical",
                    "titulo": f"{len(outliers)} relevamiento(s) con precio fuera de rango",
                    "detalle": "El formulario acepta cualquier numero: hay cargas de "
                               + ", ".join(f"US$ {r['p']:,.0f} ({r['rv']}, {r['hibrido']})" for r in outliers)
                               + f". El historico se mueve entre US$ {min(h['p'] for h in hist):.0f} y "
                                 f"US$ {max(h['p'] for h in hist):.0f} por bolsa. El dashboard los deja "
                                 "fuera de todos los calculos y los marca en la tabla, pero conviene "
                                 "validar el rango en el formulario de V0 antes de escribir en el sheet."})

emails_mal = sorted({(r["rv"], r["email"]) for r in relev
                     if r["rv"] in maestro_rv and r["email"] != maestro_rv[r["rv"]]["email"]})
if emails_mal:
    alertas.append({"nivel": "warning", "titulo": "Emails que no coinciden con el maestro de RV",
                    "detalle": "; ".join(f"{rv} carga con {em} y en MAESTRO_RV figura "
                                         f"{maestro_rv[rv]['email']}" for rv, em in emails_mal)
                               + ". El mail automatico puede terminar en la casilla equivocada."})

fuera_maestro = sorted({r["rv"] for r in relev if r["rv"] not in maestro_rv})
if fuera_maestro:
    alertas.append({"nivel": "warning", "titulo": "RV que cargan y no estan en el maestro",
                    "detalle": ", ".join(fuera_maestro) + "."})

zonas_raw = {str(r.get("Zona_Venta", "")).strip() for r in datos["MAESTRO_RV"] if r.get("RV")}
if any(z.isdigit() for z in zonas_raw):
    alertas.append({"nivel": "warning", "titulo": "MAESTRO_RV guarda la zona como numero suelto",
                    "detalle": "El historico y los relevamientos usan 'Zona 4' y el maestro guarda '4'. "
                               "Un BUSCARV directo entre las dos hojas falla; el dashboard lo normaliza, "
                               "pero conviene unificarlo en el sheet."})

sin_analisis = len(relev) - len(interp)
if sin_analisis > 0:
    alertas.append({"nivel": "warning",
                    "titulo": f"{sin_analisis} de {len(relev)} relevamientos sin interpretacion de IA",
                    "detalle": "La hoja ANALISIS solo tiene texto para "
                               f"{len(interp)} negocio(s) y repite filas. El dashboard recalcula el "
                               "comparativo por su cuenta, asi que no depende de que Zapier haya corrido."})

pobres = sum(1 for r in relev if r["ok"] and r["niveles"][0] <= 1)
if pobres:
    alertas.append({"nivel": "serious",
                    "titulo": f"{pobres} de {sum(1 for r in relev if r['ok'])} relevamientos validos tienen 1 "
                              "comparable o ninguno "
                              "con el criterio estricto",
                    "detalle": "Cruzar region + zona + marca + hibrido + condicion a 30 dias deja "
                               "muestras de 0 o 1 antecedente, y sobre eso el desvio no significa nada. "
                               "El dashboard aplica una cascada: si el criterio estricto no llega a un "
                               "comparable, afloja zona, despues region y por ultimo condicion."})

# ---------------------------------------------------------------- salida
def dia(x):
    return x.isoformat()

payload = {
    "meta": {
        "generado": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "generado_iso": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "hoy": dia(HOY),
        "sheet": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
        "hist_desde": dia(min(r["d"] for r in hist)),
        "hist_hasta": dia(fin_hist),
        "n_hist": len(hist), "n_relev": len(relev),
        "n_rv": len(maestro_rv), "n_hibridos": sum(len(v) for v in maestro_hib.values()),
    },
    "hist": [[dia(r["d"]), r["region"], r["zona"], r["marca"], r["hibrido"], r["cond"],
              round(r["p"], 2), int(r["v"])] for r in hist],
    "relev": [{"ts": r["ts"], "d": dia(r["d"]), "rv": r["rv"], "zona": r["zona"],
               "region": r["region"], "marca": r["marca"], "hibrido": r["hibrido"],
               "cond": r["cond"], "p": r["p"], "v": r["v"], "n": r["n_comp"],
               "criterio": r["criterio"], "med": r["med"], "prom": r["prom"],
               "pmin": r["pmin"], "pmax": r["pmax"], "dif": r["dif_med"],
               "pos": r["pos"], "senal": r["senal"], "interp": r["interp"], "ok": r["ok"],
               "niveles": r["niveles"]} for r in relev],
    "rvs": [{"rv": k, "zona": v["zona"], "email": v["email"]} for k, v in maestro_rv.items()],
    "maestro_hib": {k: sorted(v) for k, v in maestro_hib.items()},
    "alertas": alertas,
}

with open(os.path.join(BASE, "template.html"), encoding="utf-8") as f:
    html = f.read()
html = html.replace("/*__DATOS__*/null", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
with open(os.path.join(BASE, "dashboard.html"), "w", encoding="utf-8") as f:
    f.write(html)

# Archivo chico que la pagina consulta cada pocos minutos para saber si hay
# novedades. Lleva la cantidad de relevamientos y los ultimos cargados, asi la
# campanita puede decir que llego y no solo que "algo cambio".
ultimos = [{"rv": r["rv"], "marca": r["marca"], "hibrido": r["hibrido"],
            "p": r["p"], "d": dia(r["d"])} for r in reversed(relev[-6:])]
with open(os.path.join(BASE, "version.json"), "w", encoding="utf-8") as f:
    json.dump({"generado": payload["meta"]["generado_iso"],
               "n_relev": len(relev), "ultimos": ultimos}, f, ensure_ascii=False)

with open(HUELLA, "w", encoding="utf-8") as f:
    f.write(huella + "\n" + datetime.datetime.now().isoformat(timespec="seconds") + "\n")

print(f"OK  historico={len(hist)}  relevamientos={len(relev)}  alertas={len(alertas)}")
for a in alertas:
    print(f"  [{a['nivel']}] {a['titulo']}")
