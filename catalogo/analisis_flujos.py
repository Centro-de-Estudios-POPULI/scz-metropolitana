# -*- coding: utf-8 -*-
"""
LOS FLUJOS DE LA REGIÓN METROPOLITANA, CRUZADOS CON QUIÉN ES LA GENTE.
=======================================================================

El motor de flujos produce las matrices O-D; acá se les pega el PERFIL de las
personas, que es lo que convierte un número en una explicación.

★ SON TRES FENÓMENOS DISTINTOS Y NO SE MEZCLAN. Llamarlos a todos "migración"
  es el error de fondo que este archivo evita:

   1. ORIGEN DE TODA LA VIDA   `mun_nac`      → un STOCK: de dónde salió la gente
                                                 que hoy vive acá. No tiene fecha.
   2. MIGRACIÓN RECIENTE       `mun_res5`     → un FLUJO fechado: 2019 → 2024.
                                                 Es la que responde "qué está
                                                 pasando ahora".
   3. CONMUTACIÓN DIARIA       `mun_trabaja`  → NO ES MIGRACIÓN. La persona no se
                                                 mudó: se mueve todos los días.

★ CADA UNO TIENE SU UNIVERSO, Y SE DECLARA:
   · origen        = todos los residentes enumerados
   · reciente      = residentes de 5 años o más que declararon dónde vivían
                     (los menores de 5 NO existían en 2019: incluirlos inventa
                      "no migrantes" y diluye la tasa)
   · conmutación   = ocupados que declararon municipio de trabajo, SIN corte de
                     edad — el indicador `autocontencion_laboral` del tablero
                     corta en 14, así que sus porcentajes NO son intercambiables.
                     Ver la nota de `armar_flujos_web.py`.

★ LAS DECLARACIONES PARCIALES NO SE TIRAN. "Departamento sin municipio" (`XX9999`)
  y "provincia sin municipio" (`XXYY99`) son códigos válidos del INE: se clasifican
  por su departamento, que es lo que sí declararon. Descartarlas sesga a favor de
  los orígenes bien declarados.

    python analisis_flujos.py
"""
import json, pathlib
import numpy as np
import pandas as pd

AQUI = pathlib.Path(__file__).parent
RAIZ = AQUI.parent
PARQ = pathlib.Path(r"C:\Users\HP\cpv2024\persona_full.parquet")
DICC = pathlib.Path(r"C:\Users\HP\cpv2024\diccionario.json")
SALIDA = RAIZ / "web" / "datos" / "flujos_perfil.json"

COLS = ["cod_ine", "mun_nac", "mun_res5", "mun_trabaja", "residente", "edad",
        "mujer", "anios_estudio", "nivel", "ocupado", "ocu1d", "rama", "catocu",
        "indigena", "nac_exterior"]

# grandes grupos de edad, para leer la estructura sin 20 barras
EDADES = [(0, 14, "0-14"), (15, 24, "15-24"), (25, 39, "25-39"),
          (40, 64, "40-64"), (65, 200, "65+")]


def clasificar(cod, n9, dep_reg="07"):
    """De dónde viene, en las 5 categorías que importan para leer la región."""
    if not cod or len(cod) != 6:
        return "sd"
    if cod in n9:
        return "region"
    if cod[:2] == dep_reg:
        return "scz"          # resto del departamento (incluye `079999`)
    return "otro_dep"


def perfil(g, etiquetas):
    """El retrato de un grupo de personas. Mismo molde para todos los grupos,
    porque comparar exige que las columnas signifiquen lo mismo."""
    n = len(g)
    if n == 0:
        return None
    ocu = g[g.ocupado.astype(bool)]
    a15 = g[g.edad >= 15]
    o = {
        "n": int(n),
        "pct_mujer": round(100 * g.mujer.mean(), 1),
        "edad_mediana": round(float(g.edad.median()), 1),
        "pct_indigena": round(100 * g.indigena.mean(), 1),
        "edades": {et: round(100 * ((g.edad >= a) & (g.edad <= b)).mean(), 1)
                   for a, b, et in EDADES},
    }
    if len(a15):
        o["anios_estudio"] = round(float(a15.anios_estudio.mean()), 2)
        # `nivel` trae 4 categorías y nada más: ninguno / primaria / secundaria /
        # superior (medido, no supuesto: inventar "postgrado" habría dado 0% sin fallar)
        o["pct_superior"] = round(100 * (a15.nivel == "superior").mean(), 1)
    if len(ocu):
        o["pct_ocupado"] = round(100 * len(ocu) / max(len(a15), 1), 1)
        o["rama"] = {etiquetas["rama"].get(str(int(k)), str(k)): round(100 * v, 1)
                     for k, v in ocu.rama.value_counts(normalize=True).items()
                     if v >= .005}
        o["ocu"] = {etiquetas["ocu"].get(str(int(k)), str(k)): round(100 * v, 1)
                    for k, v in ocu.ocu1d.value_counts(normalize=True).items()
                    if v >= .005}
    return o


def main():
    muns = json.loads((RAIZ / "datos" / "municipios.json").read_text(encoding="utf-8"))
    n9 = {m["cod_ine"]: m["nombre"] for m in muns}
    orden = sorted(n9, key=lambda c: n9[c])
    dic = json.loads(DICC.read_text(encoding="utf-8"))["PERSONA"]
    etiquetas = {"rama": dic["act_eco_2d_13"]["categorias"],
                 "ocu": dic["ocu_1d_13"]["categorias"]}

    d = pd.read_parquet(PARQ, columns=COLS)
    d["cod_ine"] = d.cod_ine.astype(str)
    for c in ("mun_nac", "mun_res5", "mun_trabaja"):
        d[c] = d[c].astype(str)
    r = d[d.cod_ine.isin(n9)].copy()
    print(f"residentes enumerados en los 9: {len(r):,}")

    # ── de dónde salió cada quien ────────────────────────────────────────────
    r["o_nac"] = np.where(r.nac_exterior.astype(bool), "exterior",
                          [clasificar(c, n9) for c in r.mun_nac])
    r.loc[r.mun_nac.isin(r.cod_ine) & (r.mun_nac == r.cod_ine), "o_nac"] = "aqui"
    r["o_res5"] = [clasificar(c, n9) for c in r.mun_res5]
    r.loc[(r.mun_res5 == r.cod_ine) & (r.mun_res5 != ""), "o_res5"] = "aqui"
    # "nació en la región" no debe tapar "nació en ESTE municipio"
    r.loc[(r.mun_nac == r.cod_ine) & (r.mun_nac != ""), "o_nac"] = "aqui"

    salida = {
        "municipios": [{"cod_ine": c, "nombre": n9[c]} for c in orden],
        "etiquetas": etiquetas,
        "origen": {}, "reciente": {}, "perfil": {}, "conmuta": {},
        "region": {},
    }

    # ── 1. ORIGEN DE TODA LA VIDA (stock) ────────────────────────────────────
    for c in orden:
        g = r[r.cod_ine == c]
        v = g.o_nac.value_counts()
        salida["origen"][c] = {k: int(v.get(k, 0)) for k in
                               ("aqui", "region", "scz", "otro_dep", "exterior", "sd")}
        salida["origen"][c]["total"] = int(len(g))

    # ── 2. MIGRACIÓN RECIENTE 2019→2024 ──────────────────────────────────────
    # universo: 5 años o más QUE DECLARARON. Los menores de 5 no existían.
    base5 = r[(r.edad >= 5) & (r.o_res5 != "sd")]
    print(f"universo de migración reciente (5+ que declararon): {len(base5):,}")
    # los que SALIERON de cada uno de los 9 hacia otro de los 9 se leen desde
    # el resto del país: hay que mirar a TODO el microdato, no sólo a la región
    d["o5"] = d.mun_res5
    fuera = d[(d.edad >= 5) & d.o5.isin(n9) & (~d.cod_ine.isin(n9))]
    for c in orden:
        g = base5[base5.cod_ine == c]
        v = g.o_res5.value_counts()
        entra = {k: int(v.get(k, 0)) for k in ("region", "scz", "otro_dep", "exterior")}
        # salidas: quienes hace 5 años vivían en `c` y hoy viven en otro lado
        sal_reg = int(((base5.mun_res5 == c) & (base5.cod_ine != c)).sum())
        sal_pais = int((fuera.o5 == c).sum())
        salida["reciente"][c] = {
            **entra,
            "quedo": int(v.get("aqui", 0)),
            "entran": sum(entra.values()),
            "salen_region": sal_reg, "salen_pais": sal_pais,
            "salen": sal_reg + sal_pais,
            "universo": int(len(g)),
        }
        salida["reciente"][c]["neto"] = (salida["reciente"][c]["entran"]
                                         - salida["reciente"][c]["salen"])
        # matriz interna 9×9 de la migración reciente
        salida["reciente"][c]["desde"] = {
            o: int(((base5.cod_ine == c) & (base5.mun_res5 == o)).sum()) for o in orden}

    # ── 3. PERFIL: quien llegó hace poco vs quien ya estaba ──────────────────
    for c in orden:
        g = base5[base5.cod_ine == c]
        salida["perfil"][c] = {
            "llegados": perfil(g[g.o_res5 != "aqui"], etiquetas),
            "estaban": perfil(g[g.o_res5 == "aqui"], etiquetas),
        }
    salida["region"]["llegados"] = perfil(base5[base5.o_res5.isin(
        ["scz", "otro_dep", "exterior"])], etiquetas)
    salida["region"]["estaban"] = perfil(base5[base5.o_res5 == "aqui"], etiquetas)
    salida["region"]["universo5"] = int(len(base5))
    salida["region"]["poblacion"] = int(len(r))

    # ── 4. CONMUTACIÓN: quién se mueve y a qué RAMA entra ───────────────────
    ocu = r[r.ocupado.astype(bool) & r.mun_trabaja.str.len().eq(6)]
    print(f"ocupados con municipio de trabajo declarado: {len(ocu):,}")
    for c in orden:
        vive = ocu[ocu.cod_ine == c]
        sale = vive[vive.mun_trabaja != c]
        entra = ocu[(ocu.mun_trabaja == c) & (ocu.cod_ine != c)]
        salida["conmuta"][c] = {
            "ocupados": int(len(vive)),
            "se_queda": int((vive.mun_trabaja == c).sum()),
            "sale": int(len(sale)),
            "entra": int(len(entra)),
            "perfil_sale": perfil(sale, etiquetas),
            "perfil_queda": perfil(vive[vive.mun_trabaja == c], etiquetas),
            "perfil_entra": perfil(entra, etiquetas),
        }
    salida["region"]["conmutan"] = perfil(ocu[ocu.mun_trabaja != ocu.cod_ine], etiquetas)
    salida["region"]["no_conmutan"] = perfil(ocu[ocu.mun_trabaja == ocu.cod_ine], etiquetas)

    SALIDA.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {SALIDA.name}  {SALIDA.stat().st_size/1024:.0f} KB")

    # ── lo que hay que poder contar en una frase ────────────────────────────
    print("\nSALDO MIGRATORIO RECIENTE (2019→2024)")
    for c in sorted(orden, key=lambda x: -salida["reciente"][x]["neto"]):
        v = salida["reciente"][c]
        print(f"  {n9[c][:23]:24}{v['neto']:>+9,}   entran {v['entran']:>7,}  "
              f"salen {v['salen']:>7,}   ({100*v['entran']/v['universo']:.1f}% de su población 5+)")


if __name__ == "__main__":
    main()
