"""
Fusiona los tres catálogos del tablero metropolitano en uno solo.

    136  censales municipales   (Atlas Socioeconómico, cobertura total)
     30  fiscales municipales   (Atlas Fiscal, × 10 gestiones)
     52  censales por manzana   (derivados de las fichas del INE, sólo urbano)

Sale `datos/catalogo_tablero.json`: UNA lista de grupos temáticos donde cada
indicador declara en qué NIVELES existe. Así el panel es uno solo y el toggle
municipio↔manzana no cambia de menú: cambia de resolución.

TRES DECISIONES QUE VALE LA PENA NO RE-DISCUTIR

1. Un indicador que existe en los dos niveles con la MISMA definición es UNA
   entrada con `nivel:"ambos"` y `continuo:true`. Al hacer zoom se conserva.

2. Un par temáticamente gemelo pero con definición distinta va como DOS
   entradas, y a la de manzana se le reescribe la etiqueta para que la
   diferencia se vea en el menú: "Sin nivel educativo (15+)" a nivel municipal
   contra "Sin nivel educativo · toda la población" en la manzana. Fusionarlos
   en una sola entrada sería cómodo y falso: el número saltaría al hacer zoom y
   el lector leería un cambio territorial que no existe.

3. Los indicadores fiscales NO bajan de municipio y nunca van a bajar: no existe
   presupuesto por manzana. Se marcan `nivel:"municipio"` y el mapa debe
   desactivar el toggle cuando uno de ellos está activo, en vez de dejar un
   botón que no hace nada.
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ATLAS = RAIZ.parent / "Observatorio de Presupuesto Fiscal Departamental" / "_github_atlas_fiscal"
SALIDA = RAIZ / "datos" / "catalogo_tablero.json"

# Grupo del Atlas donde cae cada grupo de manzana cuando el indicador NO tiene
# gemelo municipal (si lo tiene, hereda el grupo de su gemelo).
GRUPO_POR_DEFECTO = {
    "poblacion":    "Demografía",
    "migracion":    "Migración interna",
    "educacion":    "Educación",
    "salud":        "Salud",
    "trabajo":      "Empleo",
    "vivienda":     "Tenencia",
    "servicios":    "Servicios Básicos",
    "conectividad": "Tecnología y Conectividad",
}

# Reescritura de etiqueta para las de manzana cuya definición NO coincide con la
# municipal. Sin esto el menú mostraría dos entradas casi idénticas y el usuario
# elegiría una creyendo que es la otra.
ETIQUETA_MANZANA = {
    "pct_menor20":      "Menores de 20 años",
    "pct_60mas":        "60 años y más",
    "dependencia":      "Razón de dependencia (20-59 como base)",
    "pers_x_vivienda":  "Personas por vivienda",
    "pct_educ_superior": "Educación superior · toda la población",
    "pct_sin_educacion": "Sin nivel educativo · toda la población",
    "pct_sin_seguro":   "Sin afiliación a salud",
    "pct_manufactura":  "Manufactura",
    "pct_agricultura":  "Agricultura",
    "pct_pozo_ciego":   "Pozo ciego (sin superficie)",
}


def main():
    mz_cat = json.loads((RAIZ / "datos" / "catalogo.json").read_text(encoding="utf-8"))
    at_cat = json.loads((ATLAS / "catalogo.json").read_text(encoding="utf-8"))
    fi_cat = json.loads((ATLAS / "fiscal_catalogo.json").read_text(encoding="utf-8"))
    cw = json.loads((RAIZ / "datos" / "crosswalk.json").read_text(encoding="utf-8"))

    por_mz = {c["manzana"]: c for c in cw}
    mz_ind = {i["key"]: (g["key"], i) for g in mz_cat["grupos"] for i in g["indicadores"]}
    # municipal -> manzana, sólo para los que son continuos
    mun_a_mz = {c["municipal"]: c for c in cw if c["municipal"]}

    grupos = {}          # label -> lista de indicadores
    orden = []           # para conservar el orden del Atlas

    # ── 1. Censales municipales (la espina del menú) ─────────────────────────
    for g in at_cat["grupos"]:
        orden.append(g["label"])
        grupos.setdefault(g["label"], [])
        for i in g["indicadores"]:
            c = mun_a_mz.get(i["key"])
            ent = {
                "key": i["key"], "label": i["label"], "unit": i.get("unit", ""),
                "dir": i.get("dir", 0), "desc": i.get("desc", ""),
                "fuente": "censo", "nivel": "municipio",
                "k_mun": i["key"], "k_mz": None, "continuo": None,
            }
            if c and c["comparable"] == "si":
                ent.update(nivel="ambos", k_mz=c["manzana"], continuo=True)
            elif c and c["comparable"] in ("no", "revisar"):
                # el gemelo va como entrada aparte; acá sólo se deja el puntero
                ent["par_manzana"] = {"key": c["manzana"], "nota": c["nota"],
                                      "estado": c["comparable"]}
            grupos[g["label"]].append(ent)

    # ── 2. De manzana que NO quedaron absorbidas arriba ──────────────────────
    absorbidas = {c["manzana"] for c in cw if c["comparable"] == "si" and c["municipal"]}
    for key, (gkey, i) in mz_ind.items():
        if key in absorbidas:
            continue
        c = por_mz[key]
        destino = None
        if c["municipal"]:                       # hereda el grupo de su gemelo
            for lbl, inds in grupos.items():
                if any(x["key"] == c["municipal"] for x in inds):
                    destino = lbl
                    break
        destino = destino or GRUPO_POR_DEFECTO.get(gkey, "Demografía")
        grupos.setdefault(destino, [])
        if destino not in orden:
            orden.append(destino)
        ent = {
            "key": f"mz_{key}", "label": ETIQUETA_MANZANA.get(key, i["label"]),
            "unit": i["unit"], "dir": i["dir"], "desc": i["desc"],
            "fuente": "censo", "nivel": "manzana",
            "k_mun": None, "k_mz": key, "continuo": None,
        }
        if c["municipal"]:
            ent["par_municipal"] = {"key": c["municipal"], "nota": c["nota"],
                                    "estado": c["comparable"]}
        if c["nota"] and not c["municipal"]:
            ent["nota"] = c["nota"]
        grupos[destino].append(ent)

    # ── 3. Fiscales (municipio y sólo municipio) ─────────────────────────────
    for g in fi_cat["grupos"]:
        lbl = f"Fiscal · {g['label']}"
        orden.append(lbl)
        grupos[lbl] = [{
            "key": f"fi_{i['key']}", "label": i["label"], "unit": i.get("unit", ""),
            "dir": i.get("dir", 0), "desc": i.get("desc", ""),
            "fuente": "fiscal", "nivel": "municipio",
            "k_mun": i["key"], "k_mz": None, "continuo": None,
            "serie": True, "div": bool(i.get("div")),
        } for i in g["indicadores"]]

    salida = {
        "anios_fiscal": fi_cat["anios"],
        "niveles": {
            "municipio": {"n": 9,      "fuente": "INE Censo 2024 · MEFP ejecución presupuestaria",
                          "cobertura": "todo el territorio municipal"},
            "manzana":   {"n": 38892,  "fuente": "INE Censo 2024, fichas por manzano",
                          "cobertura": "área urbana censada; 25.698 manzanas con ficha (66%), "
                                       "que concentran el 93,8% de la población de la región"},
        },
        "grupos": [{"key": lbl.lower().replace(" · ", "_").replace(" ", "_"),
                    "label": lbl, "indicadores": grupos[lbl]}
                   for lbl in orden if grupos.get(lbl)],
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")

    # ── recuento ─────────────────────────────────────────────────────────────
    todos = [i for g in salida["grupos"] for i in g["indicadores"]]
    n = lambda f: sum(1 for i in todos if f(i))
    print(f"Catálogo del tablero: {len(salida['grupos'])} grupos · {len(todos)} indicadores")
    print(f"  ambos niveles (el toggle conserva)  {n(lambda i: i['nivel']=='ambos'):>4}")
    print(f"  sólo municipio · censal             {n(lambda i: i['nivel']=='municipio' and i['fuente']=='censo'):>4}")
    print(f"  sólo municipio · fiscal             {n(lambda i: i['fuente']=='fiscal'):>4}")
    print(f"  sólo manzana                        {n(lambda i: i['nivel']=='manzana'):>4}")
    print(f"  con par de otra definición          {n(lambda i: 'par_manzana' in i or 'par_municipal' in i):>4}")
    print(f"\n→ {SALIDA}")


if __name__ == "__main__":
    main()
