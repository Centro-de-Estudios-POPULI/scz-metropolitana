# -*- coding: utf-8 -*-
"""
GENERADOR DEL `data.json` DEL ATLAS SOCIOECONÓMICO MUNICIPAL.
==============================================================

El Atlas publicado se armó con `extraer_microdatos_v2.py`, que tenía **mal el
denominador** (metía viviendas vacías) en 44 de 47 indicadores de vivienda. Al
comparar sus 136 indicadores contra este motor, **98 de 126 comparables diferían**,
con errores sistemáticos de hasta **+21,4 pp en electricidad**, +16,4 en celular,
+14,9 en cocina exclusiva. Este script lo regenera desde los motores validados.

★ TRES VOCABULARIOS, no dos. El motor emite `poblacion`, el catálogo declara
  `pob_total` y el Atlas publica `pct_gas_natural` donde nosotros decimos
  `pct_gas_red`. La traducción va en dos pasos: `alias.renombrar` (motor →
  catálogo) y `alias.ATLAS` (atlas → catálogo, que acá se usa al revés).
  Sin el segundo, 6 indicadores del Atlas parecerían "no calculados" y el
  reemplazo sería una regresión.

★ LA CLAVE DEL JSON ES EL CÓDIGO SIGEP, no el INE: así lo indexa el HTML del
  Atlas (`CENSO[f.properties.sigep]`). El `cod_ine` viaja dentro de cada registro.

ALCANCE DE ESTA ETAPA: se reemplazan los VALORES de los indicadores que el Atlas
ya publica, sin tocar la interfaz. La serie 2012↔2024 —que el motor ya tiene y el
Atlas no— es una etapa aparte porque exige trabajo de UI.

    python generar_atlas.py            # escribe data_nuevo.json y compara
"""
import pathlib, json, csv
import pandas as pd, numpy as np
from alias import renombrar, ATLAS

AQUI = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos"
                    r"\Observatorio de Presupuesto Fiscal Departamental\_github_atlas_fiscal")
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")
FUENTES = ["municipal", "personas", "nbi", "otros", "flujos_municipal"]


def cargar(anio):
    d = None
    for f in FUENTES:
        p = AQUI / f"{f}_{anio}.csv"
        if not p.exists():
            print(f"  (falta {p.name})")
            continue
        x = pd.read_csv(p, index_col=0, dtype={0: str})
        x.index = x.index.astype(str).str.zfill(6)
        x = x.drop(columns=[c for c in x.columns if c.startswith("_den_")])
        x = renombrar(x).rename(columns={"n_viviendas": "viviendas"})
        d = x if d is None else d.join(x[[c for c in x.columns if c not in d.columns]],
                                       how="outer")
    return d


def main():
    mio = cargar(2024)
    sp = {r["cod_ine"]: r for r in csv.DictReader(open(SPINE, encoding="utf-8"))}
    viejo = json.load(open(REPO / "data.json", encoding="utf-8"))
    cat = json.load(open(REPO / "catalogo.json", encoding="utf-8"))
    # ★ El Atlas ya no se limita a sus 136 originales: publica TODO lo que el
    #   motor calcula. Los 136 viejos conservan su clave (para no romper enlaces
    #   ni el `dir` de la rampa de color) y el resto se agrega con la clave del
    #   catálogo del motor, agrupado por su categoría declarada.
    viejos = [i["key"] for g in cat["grupos"] for i in g["indicadores"]]
    inds = list(viejos)
    equiv = {ATLAS.get(k, k) for k in viejos}       # sus claves, en vocabulario del catálogo
    decl = {i["k"]: i for i in json.loads(
        (AQUI / "catalogo.json").read_text(encoding="utf-8"))["indicadores"]}
    nuevos_k = [c for c in mio.columns if c not in equiv and c in decl]
    inds += sorted(nuevos_k)
    print(f"indicadores: {len(viejos)} del Atlas + {len(nuevos_k)} nuevos = {len(inds)}")

    nuevo, faltan, hechos = {}, set(), set()
    for sigep, reg in viejo.items():
        ci = str(reg["cod_ine"]).zfill(6)
        fila = {"cod_ine": ci,
                "nombre": sp.get(ci, {}).get("nombre", reg.get("nombre")),
                "dpto": sp.get(ci, {}).get("dpto", reg.get("dpto"))}
        for k in inds:
            col = ATLAS.get(k, k)          # traducción atlas -> catálogo
            if col in mio.columns and ci in mio.index:
                v = mio.at[ci, col]
                if pd.notna(v):
                    # los porcentajes con un decimal, como el Atlas actual
                    fila[k] = round(float(v), 1 if str(k).startswith("pct_") or
                                    str(k).startswith("tasa_") else 3)
                    hechos.add(k)
                    continue
            faltan.add(k)
        nuevo[sigep] = fila

    (REPO.parent / "data_nuevo.json").write_text(
        json.dumps(nuevo, ensure_ascii=False), encoding="utf-8")

    # ── catálogo ampliado: los grupos viejos intactos + los nuevos por categoría
    #    declarada en el catálogo del motor, que ya trae etiqueta, unidad y `dir`
    grupos = [dict(g) for g in cat["grupos"]]
    porcat = {}
    for k in nuevos_k:
        i = decl[k]
        porcat.setdefault(i["g"], []).append(
            {"key": k, "label": i["l"], "unit": i["u"], "dir": i.get("d", 0),
             "desc": i.get("nota") or i["l"]})
    idx = {g["label"]: g for g in grupos}
    for g, items in sorted(porcat.items()):
        if g in idx:
            idx[g]["indicadores"] = idx[g]["indicadores"] + items
        else:
            grupos.append({"key": g.lower().replace(" ", "_"), "label": g,
                           "indicadores": items})
    (REPO.parent / "catalogo_nuevo.json").write_text(
        json.dumps({"grupos": grupos}, ensure_ascii=False), encoding="utf-8")
    tot = sum(len(g["indicadores"]) for g in grupos)
    print(f"catálogo ampliado: {len(grupos)} grupos · {tot} indicadores")

    print(f"municipios: {len(nuevo)} · indicadores del Atlas: {len(inds)}")
    print(f"  cubiertos por el motor : {len(hechos)}")
    print(f"  sin cubrir             : {sorted(set(inds) - hechos)}")

    # ── cuánto se mueve cada indicador, que es lo que hay que poder explicar ──
    A = pd.DataFrame(viejo).T
    B = pd.DataFrame(nuevo).T
    filas = []
    for k in sorted(hechos):
        a = pd.to_numeric(A[k], errors="coerce") if k in A.columns else None
        if a is None:
            continue
        b = pd.to_numeric(B[k], errors="coerce")
        j = pd.concat([a, b], axis=1, keys=["viejo", "nuevo"]).dropna()
        if len(j) < 300:
            continue
        d = j["nuevo"] - j["viejo"]
        filas.append((k, d.median(), d.abs().max(), (d.abs() < 0.05).mean() * 100))
    r = pd.DataFrame(filas, columns=["ind", "dif_mediana", "max_abs", "pct_iguales"])
    r.to_csv(AQUI / "atlas_cambios.csv", index=False, encoding="utf-8")
    print(f"\nindicadores que NO se mueven: {(r.pct_iguales > 99).sum()} de {len(r)}")
    print("\nLOS 15 QUE MÁS CAMBIAN (nuevo − viejo)")
    print("=" * 52)
    for _, x in r.reindex(r.dif_mediana.abs().sort_values(ascending=False).index).head(15).iterrows():
        print(f"  {x['ind']:<30}{x['dif_mediana']:>+9.2f}")
    print(f"\n-> data_nuevo.json (NO se pisó el vivo) · atlas_cambios.csv")


if __name__ == "__main__":
    main()
