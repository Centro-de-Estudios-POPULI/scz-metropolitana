# -*- coding: utf-8 -*-
"""
VALIDACIÓN DE EMIGRACIÓN Y MORTALIDAD — el bloque que no tenía contraste externo.
=================================================================================

★ POR QUÉ EXISTE ESTE ARCHIVO. `validar.py` divide todo por `n_viviendas` y
  `validar_persona.py` por la población: los dos asumen el universo de su motor.
  Los indicadores de este bloque tienen **denominador propio** —los EMIGRANTES,
  los FALLECIDOS— así que no entraban en ninguno de los dos y quedaron sin validar.
  Por ese hueco pasaron dos errores que se publicaron:
    · la emigración contaba TODO el stock declarado (500.914) cuando el INE
      publica sólo el flujo del período intercensal (329.047);
    · la tasa de mortalidad dividía el acumulado 2019-2024 por la población y
      daba 33,4 por mil contra una tasa bruta de ~7.
  Ninguno de los dos los agarra `chequeo.py`: son cifras perfectamente verosímiles.
  **Sólo el contraste contra el tabulado publicado los encuentra.**

★ LAS COLUMNAS SE PIDEN POR RUTA EXACTA, no por patrón. En `mortalidad/2` la
  ruta ('2024','2023','total') y ('2024','total','total') se distinguen sólo por
  el tramo del medio; buscar el patrón "total" devuelve las seis columnas de la
  hoja y compararía el año contra el acumulado.
"""
import pathlib, csv
import pandas as pd
import lector
from lector import norm

AQUI = pathlib.Path(__file__).parent
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

# (indicador, archivo, hoja, ruta del NUMERADOR, ruta del DENOMINADOR, años)
# `{a}` se reemplaza por el año: el INE pone los dos censos en la misma hoja.
# denominador None ⇒ el indicador es un CONTEO y se compara contra la columna tal cual.
CASOS = [
    ("emigrantes",         "emigracion_internacional", "2", ("{a}", "numero", "total"), None, (2024, 2012)),
    ("pct_emi_argentina",  "emigracion_internacional", "2", ("{a}", "numero", "argentina"),
                                                            ("{a}", "numero", "total"), (2024, 2012)),
    ("pct_emi_espana",     "emigracion_internacional", "2", ("{a}", "numero", "espana"),
                                                            ("{a}", "numero", "total"), (2024, 2012)),
    ("pct_emi_brasil",     "emigracion_internacional", "2", ("{a}", "numero", "brasil"),
                                                            ("{a}", "numero", "total"), (2024, 2012)),
    ("pct_emi_chile",      "emigracion_internacional", "2", ("{a}", "numero", "chile"),
                                                            ("{a}", "numero", "total"), (2024, 2012)),
    ("pct_emi_eeuu",       "emigracion_internacional", "2", ("{a}", "numero", "eeuu"),
                                                            ("{a}", "numero", "total"), (2024, 2012)),
    # ── mortalidad ──
    # ⚠️ Sólo 2024: el módulo MORTA de 2012 no trae año de fallecimiento (ver
    #    motor_otros.py), y la hoja del INE tampoco publica 2012 desagregado.
    ("fallecidos",      "mortalidad", "2", ("{a}", "total", "total"), None, (2024,)),
    ("fallecidos_2023", "mortalidad", "2", ("{a}", "2023", "total"),  None, (2024,)),
]


# ── PROMEDIOS: el INE publica el valor, no un conteo ─────────────────────────
# No son porcentajes ni conteos, así que tampoco entraban en ningún validador.
# Son los tres de `vivienda_hogar/15`, y salen de `municipal_*.csv`.
# ⚠️ `pers_x_vivienda` NO está acá porque es un duplicado exacto de `tam_hogar`
#    (misma regla): validarlo dos veces no agrega nada.
PROMEDIOS = [
    ("tam_hogar",         "vivienda_hogar", "15", ("{a}", "promedio de personas por hogar")),
    ("pers_x_dormitorio", "vivienda_hogar", "15", ("{a}", "promedio de personas por dormitorio")),
    ("pers_x_habitacion", "vivienda_hogar", "15", ("{a}", "promedio de personas por habitacion")),
]
TOL = 0.011          # el INE publica con 2 decimales


def col(h, ruta, a):
    """Índice de la columna cuya ruta es EXACTAMENTE la pedida."""
    return h.cols.get(tuple(norm(p.format(a=a)) for p in ruta))


sp = list(csv.DictReader(open(SPINE, encoding="utf-8")))
clave = {}
for r in sp:
    for nm in {norm(r["nombre_censo"]), norm(r["nombre"])}:
        clave[(norm(r["dpto"]), nm)] = r["cod_ine"]

res = {a: pd.read_csv(AQUI / f"otros_{a}.csv", index_col=0, dtype={0: str})
       for a in (2024, 2012)}
for a in res:
    res[a].index = res[a].index.astype(str).str.zfill(6)

print(f"{'indicador':<22}{'2024':>18}{'2012':>18}")
print("=" * 58)
resumen = {2024: [0, 0], 2012: [0, 0]}
detalle = []
for ind, arch, hoja, r_num, r_den, anios in CASOS:
    fila = f"{ind:<22}"
    for a in (2024, 2012):
        if a not in anios:
            fila += f"{'no publica':>18}"; continue
        h = lector.abrir(arch, hoja)
        c_num = col(h, r_num, a)
        c_den = col(h, r_den, a) if r_den else None
        if c_num is None or (r_den and c_den is None):
            fila += f"{'sin columna':>18}"; continue
        r = res[a]
        if ind not in r.columns:
            fila += f"{'sin calcular':>18}"; continue
        ok = tot = 0
        peor = None
        for k, f in h.filas.items():
            ci = clave.get(k)
            if ci is None or ci not in r.index or f[c_num] is None:
                continue
            v = r.at[ci, ind]
            if pd.isna(v):
                continue
            tot += 1
            n_ine = float(f[c_num])
            if r_den is None:
                n_mic = float(v)                      # conteo directo
            else:
                n_mic = round(v / 100 * r.at[ci, "emigrantes"])
                # el denominador tiene que cerrar TAMBIÉN: un porcentaje puede
                # coincidir por casualidad sobre un universo equivocado
                if abs(float(f[c_den]) - r.at[ci, "emigrantes"]) > 0.5:
                    continue
            if abs(n_mic - n_ine) <= 1:
                ok += 1
            elif peor is None or abs(n_mic - n_ine) > peor[1]:
                peor = (k[1], abs(n_mic - n_ine), n_mic, n_ine)
        resumen[a][0] += ok; resumen[a][1] += tot
        fila += f"{('✓' if ok == tot else '✗') + f' {ok}/{tot}':>18}"
        if peor:
            detalle.append((ind, a, peor))
    print(fila)

mun = {a: pd.read_csv(AQUI / f"municipal_{a}.csv", index_col=0, dtype={0: str})
       for a in (2024, 2012)}
for a in mun:
    mun[a].index = mun[a].index.astype(str).str.zfill(6)

for ind, arch, hoja, ruta in PROMEDIOS:
    fila = f"{ind:<22}"
    for a in (2024, 2012):
        h = lector.abrir(arch, hoja)
        j = col(h, ruta, a)
        if j is None or ind not in mun[a].columns:
            fila += f"{'sin columna':>18}"; continue
        ok = tot = 0; peor = None
        for k, f in h.filas.items():
            ci = clave.get(k)
            if ci is None or ci not in mun[a].index or f[j] is None:
                continue
            v = mun[a].at[ci, ind]
            if pd.isna(v):
                continue
            tot += 1
            dif = abs(float(f[j]) - v)
            if dif <= TOL:
                ok += 1
            elif peor is None or dif > peor[1]:
                peor = (k[1], dif, v, float(f[j]))
        resumen[a][0] += ok; resumen[a][1] += tot
        fila += f"{('✓' if ok == tot else '✗') + f' {ok}/{tot}':>18}"
        if peor:
            detalle.append((ind, a, peor))
    print(fila)

print("=" * 58)
for a in (2024, 2012):
    ok, tot = resumen[a]
    print(f"  {a}: {ok}/{tot} comparaciones municipio×indicador idénticas al registro"
          f"  ({100 * ok / tot if tot else 0:.1f}%)")
if detalle:
    print("\n  mayor divergencia por indicador:")
    for ind, a, (mun, d, mic, ine) in detalle:
        print(f"    {ind} ({a}) — {mun}: nuestro {mic:,.0f} vs INE {ine:,.0f}  (dif {d:,.0f})")
