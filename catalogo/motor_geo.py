# -*- coding: utf-8 -*-
"""
MOTOR GEOMÉTRICO — la superficie, que es lo único que no sale del censo.
=========================================================================

`densidad` estaba declarada en el catálogo desde el principio, con nivel
`mun+mz` y su nota puesta ("Única que no sale del censo: la superficie viene
del mapa maestro"), pero **ningún motor la calculaba**. Por eso el tablero no
tenía densidad en ninguno de los dos niveles: no era la regla de comparabilidad
—que es lo primero que uno sospecha—, era que el indicador no existía.

Este archivo la produce a nivel MUNICIPIO. La de manzana la calcula
`motor_manzana.py`, que ahí sí tiene la geometría del manzano al lado.

⚠️ LAS DOS DENSIDADES NO SON COMPARABLES ENTRE SÍ, y hay que decirlo donde se
   publiquen. La municipal divide por TODA la superficie del municipio —montes,
   chacos y ríos incluidos— y la de manzana divide por la superficie
   AMANZANADA, que no incluye calles ni vacíos. Pailón es el caso extremo: su
   densidad municipal es de las más bajas del país y la de sus manzanas se
   parece a la de cualquier pueblo. Miden cosas distintas y las dos son
   correctas; lo que no se puede es leerlas como una serie continua al bajar de
   nivel, que es justo lo que el resto de los indicadores sí permite.

    python motor_geo.py     ->  geo_2024.csv
"""
import pathlib
import pandas as pd

AQUI = pathlib.Path(__file__).parent
MAESTRO = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro"
                       r"\geo\municipios.geojson")
UTM20S = 32720          # metros, la proyección que usa el resto del proyecto


def main():
    import geopandas as gpd
    g = gpd.read_file(MAESTRO)
    if "cod_ine" not in g.columns:
        raise SystemExit("el mapa maestro no trae cod_ine")
    # ⚠️ Reproyectar ANTES de medir: un área calculada sobre grados no es una
    #    superficie. A esta latitud el error es de más del 10%.
    g["superficie_ha"] = g.to_crs(UTM20S).area / 1e4

    # ⚠️ La población NO está en `municipal_2024.csv` —ese es el motor de
    #    VIVIENDA— sino en `personas_2024.csv`, y ahí se llama `poblacion`;
    #    `alias.py` la traduce después a `pob_total`.
    pob = pd.read_csv(AQUI / "personas_2024.csv", dtype={0: str})
    pob = pob.rename(columns={pob.columns[0]: "cod_ine"})
    col = "poblacion"
    if col not in pob.columns:
        raise SystemExit(f"no encuentro la población: {list(pob.columns)[:12]}")

    d = (g[["cod_ine", "superficie_ha"]]
         .assign(cod_ine=lambda x: x.cod_ine.astype(str).str.zfill(6))
         .merge(pob[["cod_ine", col]].assign(
                    cod_ine=lambda x: x.cod_ine.astype(str).str.zfill(6)),
                on="cod_ine", how="inner"))
    d["densidad"] = d[col] / d.superficie_ha
    d = d[["cod_ine", "superficie_ha", "densidad"]]
    d.to_csv(AQUI / "geo_2024.csv", index=False, encoding="utf-8")

    print(f"{len(d)} municipios con superficie y densidad")
    print(f"  superficie total: {d.superficie_ha.sum()/100:,.0f} km²")
    print(f"  densidad mediana: {d.densidad.median():.2f} hab/ha")
    top = d.nlargest(5, "densidad")
    nom = g.set_index(g.cod_ine.astype(str).str.zfill(6)).nombre
    print("  las 5 más densas:")
    for _, r in top.iterrows():
        print(f"    {nom.get(r.cod_ine, r.cod_ine):<28} {r.densidad:8.2f} hab/ha")
    print("-> geo_2024.csv")


if __name__ == "__main__":
    main()
