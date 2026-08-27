# -*- coding: utf-8 -*-
"""LAS TARJETAS DICEN EL CORTE DE EDAD Y LA BASE DEL ÍNDICE.

★ EL PEDIDO (Carlos, 2026-08-27): «el índice de juventud dice qué peso tiene la
  población joven dentro de la población total — ¿qué se define como joven? Es
  un número índice, ¿de dónde sale? Hay valores de 900, ¿es por cada 100 no
  jóvenes o cómo?». Y: revisarlo en TODOS.

Se revisó en todos, contra el MOTOR —que es quien produce el número— y no
contra el catálogo, que en varios casos declara otra cosa. Aparecieron tres
familias de error, y ninguna es de redacción:

──────────────────────────────────────────────────────────────────────────────
1 · UNA DESCRIPCIÓN QUE DESCRIBE OTRA ESTADÍSTICA
   `indice_juventud` decía «qué peso tienen las personas jóvenes dentro de la
   población total». El motor calcula `100 * n0_14 / n65`: menores de quince por
   cada cien personas de sesenta y cinco o más. Verificado sobre el dato
   publicado: coincide con esa fórmula y **coincide con el % de 15-29 en 0 de
   los 343 municipios**. Por eso hay valores de 1.651 — mil seiscientos chicos
   por cada cien viejos, no un porcentaje.
   ⚠️ El `catalogo.py` TAMBIÉN lo declara mal (`e24 = 100 * 15-29 / total`): la
      descripción se escribió desde esa declaración. Tres fuentes y sólo el
      motor tenía razón.

2 · RÓTULOS QUE CONTRADICEN A SU PROPIO UNIVERSO
   Siete indicadores de Educación anuncian un corte de edad en el título y otro
   en el universo. El motor usa `uni="p19mas"`, y el total del denominador lo
   confirma: 7.350.282 = 0,647 de la población, que es la de 19 años o más.
   El rótulo es el que está mal.

3 · UNIVERSOS QUE NO SON LOS QUE USA EL MOTOR
   Se identificó cada denominador por su TOTAL NACIONAL y se contrastó con el
   motor. Ocho no decían la verdad. El más grave:
   `tasa_desocupacion` decía «sobre la población en edad de trabajar» y el
   motor divide por la PEA (`100*(n_pea-n_ocu)/n_pea`); el denominador suma
   5.931.530 y la población de 15+ son 8.300.933. No es un matiz: cambia el
   denominador de la tasa de desempleo.
──────────────────────────────────────────────────────────────────────────────

    python catalogo/precisar_atlas.py            # ensayo
    python catalogo/precisar_atlas.py --escribir
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
REPO = (AQUI.parent.parent / "Observatorio de Presupuesto Fiscal Departamental"
        / "_github_atlas_fiscal")

# ── 1 · rótulos: el corte de edad que dice el MOTOR ──────────────────────────
# `uni="p19mas"` en catalogo.py, confirmado por el total del denominador
ROTULOS = {
 "prom_anios_estudio":  "Años de estudio promedio (19+)",
 "pct_sin_educacion":   "Sin nivel educativo (19+)",
 "pct_edu_primaria":    "Solo primaria (19+)",
 "pct_edu_secundaria":  "Secundaria (19+)",
 "pct_edu_superior":    "Educación superior (19+)",
 "pct_secundaria_mas":  "Secundaria o más (19+)",
 # `esc = res & d.edad.between(8, 17)` — ni 12-17 ni 6-17
 "pct_rezago_escolar":  "Rezago escolar (8-17)",
}

# ── 2 · universos: los que el motor usa de verdad ────────────────────────────
UNIVERSOS = {
 # 100*(n_pea-n_ocu)/n_pea — la PEA, no la población en edad de trabajar
 "tasa_desocupacion":      "sobre la población económicamente activa",
 # pct(hijos>0, mujer & edad.between(15,19))
 "pct_madres_adolescentes": "sobre las mujeres de 15 a 19 años",
 # pct(publica, edad.between(4,17) & asiste)
 "pct_educacion_publica":  "sobre quienes asisten a un establecimiento educativo, de 4 a 17 años",
 # mef = mujer & edad.between(15,49) & hijos_nac.notna()
 "paridez_media":          "sobre las mujeres de 15 a 49 años que declararon hijos",
 # res & parto_quien.between(1,8) — a quien se le hace la pregunta
 "pct_parto_calificado":   "sobre las mujeres con un parto en los últimos cinco años",
 "pct_rezago_escolar":     "sobre la población de 8 a 17 años que asiste a la escuela",
 # el denominador de la razón son las habitaciones y los dormitorios, no las viviendas
 "pers_x_habitacion":      "sobre las habitaciones de las viviendas particulares ocupadas",
 "pers_x_dormitorio":      "sobre los dormitorios de las viviendas particulares ocupadas",
}

# ── 3 · descripciones: nombrar el corte y la base ────────────────────────────
# La regla: si el indicador tiene un corte de edad, la definición lo dice; si es
# una razón, dice POR CADA CUÁNTO. El rótulo puede traerlo, pero la definición
# no puede contradecirlo ni dejarlo en «personas mayores».
DESCRIPCIONES = {
 "indice_juventud":
   "Cuántos menores de quince años hay por cada cien personas de sesenta y cinco "
   "o más. Es el espejo del índice de envejecimiento: por encima de cien hay más "
   "chicos que viejos, y en Bolivia llega a pasar de mil.",
 "indice_envejecimiento":
   "Cuántas personas de sesenta y cinco años o más hay por cada cien menores de "
   "quince. Cruzar cien significa que ya hay más viejos que chicos.",
 "pct_0_14":
   "Niñas, niños y adolescentes de hasta catorce años.",
 "pct_65_mas":
   "Personas de sesenta y cinco años o más.",
 "pct_15_64":
   "Población de quince a sesenta y cuatro años, la franja en edades típicamente "
   "activas; es el grupo que sostiene económicamente a los otros dos.",
 "prom_anios_estudio":
   "Cuántos años de escuela acumula, en promedio, una persona de diecinueve años o más.",
 "pct_sin_educacion":
   "Personas de diecinueve años o más que no completaron ningún nivel educativo.",
 "pct_edu_primaria":
   "Personas de diecinueve años o más cuyo máximo nivel alcanzado es la primaria.",
 "pct_edu_secundaria":
   "Personas de diecinueve años o más cuyo máximo nivel alcanzado es la secundaria.",
 "pct_edu_superior":
   "Personas de diecinueve años o más con estudios técnicos o universitarios. Es "
   "el indicador que más separa a unos municipios de otros.",
 "pct_secundaria_mas":
   "Personas de diecinueve años o más que terminaron al menos la secundaria.",
 "pct_primaria_completa":
   "Personas de diecinueve años o más que completaron los seis años de primaria.",
 "pct_rezago_escolar":
   "De ocho a diecisiete años, quienes van dos o más cursos por debajo del que les "
   "corresponde por edad; mide el atraso acumulado, no el abandono.",
 "paridez_media":
   "Cuántos hijos ha tenido, en promedio, una mujer de quince a cuarenta y nueve años.",
 "tasa_desocupacion":
   "De quienes están en el mercado laboral —trabajando o buscando—, cuántos buscan "
   "trabajo y no lo encuentran.",
 "pct_educacion_publica":
   "De quienes asisten a un establecimiento educativo, cuántos van a uno público o "
   "de convenio y no a uno privado.",
 "pct_parto_calificado":
   "De las mujeres que tuvieron un parto en los últimos cinco años, cuántas fueron "
   "atendidas por personal de salud y no por partera o familiar.",
 "indice_masculinidad":
   "Cuántos hombres hay por cada cien mujeres en toda la población. Por encima de "
   "cien indica predominio masculino, algo típico de zonas de trabajo agrícola o minero.",
 "pers_x_habitacion":
   "Cuántas personas hay, en promedio, por cada habitación —los cuartos sin contar "
   "baño ni cocina—. Es la medida de hacinamiento.",
 "pers_x_dormitorio":
   "Cuántas personas hay, en promedio, por cada dormitorio.",
}

EDAD = re.compile(r"\((\d{1,2})\s*[–-]\s*(\d{1,2})\)|\((\d{1,2})\+\)")
EDAD_UNI = re.compile(r"(\d{1,2})\s*(?:a|y)\s*(\d{1,2})\s*años|(\d{1,2})\s*años o más")


def rangos(txt, pat):
    out = set()
    for m in pat.finditer(txt or ""):
        gs = [g for g in m.groups() if g]
        out.add(tuple(gs))
    return out


def main(escribir):
    cat = json.loads((REPO / "catalogo.json").read_text(encoding="utf-8"))
    inds = [i for g in cat["grupos"] for i in g["indicadores"]]
    n_r = n_u = n_d = 0
    for i in inds:
        k = i["key"]
        if k in ROTULOS and i["label"] != ROTULOS[k]:
            print(f"  rótulo   {k}\n     antes: {i['label']}\n     ahora: {ROTULOS[k]}")
            i["label"] = ROTULOS[k]
            n_r += 1
        if k in UNIVERSOS and i.get("universo") != UNIVERSOS[k]:
            print(f"  universo {k}\n     antes: {i.get('universo')}\n     ahora: {UNIVERSOS[k]}")
            i["universo"] = UNIVERSOS[k]
            n_u += 1
        if k in DESCRIPCIONES and i.get("desc") != DESCRIPCIONES[k]:
            n_d += 1
            i["desc"] = DESCRIPCIONES[k]
    print(f"\n  rótulos {n_r} · universos {n_u} · descripciones {n_d}")

    # ── EL CHEQUEO QUE IMPIDE QUE VUELVA ────────────────────────────────────
    # Si el rótulo anuncia un corte de edad, el universo tiene que decir el
    # MISMO. Es lo que estaba fallando en siete indicadores a la vez.
    print("\n▸ ¿ALGÚN RÓTULO SIGUE CONTRADICIENDO A SU UNIVERSO?")
    choques = 0
    for i in inds:
        rl = rangos(i["label"], EDAD)
        if not rl:
            continue
        ru = rangos(i.get("universo", ""), EDAD_UNI)
        if not ru:
            continue
        nums_l = {x for t in rl for x in t}
        nums_u = {x for t in ru for x in t}
        if not (nums_l & nums_u):
            choques += 1
            print(f"  ⛔ {i['key']}: «{i['label']}» contra «{i['universo']}»")
    print(f"  {'✅ ninguno' if not choques else f'⛔ {choques} sin resolver'}")

    # y ninguna definición puede prometer una proporción si el dato pasa de 100
    print("\n▸ ¿ALGUNA DEFINICIÓN PROMETE UNA PROPORCIÓN Y NO LO ES?")
    data = json.loads((REPO / "data.json").read_text(encoding="utf-8"))
    malos = 0
    for i in inds:
        vals = [data[s][i["key"]] for s in data if data[s].get(i["key"]) is not None]
        if not vals:
            continue
        if max(vals) > 100.5 and re.search(
                r"porcentaje|proporci|qué peso|del total", (i.get("desc") or "").lower()):
            malos += 1
            print(f"  ⛔ {i['key']} llega a {max(vals):.0f} y se describe como proporción")
    print(f"  {'✅ ninguna' if not malos else f'⛔ {malos}'}")

    if choques or malos:
        print("\n⛔ hay contradicciones sin resolver: no se escribe.")
        return 1
    if escribir:
        (REPO / "catalogo.json").write_text(
            json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ escrito {REPO / 'catalogo.json'}")
        print("⚠️ Los rótulos cambiaron: el generador de láminas de la Galería los "
              "declara por su cuenta y hay que alinearlo antes de regenerar.")
    else:
        print("\n(ensayo: no se escribió. Volvé a correr con --escribir)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--escribir" in sys.argv))
