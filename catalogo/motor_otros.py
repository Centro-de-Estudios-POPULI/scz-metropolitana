# -*- coding: utf-8 -*-
"""
EMIGRACIÓN INTERNACIONAL Y MORTALIDAD — los dos archivos chicos del censo.
===========================================================================

2024: `Emigracion_CPV-2024.csv` (8 columnas) y `Mortalidad_CPV-2024.csv` (10).
2012: las entidades `EMIGRA` y `MORTA` del Redatam.

Ambos son listas de EVENTOS (una fila por emigrante / por fallecido), no de
personas, así que las tasas se calculan contra la población del municipio, que
viene de los motores de personas.
"""
import pathlib, sys, numpy as np, pandas as pd

AQUI = pathlib.Path(__file__).parent
CPV24 = pathlib.Path(r"C:\Users\HP\cpv2024")
CPV12 = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones"
                     r"\upre-nbi\datos\crudo\CPV2012 343M\baser")
sys.path.insert(0, r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones\upre-nbi\scripts")

# ISO 3166-1 numérico, que es lo que usa el censo en `pais_destino_cod`
PAISES = {"argentina": 32, "brasil": 76, "chile": 152, "espana": 724, "eeuu": 840}


def _2024():
    e = pd.read_csv(CPV24 / "Emigracion_CPV-2024.csv", sep=";", dtype=str, encoding="latin-1")
    e["cod_ine"] = e.idep.str.zfill(2) + e.iprov.str.zfill(2) + e.imun.str.zfill(2)
    # ⚠️ Mismo recorte que en 2012 (que sí lo tenía) y por el mismo motivo: los
    #    códigos de "no aplica" / "sin especificar" son números grandes y entran
    #    al promedio. Sin esto la edad media de emigración daba 128,9 años de
    #    mediana nacional y hasta 660,8 en un municipio.
    e["edad"] = pd.to_numeric(e.e205_edad, errors="coerce").where(lambda x: x <= 110)
    e["pais"] = pd.to_numeric(e.pais_destino_cod, errors="coerce")
    m = pd.read_csv(CPV24 / "Mortalidad_CPV-2024.csv", sep=";", dtype=str, encoding="latin-1")
    m["cod_ine"] = m.idep.str.zfill(2) + m.iprov.str.zfill(2) + m.imun.str.zfill(2)
    m["edad"] = pd.to_numeric(m.m213_edad, errors="coerce").where(lambda x: x <= 110)
    m["covid"] = pd.to_numeric(m.m214_cov, errors="coerce") == 1
    # ★★ EL MÓDULO DE MORTALIDAD NO CUBRE UN AÑO: cubre 2019-2024.
    #    Distribución real: 2019 56.408 · 2020 77.750 · 2021 78.869 ·
    #    2022 65.032 · 2023 73.756 · 2024 17.344 (parcial) · 9999 13.572.
    #    Dividir los 382.731 por la población daba **33,4 por mil**, contra una
    #    tasa bruta de Bolivia de ~7. La tasa anual se calcula con el ÚLTIMO AÑO
    #    COMPLETO antes del censo: 2023 ⇒ 73.756/11.365.333 = 6,5 por mil, que sí
    #    es del orden correcto.
    m["anio"] = pd.to_numeric(m.m212b_an, errors="coerce")
    return e, m


def _2012():
    from redatam import RedatamDB
    db = RedatamDB(str(CPV12))
    cods = db.codigos_municipio()
    def marco(ent, mapa):
        idx = db.municipio_de(ent)
        d = pd.DataFrame({"cod_ine": pd.Categorical.from_codes(idx, cods).astype(str)})
        for destino, var in mapa.items():
            clave = f"{ent}:{var}"
            d[destino] = pd.Series(db.leer(clave)) if clave in db.vars else np.nan
        return d
    print("  variables EMIGRA:", sorted({k.split(":")[1] for k in db.vars if k.startswith("EMIGRA:")}))
    print("  variables MORTA :", sorted({k.split(":")[1] for k in db.vars if k.startswith("MORTA:")}))
    return db, marco


if __name__ == "__main__":
    pob = {a: pd.read_csv(AQUI / f"personas_{a}.csv", index_col=0, dtype={0: str}).poblacion
           for a in (2024, 2012)}
    for a in pob:
        pob[a].index = pob[a].index.astype(str).str.zfill(6)

    print("2024 …")
    e, m = _2024()
    print(f"  emigrantes {len(e):,} · fallecidos {len(m):,}")
    top = e.pais.value_counts().head(6)
    print(f"  destinos más frecuentes (código ISO): {dict(top)}")
    out = {}
    ge, gm = e.groupby("cod_ine"), m.groupby("cod_ine")
    out["emigrantes"] = ge.size()
    out["edad_prom_emigracion"] = ge.edad.mean()
    for n, c in PAISES.items():
        out["pct_emi_" + n] = 100 * e[e.pais == c].groupby("cod_ine").size() / ge.size()
    out["fallecidos"] = gm.size()
    out["edad_prom_fallecimiento"] = gm.edad.mean()
    out["pct_muertes_covid"] = 100 * m[m.covid].groupby("cod_ine").size() / gm.size()
    # fallecidos del último año completo: es el numerador de la tasa anual
    AREF = 2023
    out["fallecidos_" + str(AREF)] = m[m.anio == AREF].groupby("cod_ine").size()
    d24 = pd.DataFrame(out)
    d24["emigrantes_x1000"] = 1000 * d24.emigrantes / pob[2024]
    # ⚠️ `fallecidos` es el ACUMULADO 2019-2024 del módulo, NO un año. La tasa
    #    se calcula con el año de referencia; publicar el acumulado como tasa
    #    anual daba 33,4 por mil (ver _2024 arriba).
    d24["tasa_mortalidad"] = 1000 * d24["fallecidos_" + str(AREF)] / pob[2024]
    d24.index.name = "cod_ine"
    d24.to_csv(AQUI / "otros_2024.csv", encoding="utf-8")
    print(f"  → otros_2024.csv · {len(d24)} municipios · "
          f"{d24.emigrantes.sum():,.0f} emigrantes · {d24.fallecidos.sum():,.0f} fallecidos")

    print("2012 …")
    from redatam import RedatamDB
    db = RedatamDB(str(CPV12))
    cods = db.codigos_municipio()
    et = db.vars["EMIGRA:P20J"]["etiquetas"]
    # el país de 2012 NO usa ISO: trae su propia lista con etiquetas, así que se
    # emparejan por NOMBRE y no por número (el mismo criterio de siempre)
    def cod_pais(nombre):
        for k, v in et.items():
            n = v.lower()
            if nombre in n: return k
        return None
    equiv = {"argentina": "argentin", "brasil": "brasil", "chile": "chile",
             "espana": "espa", "eeuu": "estados unidos"}
    codigos12 = {k: cod_pais(v) for k, v in equiv.items()}
    print(f"  códigos de país en 2012: {codigos12}")

    ie = db.municipio_de("EMIGRA")
    im = db.municipio_de("MORTA")
    de = pd.DataFrame({"cod_ine": pd.Categorical.from_codes(ie, cods).astype(str),
                       "edad": pd.Series(db.leer("EMIGRA:P20G")).where(lambda x: x <= 110),
                       "pais": pd.Series(db.leer("EMIGRA:P20J"))})
    dm = pd.DataFrame({"cod_ine": pd.Categorical.from_codes(im, cods).astype(str),
                       "edad": pd.Series(db.leer("MORTA:P21E")).where(lambda x: x <= 110)})
    o = {}
    g1, g2 = de.groupby("cod_ine"), dm.groupby("cod_ine")
    o["emigrantes"] = g1.size()
    o["edad_prom_emigracion"] = g1.edad.mean()
    for n, c in codigos12.items():
        if c is not None:
            o["pct_emi_" + n] = 100 * de[de.pais == c].groupby("cod_ine").size() / g1.size()
    o["fallecidos"] = g2.size()
    o["edad_prom_fallecimiento"] = g2.edad.mean()
    d12 = pd.DataFrame(o)
    d12["emigrantes_x1000"] = 1000 * d12.emigrantes / pob[2012]
    # ⛔ 2012 NO PUEDE dar tasa de mortalidad, y va VACÍA a propósito.
    #    El módulo MORTA de 2012 trae SÓLO tres variables —edad (P21E), sexo
    #    (P21F) y causa (P21G)—: **no hay año de fallecimiento**, así que el
    #    período lo define la pregunta y sin el cuestionario no se conoce el
    #    divisor. Los 135.112 fallecidos sobre la población dan 13,9 por mil
    #    contra una tasa bruta de referencia de ~7,5: es un acumulado de varios
    #    años, no una tasa anual.
    #    ⚠️ Y aunque se adivinara el divisor, la SERIE seguiría siendo inválida:
    #    2024 se calcula con el último año completo (2023, vía `m212b_an`) y esto
    #    es un acumulado. Comparar los dos sería comparar cosas distintas.
    d12["tasa_mortalidad"] = np.nan
    d12.index.name = "cod_ine"
    d12.to_csv(AQUI / "otros_2012.csv", encoding="utf-8")
    print(f"  -> otros_2012.csv · {len(d12)} municipios · "
          f"{d12.emigrantes.sum():,.0f} emigrantes · {d12.fallecidos.sum():,.0f} fallecidos")
