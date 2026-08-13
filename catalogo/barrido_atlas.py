# -*- coding: utf-8 -*-
"""
BARRIDO PREVIO AL REEMPLAZO DEL ATLAS.
======================================

`tasa_mortalidad` enseñó que **"el nuevo es el bueno" no es automático**: ahí el
equivocado era nuestro motor (33,4 por mil contra una referencia de ~7), y ni
`chequeo.py` ni los validadores lo agarraban —no era un valor imposible y no
tenía hoja del INE—. Lo cazó comparar contra el valor publicado y contra una
referencia externa.

Este script hace eso de forma sistemática antes de publicar: parte los
indicadores que se mueven en dos, según el respaldo que tengan.

  · **VALIDADO** — coincide al 343/343 con el tabulado del INE. Si se mueve, el
    que estaba mal es el Atlas. Se puede publicar sin mirar.
  · **SIN VALIDAR** — no hay hoja del INE contra la cual contrastarlo. Acá el
    movimiento NO prueba nada, y hay que mirarlo con criterio externo. Es la
    lista corta que hay que revisar a mano.

No decide por nadie: ordena por cuánto se mueve y marca de qué lado está cada uno.
"""
import pathlib, json
import pandas as pd, numpy as np
from alias import ALIAS, ATLAS

AQUI = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos"
                    r"\Observatorio de Presupuesto Fiscal Departamental\_github_atlas_fiscal")


def validados():
    """Los que están probados contra el tabulado, en vocabulario del Atlas."""
    import validar as V, validar_persona as VP
    v = {ALIAS.get(c[0], c[0]) for c in V.CASOS}
    v |= {ALIAS.get(c[0], c[0]) for c in VP.CASOS}
    v |= {ALIAS.get(c[0], c[0]) for c in VP.CASOS_VALOR}
    v |= {ALIAS.get(c[0], c[0]) for c in VP.CASOS_CONTEO_POB}
    v |= {"pct_idioma_materno_castellano", "pct_idioma_materno_originario"}
    # traducir al vocabulario del Atlas (la equivalencia va al revés)
    inv = {b: a for a, b in ATLAS.items()}
    return v | {inv[k] for k in v if k in inv}


def main():
    A = pd.DataFrame(json.load(open(REPO / "data.json", encoding="utf-8"))).T
    B = pd.DataFrame(json.load(open(REPO.parent / "data_nuevo.json", encoding="utf-8"))).T
    ok = validados()

    filas = []
    for k in A.columns:
        if k in ("cod_ine", "nombre", "dpto") or k not in B.columns:
            continue
        a = pd.to_numeric(A[k], errors="coerce")
        b = pd.to_numeric(B[k], errors="coerce")
        j = pd.concat([a, b], axis=1, keys=["viejo", "nuevo"]).dropna()
        if len(j) < 300:
            continue
        d = j["nuevo"] - j["viejo"]
        if (d.abs() < 0.05).mean() > 0.99:
            continue                                   # no se mueve
        filas.append({"ind": k, "validado": k in ok,
                      "viejo": j["viejo"].median(), "nuevo": j["nuevo"].median(),
                      "dif": d.median(), "max_abs": d.abs().max()})
    r = pd.DataFrame(filas)
    r["orden"] = r.dif.abs()
    r = r.sort_values("orden", ascending=False)
    r.drop(columns="orden").to_csv(AQUI / "barrido_atlas.csv", index=False, encoding="utf-8")

    v, s = r[r.validado], r[~r.validado]
    print(f"indicadores que se mueven: {len(r)}")
    print(f"  VALIDADOS contra el INE  : {len(v)}  -> el que estaba mal es el Atlas")
    print(f"  SIN VALIDAR              : {len(s)}  -> HAY QUE MIRARLOS")
    print()
    print("★ LA LISTA A REVISAR A MANO (sin respaldo del INE, ordenada por movimiento)")
    print("=" * 74)
    print(f"{'indicador':<32}{'viejo':>9}{'nuevo':>9}{'dif':>9}{'max':>9}")
    for _, x in s.iterrows():
        print(f"  {x['ind']:<30}{x['viejo']:>9.2f}{x['nuevo']:>9.2f}"
              f"{x['dif']:>+9.2f}{x['max_abs']:>9.1f}")
    print("\n-> barrido_atlas.csv")


if __name__ == "__main__":
    main()
