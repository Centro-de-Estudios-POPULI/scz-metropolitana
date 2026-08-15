# -*- coding: utf-8 -*-
"""
AGREGACIÓN CORRECTA: el denominador de cada indicador viaja al Atlas.
======================================================================

El Atlas agregaba **todo ponderando por población**, pero cada indicador tiene su
propio universo. Un porcentaje de VIVIENDAS ponderado por PERSONAS le da más peso
a los municipios con hogares grandes:

    pct_agua_caneria nacional 2024
      INE publica                71,19%   (2.579.821 de 3.623.711 viviendas)
      ponderado por población    72,27%   ← lo que hacía el Atlas
      ponderado por viviendas    71,19%   ← exacto
      promedio simple            54,50%

Los valores municipales estaban bien —salen del motor validado—; lo que estaba mal
era la cuenta que hacía el navegador al subir a departamento o país.

★ TRES CASOS, no uno. El catálogo declara cuál aplica en el campo `agg`:

  · **"peso"** (la mayoría) — promedio ponderado por SU denominador, que se
    nombra en `den`. Son 21 denominadores distintos para 214 indicadores, así que
    viajan como un diccionario aparte y no uno por indicador.

  · **"razon"** — cociente de dos totales (índice de masculinidad, razón de
    dependencia, tasa de mortalidad). El agregado correcto suma numerador y
    denominador y recién ahí divide; promediar los cocientes municipales da otra
    cosa.

  · **"no"** — NO SE PUEDE AGREGAR desde lo municipal. La mediana nacional no es
    función de las medianas municipales: `edad_mediana` ponderada da 27,57 contra
    los 26 que publica el INE, y no hay ponderación que lo arregle. Sólo sale del
    microdato, así que se sirve precalculada.
"""
import json, pathlib
import pandas as pd
from alias import ALIAS, ATLAS, renombrar

AQUI = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos"
                    r"\Observatorio de Presupuesto Fiscal Departamental\_github_atlas_fiscal")
FUENTES = ["municipal", "personas", "nbi", "otros", "flujos_municipal"]

# ── denominadores que el motor NO emite como `_den_` porque divide directo ───
POR_BLOQUE = {"municipal": "viviendas", "nbi": "poblacion_nbi",
              "flujos_municipal": "trabajan_en_su_municipio"}

# ── cocientes de dos totales: se recalculan, no se promedian ─────────────────
RAZONES = {"indice_masculinidad": ("pob_hombres", "pob_mujeres"),
           "razon_dependencia": None, "dep_juvenil": None, "dep_senil": None,
           "indice_envejecimiento": None, "indice_juventud": None,
           "tasa_mortalidad": None, "emigrantes_x1000": None}

# ── no agregables desde lo municipal ─────────────────────────────────────────
NO_AGREGABLES = {"edad_mediana"}

# ── CONTEOS: el agregado es la SUMA de los municipios ────────────────────────
# ⚠️ 2026-08-15. El frontend decidía esto solo, mirando la UNIDAD: `hab`, `viv` y
#    `pers` ⇒ sumar. Pero **`pers` es ambigua**: vale "personas" (un conteo) y
#    también "personas por hogar" (una razón). Resultado visible en la pantalla
#    de entrada del Atlas: **"Personas por hogar: 1.049,2"** — la suma de los 343
#    promedios municipales. Igual `pers_x_vivienda` (1.049) y `pers_x_dormitorio`
#    (723). Es el mismo error de fondo que en `armar_metro.py`: inferir la
#    naturaleza del indicador de su unidad en vez de declararla.
#    ⇒ acá se declara `agg:"suma"` y el frontend ya no adivina.
SUMAS = {"pob_total", "pob_hombres", "pob_mujeres", "viviendas", "hogares",
         "poblacion_nbi", "emigrantes", "fallecidos",
         "inmigrantes_5a", "emigrantes_internos_5a", "saldo_migratorio",
         "inmigrantes_vida", "emigrantes_internos_vida", "saldo_migratorio_vida",
         "entran_a_trabajar", "salen_a_trabajar", "poblacion_flotante",
         "trabajan_en_su_municipio"}
# unidades que PARECEN conteo; toda clave con una de éstas que no esté declarada
# arriba se avisa al cerrar, para que no vuelva a pasar en silencio
UNI_CONTEO = {"hab", "viv", "pers"}

# ── brechas: se rearman desde sus componentes, que el motor ahora emite ──────
BRECHAS = {"brecha_alfabetismo", "brecha_edu_superior", "brecha_anios_estudio",
           "brecha_participacion"}


def cargar(anio):
    partes = {}
    for f in FUENTES:
        p = AQUI / f"{f}_{anio}.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p, index_col=0, dtype={0: str})
        d.index = d.index.astype(str).str.zfill(6)
        partes[f] = d
    return partes


def main():
    partes = cargar(2024)
    # ── denominador de cada indicador, en vocabulario del catálogo ──
    den_de, series = {}, {}
    for f, d in partes.items():
        base = POR_BLOQUE.get(f)
        for c in d.columns:
            if c.startswith("_den_"):
                continue
            k = ALIAS.get(c, c)
            col = "_den_" + c
            if col in d.columns:
                nombre = f"den_{k}"
                # reutilizar si un denominador idéntico ya existe
                firma = tuple(d[col].fillna(-1).astype("int64"))
                prev = next((n for n, s in series.items() if s == firma), None)
                if prev:
                    den_de[k] = prev
                else:
                    series[nombre] = firma
                    den_de[k] = nombre
            elif base:
                den_de[k] = base
    # las series concretas, ya deduplicadas
    dens = {}
    for f, d in partes.items():
        for c in d.columns:
            if c.startswith("_den_"):
                k = ALIAS.get(c[5:], c[5:])
                n = den_de.get(k)
                if n and n.startswith("den_") and n not in dens:
                    dens[n] = d[c]
    m = renombrar(partes["municipal"]).rename(columns={"n_viviendas": "viviendas"})
    dens["viviendas"] = m["viviendas"]
    if "nbi" in partes:
        dens["poblacion_nbi"] = partes["nbi"].get("poblacion_nbi")
    per = renombrar(partes["personas"])
    dens["poblacion"] = per["pob_total"] if "pob_total" in per else per["poblacion"]
    # el universo de los flujos: quienes declararon dónde trabajan
    if "flujos_municipal" in partes:
        fl = partes["flujos_municipal"]
        if "trabajan_en_su_municipio" in fl:
            dens["trabajan_en_su_municipio"] = (fl["trabajan_en_su_municipio"]
                                                + fl.get("salen_a_trabajar", 0))
    # ⚠️ ninguna referencia colgada: un `den` declarado que no viaje deja al
    #    frontend cayendo silenciosamente a población, que es el bug original
    faltan = {v for v in den_de.values()} - set(dens)
    if faltan:
        print(f"  ⚠️ denominadores declarados sin serie: {sorted(faltan)}")

    print(f"denominadores distintos: {len(dens)}")
    print(f"indicadores con denominador asignado: {len(den_de)}")

    # ── anotar el catálogo ──
    cat = json.loads((REPO / "catalogo.json").read_text(encoding="utf-8"))
    n = {"peso": 0, "razon": 0, "no": 0, "sin": 0, "suma": 0}
    dudosos = []
    for g in cat["grupos"]:
        for i in g["indicadores"]:
            k = i["key"]
            if i.get("unit") in UNI_CONTEO and k not in SUMAS:
                dudosos.append(k)
            if k in SUMAS:
                i["agg"] = "suma"; i.pop("den", None); n["suma"] += 1
            elif k in BRECHAS:
                i["agg"] = "brecha"
                i["comp"] = [k + "_muj", k + "_hom"]
                n.setdefault("brecha", 0); n["brecha"] += 1
            elif k in NO_AGREGABLES:
                i["agg"] = "no"; n["no"] += 1
            elif k in RAZONES:
                i["agg"] = "razon"; n["razon"] += 1
            elif k in den_de or ATLAS.get(k) in den_de:
                # ★ los alias del Atlas (`pct_gas_natural` = `pct_gas_red`)
                #   heredan el denominador de su gemelo: el motor no los conoce
                #   por ese nombre, pero es el MISMO indicador
                i["agg"] = "peso"
                i["den"] = den_de.get(k) or den_de[ATLAS[k]]
                n["peso"] += 1
            else:
                i["agg"] = "peso"; i["den"] = "poblacion"; n["sin"] += 1
    print(f"  ponderados: {n['peso']} · razones: {n['razon']} · sumas: {n['suma']} · "
          f"brechas: {n.get('brecha', 0)} · no agregables: {n['no']}")
    print(f"  sin denominador propio (caen a población): {n['sin']}")
    if dudosos:
        print(f"  ⚠️ unidad de conteo pero NO declarados como suma "
              f"(se agregan ponderando, verificar): {', '.join(sorted(dudosos))}")

    idx = sorted(dens)
    payload = {ci: [None if pd.isna(dens[c].get(ci)) else int(dens[c].get(ci, 0))
                    for c in idx] for ci in m.index}
    (REPO.parent / "denominadores.json").write_text(
        json.dumps({"orden": idx, "municipios": payload}, ensure_ascii=False),
        encoding="utf-8")
    (REPO.parent / "catalogo_agg.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    print("-> denominadores.json · catalogo_agg.json")
    return dens, den_de, cat


if __name__ == "__main__":
    main()
