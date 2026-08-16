# -*- coding: utf-8 -*-
"""
ARMA LOS DOS TABLEROS METROPOLITANOS DESDE EL MOTOR VALIDADO.
==============================================================

Decisión de producto de Carlos: son DOS sitios, no uno.

  · **Tablero A — municipal**: todo lo que el motor calcula a nivel municipio
    (210 indicadores, 208 con serie 2012) más los fiscales por gestión.
  · **Tablero B — municipio ↔ manzana**: SÓLO los que existen en los dos niveles
    con la MISMA definición y que además REPRODUCEN la cifra urbana del
    microdato, para que el toggle conserve el indicador en vez de cambiar de
    objeto en silencio.

★ POR QUÉ DOS. El nivel manzana no tiene serie temporal, no tiene flujos y es
  sólo urbano. Un tablero único tendría que apagar medio panel al bajar de nivel.

★ DE DÓNDE SALE CADA COSA. La web venía leyendo el pipeline VIEJO
  (`derivar_indicadores.py` + `fusionar_catalogos.py`): 193 indicadores anteriores
  a toda la validación, con el denominador equivocado. Acá se lee lo que producen
  los motores validados contra el tabulado del INE.

★ SE EMITE EN LA FORMA QUE LA WEB YA CONSUME (`catalogo_tablero.json` +
  `municipios.json`), a propósito: así los dos sitios son el MISMO motor de
  interfaz —que ya funciona— con distinto par de archivos, en vez de una
  reescritura.

⚠️ EL AGREGADO REGIONAL SE PONDERA POR EL UNIVERSO DE CADA INDICADOR, no por
   población. Es el mismo error que tuvo el Atlas nacional: un porcentaje de
   VIVIENDAS ponderado por PERSONAS le da más peso a los municipios con hogares
   grandes. Cada motor emite su denominador en `_den_<indicador>`.

    python armar_tableros.py
"""
import json, pathlib, csv
import pandas as pd, numpy as np
from alias import renombrar, ALIAS

AQUI = pathlib.Path(__file__).parent
RAIZ = AQUI.parent
SALIDA = RAIZ / "web" / "datos"
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

POR_BLOQUE = {"municipal": "n_viviendas", "municipal_urbano": "n_viviendas",
              "personas": "poblacion", "personas_urbano": "poblacion",
              "nbi": "poblacion_nbi", "flujos_municipal": "trabajan_en_su_municipio"}
FUENTES24 = ["municipal", "personas", "nbi", "otros", "flujos_municipal"]
FUENTES12 = ["municipal", "personas", "nbi", "otros"]
FUENTES_URB = ["municipal_urbano", "personas_urbano"]

COBERTURA = {
 "municipio": "todo el territorio municipal, urbano y rural",
 "manzana": ("área urbana censada; 25.698 manzanas con ficha de 38.892 (66%), "
             "que concentran el 93,8% de la población de la región"),
}

# ★ LA TARJETA TIENE QUE DECIR QUÉ MUESTRA EL MAPA (pedido de Carlos).
#   ⚠️ NO sirve el campo `nota` del catálogo: son anotaciones INTERNAS de método
#      ("El INE lo publica sobre POBLACIÓN, no sobre viviendas: validar contra esa
#      hoja"). Usarlas como descripción le muestra al lector nuestra cocina.
#   La descripción se compone del universo declarado, que es el dato que de
#   verdad hace falta para leer el número: un 40% no significa lo mismo sobre
#   viviendas que sobre personas.
UNIVERSO = {
 "viv_ocu": "las viviendas particulares ocupadas",
 "viv_part": "todas las viviendas particulares",
 "hogares": "los hogares",
 "personas": "la población",
 "ocupados": "la población ocupada",
 "pet15": "la población en edad de trabajar (15 años o más)",
 "p19mas": "la población de 19 años o más",
 "p18mas": "la población de 18 años o más",
 "p15mas": "la población de 15 años o más",
 "p6_17": "la población de 6 a 17 años",
 "p4_5": "la población de 4 y 5 años",
 "muj12": "las mujeres de 12 años o más",
 "mef": "las mujeres en edad fértil (15 a 49 años)",
}


def describir(i, glosario):
    """Qué muestra el mapa, en una frase, sin jerga del pipeline."""
    uni = UNIVERSO.get(i.get("uni"))
    partes = [i["l"] + "."]
    if uni and i["u"] == "%":
        partes.append(f"Porcentaje sobre {uni}.")
    elif uni:
        partes.append(f"Medido sobre {uni}.")
    # si el INE define el término en su propio glosario, vale más que lo nuestro
    d = glosario.get(i["l"])
    if d and len(d) > 25:
        partes.append(d.strip().rstrip(".") + ".")
    return " ".join(partes)


def cargar(fuentes, sufijo):
    """Une los CSV de los motores y devuelve (valores, denominadores)."""
    val, den = None, {}
    for f in fuentes:
        p = AQUI / f"{f}_{sufijo}.csv"
        if not p.exists():
            print(f"  (falta {p.name})")
            continue
        d = pd.read_csv(p, index_col=0, dtype={0: str})
        d.index = d.index.astype(str).str.zfill(6)
        base = POR_BLOQUE.get(f)
        propios = {c[5:]: d[c] for c in d.columns if c.startswith("_den_")}
        d = d.drop(columns=[c for c in d.columns if c.startswith("_den_")])
        for c in d.columns:
            den[c] = propios.get(c, d[base] if base and base in d.columns else None)
        d = renombrar(d)
        val = d if val is None else val.join(
            d[[c for c in d.columns if c not in val.columns]], how="outer")
    return val, {ALIAS.get(k, k): v for k, v in den.items()}


def region(val, den, ks, cods):
    """Agregado de los 9, ponderado por el universo de cada indicador."""
    out = {}
    if val is None:
        return out
    for k in ks:
        if k not in val.columns:
            continue
        sub = val.loc[val.index.isin(cods), k]
        w = den.get(k)
        if w is None:
            if sub.notna().any():
                out[k] = round(float(sub.mean()), 3)
            continue
        ww = w.reindex(sub.index)
        m = sub.notna() & ww.notna() & (ww > 0)
        if m.any():
            out[k] = round(float((sub[m] * ww[m]).sum() / ww[m].sum()), 3)
    return out


def bloque(val, ks, ci):
    if val is None or ci not in val.index:
        return {}
    o = {}
    for k in ks:
        if k in val.columns:
            v = val.at[ci, k]
            if np.isfinite(v):
                o[k] = round(float(v), 3)
    return o


def catalogo(claves, decl, nivel, glosario, avisos=None, err=None, con_serie=None):
    """Catálogo en la forma que consume la web: grupos con `k_mun` / `k_mz`."""
    por = {}
    for k in claves:
        i = decl[k]
        it = {"key": k, "label": i["l"], "unit": i["u"], "dir": i.get("d", 0),
              "desc": describir(i, glosario), "fuente": "censo",
              "nivel": nivel, "k_mun": k,
              "k_mz": k if nivel == "ambos" else None,
              "continuo": nivel == "ambos"}
        if con_serie is not None:
            it["serie"] = k in con_serie
        if avisos and k in avisos:
            it["aviso"] = (f"La suma de las manzanas y la cifra urbana del municipio "
                           f"difieren {err.get(k, 0):.1f} pp en promedio: varía fuerte "
                           f"en el borde del área urbana censada.")
        por.setdefault(i["g"], []).append(it)
    return [{"key": g.lower().replace(" ", "_").replace("ó", "o").replace("í", "i"),
             "label": g, "indicadores": sorted(v, key=lambda x: x["label"])}
            for g, v in sorted(por.items())]


def main():
    decl = {i["k"]: i for i in
            json.loads((AQUI / "catalogo.json").read_text(encoding="utf-8"))["indicadores"]}
    comp = json.loads((AQUI / "comparables.json").read_text(encoding="utf-8"))
    muns = json.loads((RAIZ / "datos" / "municipios.json").read_text(encoding="utf-8"))
    cods = [m["cod_ine"] for m in muns]
    sp = {r["cod_ine"]: r for r in csv.DictReader(open(SPINE, encoding="utf-8"))}
    fiscal = json.loads((SALIDA / "fiscal.json").read_text(encoding="utf-8"))
    glosario = json.loads((AQUI / "glosario_ine.json").read_text(encoding="utf-8"))

    v24, d24 = cargar(FUENTES24, "2024")
    v12, d12 = cargar(FUENTES12, "2012")
    vur, dur = cargar(FUENTES_URB, "2024")

    def ficha(m, ks, con_urbano, con_2012):
        ci = m["cod_ine"]
        r = {"sigep": m.get("sigep"), "cod_ine": ci,
             "nombre": sp.get(ci, {}).get("nombre", m["nombre"]),
             "ambito": m.get("ambito"), "manzanas": m.get("manzanas"),
             "con_ficha": m.get("con_ficha"),
             "personas_urbano": m.get("personas_urbano"),
             "viviendas_urbano": m.get("viviendas_urbano"),
             # ★ población y viviendas viajan SIEMPRE, aunque no estén entre los
             #   indicadores del tablero: son CONTEXTO, no un indicador elegible.
             #   Sin esto el Tablero B —donde `pob_total` no es comparable con la
             #   manzana— encabezaba la ficha con "9 municipios · 0 personas".
             "municipal": bloque(v24, sorted(set(ks) | {"pob_total", "viviendas"}), ci)}
        r["urbano"] = bloque(vur, ks, ci) if con_urbano else {}
        if con_2012:
            r["municipal_2012"] = bloque(v12, ks, ci)
        return r

    # ── TABLERO A — municipal ────────────────────────────────────────────────
    ks_a = sorted(k for k in v24.columns if k in decl)
    serie = {k for k in ks_a if k in v12.columns}
    print(f"TABLERO A · municipal: {len(ks_a)} indicadores · con serie 2012: {len(serie)}")
    # ★ LOS FISCALES SE CONSERVAN TAL CUAL. No salen del microdato censal sino de
    #   la ejecución presupuestaria del MEFP (30 indicadores × 10 gestiones, en
    #   `fiscal.json`), así que no pasan por los motores ni por esta validación:
    #   se toman del catálogo anterior, que ya los tenía descritos. Sin esto el
    #   tablero municipal perdía el bloque fiscal entero respecto del que había.
    viejo = json.loads((SALIDA / "catalogo_tablero.json").read_text(encoding="utf-8"))
    g_fis = [{"key": g["key"], "label": g["label"],
              "indicadores": [i for i in g["indicadores"] if i.get("fuente") == "fiscal"]}
             for g in viejo["grupos"]]
    g_fis = [g for g in g_fis if g["indicadores"]]
    print(f"  + bloque fiscal: {len(g_fis)} categorías · "
          f"{sum(len(g['indicadores']) for g in g_fis)} indicadores × "
          f"{len(fiscal.get('anios', []))} gestiones")

    (SALIDA / "catalogo_municipal.json").write_text(json.dumps({
        "tablero": "municipal", "anios_fiscal": fiscal.get("anios", []),
        "niveles": {"municipio": {"n": len(muns), "fuente": "INE Censo 2024 y 2012 · MEFP",
                                  "cobertura": COBERTURA["municipio"]}},
        "grupos": catalogo(ks_a, decl, "municipio", glosario, con_serie=serie) + g_fis,
        "region": {"municipal": region(v24, d24, ks_a, cods),
                   "municipal_2012": region(v12, d12, sorted(serie), cods)},
    }, ensure_ascii=False), encoding="utf-8")
    (SALIDA / "municipios_municipal.json").write_text(json.dumps(
        [ficha(m, ks_a, False, True) for m in muns], ensure_ascii=False), encoding="utf-8")

    # ── TABLERO B — municipio ↔ manzana ──────────────────────────────────────
    ks_b = sorted(set(comp["verificados"]) & set(decl) & set(v24.columns))
    avisos, err = set(comp.get("con_aviso", [])), comp.get("error_pp", {})
    print(f"TABLERO B · comparables: {len(ks_b)} indicadores "
          f"({len(avisos)} con aviso · {len(comp.get('excluidos', []))} excluidos por definición)")
    (SALIDA / "catalogo_manzana.json").write_text(json.dumps({
        "tablero": "manzana", "anios_fiscal": [],
        "niveles": {k: {"n": len(muns) if k == "municipio" else 38892,
                        "fuente": ("INE Censo 2024, microdato" if k == "municipio"
                                   else "INE Censo 2024, fichas por manzano"),
                        "cobertura": COBERTURA[k]} for k in ("municipio", "manzana")},
        "excluidos": comp.get("excluidos", []),
        "grupos": catalogo(ks_b, decl, "ambos", glosario, avisos, err),
        "region": {"municipal": region(v24, d24, ks_b, cods),
                   "urbano": region(vur, dur, ks_b, cods)},
    }, ensure_ascii=False), encoding="utf-8")
    (SALIDA / "municipios_manzana.json").write_text(json.dumps(
        [ficha(m, ks_b, True, False) for m in muns], ensure_ascii=False), encoding="utf-8")

    for n in ("catalogo_municipal", "municipios_municipal",
              "catalogo_manzana", "municipios_manzana"):
        f = SALIDA / f"{n}.json"
        print(f"  -> {f.name:<28}{f.stat().st_size/1024:>8.0f} KB")


if __name__ == "__main__":
    main()
