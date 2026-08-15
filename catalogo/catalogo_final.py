# -*- coding: utf-8 -*-
"""
CATÁLOGO FINAL DEL ATLAS: fusiona grupos, adopta el INE y explica cada indicador.
=================================================================================

`generar_atlas.py` agregaba los indicadores nuevos creando un grupo por cada
categoría del catálogo del motor, y eso producía **duplicados temáticos**: el
Atlas ya tiene "Servicios Básicos" y aparecía además "Agua", "Saneamiento" y
"Residuos" como categorías separadas. No eran temas nuevos, era el mismo tema
con otro rótulo — y por eso pasar de 18 a 29 grupos se sentía tanto.

Acá se resuelven tres cosas de una:

1. **FUSIÓN DE GRUPOS.** `MAPA_GRUPOS` manda cada categoría del motor a la
   categoría que el Atlas ya usa. Sólo quedan como nuevas las que de verdad no
   existían.

2. **`paridez_media` ADOPTA LA DEFINICIÓN DEL INE.** Decisión de Carlos, y
   aplica el criterio general: si el INE publica el indicador con ese nombre, el
   nombre ya tiene dueño y significado público; publicar otra cosa bajo él es el
   error, por impecable que sea nuestro cálculo.
   ★ Verificado aritméticamente contra `salud/6`: su paridez es
     `hijos nacidos vivos / (total de mujeres − sin información)` y su universo
     son las MUJERES EN EDAD FÉRTIL (15-49) — 87.540 en Sucre, contra 116.900 si
     fueran todas las de 15+. Eso es exactamente lo que el motor venía llamando
     `fecundidad`. ⇒ `fecundidad` pasa a llamarse `paridez_media`, y la versión
     vieja sobre mujeres de 12+ se retira del Atlas (sigue en el motor).

3. **DEFINICIONES OFICIALES.** `glosario_ine.json` trae 242 términos definidos
   por el propio INE, extraídos de las hojas "Glosario" de los 18 tabulados. Se
   emparejan con la etiqueta del indicador para que el botón con minimapa
   explique qué mide **con las palabras de la fuente**, no con una paráfrasis
   nuestra.
"""
import json, pathlib, re, unicodedata

AQUI = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos"
                    r"\Observatorio de Presupuesto Fiscal Departamental\_github_atlas_fiscal")

# ── categoría del motor -> categoría que el Atlas YA usa ────────────────────
# Las que no están acá se crean como grupo nuevo, y son sólo las que de verdad
# no existían en el Atlas.
MAPA_GRUPOS = {
    "Agua":                          "Servicios Básicos",
    "Saneamiento":                   "Servicios Básicos",
    "Residuos":                      "Servicios Básicos",
    "Energía y cocina":              "Energía y Cocina",
    "Vivienda y materiales":         "Vivienda y Materiales",
    "Demografía y estructura":       "Demografía",
    "Tecnología y equipamiento":     "Tecnología y Conectividad",
    "Pueblos, idiomas y ciudadanía": "Pueblos e Idiomas",
    "Migración y territorio":        "Migración interna",
    "Emigración internacional y mortalidad": "Emigración internacional",
    # genuinamente nuevas
    "Hogares y jefatura":            "Hogares y Jefatura",
    "Flujos metropolitanos":         "Flujos Metropolitanos",
}

# ── el INE manda en el nombre ────────────────────────────────────────────────
RENOMBRA = {"fecundidad": "paridez_media"}
# la paridez sobre mujeres 12+ no es la del INE: no va al Atlas
RETIRA = {"paridez_media_12mas"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", s.lower()).split())


VACIAS = {"de", "la", "el", "los", "las", "en", "con", "sin", "por", "y", "o",
          "del", "al", "un", "una", "que", "se", "su", "mas", "es", "para"}


def definicion(label, glos, _idx={}):
    """La definición del INE que corresponde a la etiqueta, si la hay.

    ⚠️ El emparejamiento LITERAL no alcanza: los rótulos del Atlas son cortos
    ("Con agua por cañería") y los términos del glosario son conceptos ("Agua por
    cañería de red"). Con igualdad o subcadena sólo enganchaban 64 de 215.
    Se usa solapamiento de palabras con peso, exigiendo que la coincidencia sea
    sustantiva: al menos dos términos de contenido en común y que cubran la
    mayoría del rótulo. Es preferible NO poner definición a poner una ajena.
    """
    if not _idx:
        _idx.update({norm(k): (v, set(norm(k).split()) - VACIAS)
                     for k, v in glos.items()})
    n = norm(label)
    tn = set(n.split()) - VACIAS
    if not tn:
        return None
    if n in _idx:
        return _idx[n][0]
    mejor, puntaje = None, 0.0
    for k, (v, tk) in _idx.items():
        if not tk:
            continue
        comun = tn & tk
        if len(comun) < 2 and not (len(tn) == 1 and tn <= tk):
            continue
        # cuánto del rótulo cubre el término, y cuánto del término el rótulo
        p = len(comun) / len(tn) * 0.7 + len(comun) / len(tk) * 0.3
        if p > puntaje:
            mejor, puntaje = v, p
    return mejor if puntaje >= 0.55 else None


def main():
    glos = json.loads((AQUI / "glosario_ine.json").read_text(encoding="utf-8"))
    viv = json.loads((REPO / "catalogo.json").read_text(encoding="utf-8"))
    amp = json.loads((REPO.parent / "catalogo_nuevo.json").read_text(encoding="utf-8"))

    # ⚠️ El renombre se aplica TAMBIÉN a los indicadores que el Atlas ya publica:
    #    `fecundidad` está entre los 136 vivos, así que renombrar sólo los nuevos
    #    dejaría el MISMO indicador dos veces con nombres distintos.
    def ren(ind):
        k = RENOMBRA.get(ind["key"], ind["key"])
        if k == ind["key"]:
            return ind
        return {**ind, "key": k, "label": "Paridez media"}

    orden = [g["label"] for g in viv["grupos"]]
    grupos = {g["label"]: {**g, "indicadores": [ren(i) for i in g["indicadores"]]}
              for g in viv["grupos"]}
    viejas = {i["key"] for g in grupos.values() for i in g["indicadores"]}

    nuevos = 0
    for g in amp["grupos"]:
        destino = MAPA_GRUPOS.get(g["label"], g["label"])
        for ind in g["indicadores"]:
            k = RENOMBRA.get(ind["key"], ind["key"])
            if k in viejas or k in RETIRA:
                continue
            viejas.add(k)
            nuevos += 1
            if destino not in grupos:
                grupos[destino] = {"key": norm(destino).replace(" ", "_"),
                                   "label": destino, "indicadores": []}
                orden.append(destino)
            grupos[destino]["indicadores"].append({**ind, "key": k})

    # ── explicación de cada indicador, en tres niveles de preferencia ──
    # 1. la definición OFICIAL del INE, cuando el glosario cubre el concepto
    # 2. la descripción propia del Atlas, si es sustantiva
    # 3. la REGLA DE CÁLCULO declarada en el catálogo del motor: dice
    #    exactamente qué se cuenta y sobre qué universo, que para un indicador
    #    demográfico ("Mujeres", "Edad promedio") es más útil que una definición
    #    de diccionario.
    decl = {i["k"]: i for i in json.loads(
        (AQUI / "catalogo.json").read_text(encoding="utf-8"))["indicadores"]}
    UNIV = {"personas": "personas", "viv_ocu": "viviendas particulares ocupadas",
            "hogares": "hogares", "ocupados": "población ocupada de 14+",
            "p6_17": "población de 6 a 17 años", "viviendas": "viviendas"}
    con = propia = regla = 0
    for g in grupos.values():
        for i in g["indicadores"]:
            d = definicion(i["label"], glos)
            if d:
                i["desc_ine"] = d
                con += 1
                continue
            prop = (i.get("desc") or "").strip()
            if prop and prop != i["label"] and len(prop) >= 25:
                propia += 1
                continue
            # último recurso: la regla declarada
            c = decl.get(i["key"], {})
            uni = UNIV.get(c.get("uni"), c.get("uni"))
            r = c.get("e24")
            partes = []
            if uni:
                partes.append(f"Se calcula sobre {uni}")
            if r and r not in ("derivado", None):
                partes.append(f"regla: {r}")
            if partes:
                i["desc"] = i["label"] + ". " + " · ".join(partes) + "."
                regla += 1
    sin = sum(1 for g in grupos.values() for i in g["indicadores"]
              if "desc_ine" not in i and len((i.get("desc") or "")) < 25)

    out = {"grupos": [grupos[l] for l in orden]}
    (REPO.parent / "catalogo_final.json").write_text(
        json.dumps(out, ensure_ascii=False), encoding="utf-8")

    tot = sum(len(g["indicadores"]) for g in out["grupos"])
    print(f"CATÁLOGO FINAL: {tot} indicadores en {len(out['grupos'])} grupos")
    print(f"  (el Atlas vivo tiene 136 en 18 · se agregan {nuevos})")
    print(f"  con definición OFICIAL del INE : {con}")
    print(f"  con descripción propia         : {propia}")
    print(f"  con la regla de cálculo        : {regla}")
    print(f"  SIN explicación                : {sin}")
    print()
    print("GRUPOS:")
    for g in out["grupos"]:
        mark = "  ← NUEVO" if g["label"] not in [x["label"] for x in viv["grupos"]] else ""
        print(f"   {g['label']:<30}{len(g['indicadores']):>4}{mark}")
    return out


if __name__ == "__main__":
    main()
