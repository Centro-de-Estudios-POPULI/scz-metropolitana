# -*- coding: utf-8 -*-
"""LAS TARJETAS DEL ATLAS DICEN QUÉ MUESTRA EL MAPA.

Reescribe `desc` y agrega `universo` a los 215 indicadores del
`catalogo.json` del Atlas Socioeconómico Municipal.

★ POR QUÉ HACÍA FALTA. El Atlas publica descripciones que quedaron de ANTES de
  que el commit `f42a389` recalculara los 136 indicadores desde el microdato
  validado: describen el cálculo viejo. El caso que lo resume es
  `pct_electricidad`, cuya tarjeta dice «servicio público de energía eléctrica»
  cuando el dato mide CUALQUIER fuente —red, generador o panel solar—. Los
  valores se corrigieron y los textos no.

★ DE DÓNDE SALEN LAS NUEVAS. De las 267 definiciones que se redactaron una por
  una para el tablero metropolitano, con esta regla:
    1. Una frase. Empieza por el SUJETO que se cuenta, no por el título.
    2. Dice qué entra y qué no cuando el recorte no es obvio.
    3. Si el número tiene una lectura va al final, tras punto y coma o guion.
    4. NADA de variables, denominadores ni fórmulas: el universo viaja aparte.
    5. Se escribe contra la EXPRESIÓN REAL del catálogo, no contra el título.

★ POR QUÉ SE PUEDEN REUSAR — MEDIDO, NO SUPUESTO. El `data.json` del Atlas lo
  genera `generar_atlas.py` desde los MISMOS motores que alimentan el tablero
  metropolitano. Comprobado clave por clave: 1.890 pares de valores (9
  municipios × 210 claves comunes) y **cero diferencias**. Si el número es el
  mismo, la definición que lo describe también lo es.

⚠️ PERO NO TODAS SE COPIAN TAL CUAL. Seis definiciones afirman algo que es
   cierto en la región metropolitana y falso en el país. Se midieron sobre el
   `data.json` nacional antes de reescribirlas (ver NACIONALIZADAS abajo). Es
   el mismo error de fondo que ya mordió cuatro veces en este código: dar por
   bueno un contexto que no se volvió a comprobar al cambiar de escala.

    python catalogo/enriquecer_atlas.py            # ensayo, no escribe
    python catalogo/enriquecer_atlas.py --escribir
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
PROY = AQUI.parent.parent
REPO = PROY / "Observatorio de Presupuesto Fiscal Departamental" / "_github_atlas_fiscal"
METRO = PROY / "scz-metropolitana-gobernacion" / "docs" / "datos"

# el vocabulario del Atlas publicado no es el del catálogo: seis claves difieren
sys.path.insert(0, str(AQUI))
try:
    from alias import ATLAS
except ImportError:                       # la copia POPULI todavía no lo tenía
    ATLAS = {
        "pct_gas_natural": "pct_gas_red",
        "pct_combustible_solido": "pct_lena_guano",
        "pct_vivienda_propia": "pct_viv_propia",
        "pct_alquiler": "pct_viv_alquilada",
        "pct_tv": "pct_televisor",
        "pct_disc_cognitiva": "pct_disc_comunicar",
    }

# ── LAS QUE HAY QUE NACIONALIZAR ─────────────────────────────────────────────
# Cada una afirmaba un hecho de la región metropolitana. El reemplazo se midió
# sobre el `data.json` nacional (promedio ponderado por el universo de cada
# indicador), no se supuso:
#   · comercio    → agricultura 26,1 % > comercio 18,4 %: comercio es la SEGUNDA
#   · Chile       → sigue siendo el primer destino en el país (34,5 %), pero la
#                   frase decía «de la región» y ahora tiene que decir del país
#   · chiquitano  → quechua 16,4 % y aymara 15,6 % contra 0,9 %: en el país no
#                   es «el de mayor presencia», es un pueblo territorializado
#   · capital     → el motor dejó de cablear Santa Cruz de la Sierra y usa la
#                   capital del PROPIO departamento (`cod_dpto + "0101"`); la
#                   definición heredada seguía nombrando a Santa Cruz y en los
#                   otros ocho departamentos habría estado midiendo otra cosa
NACIONALIZADAS = {
 "pct_comercio": "Personas ocupadas en comercio al por mayor o menor; es la segunda "
                 "rama del país, después de la agricultura.",
 "pct_emi_chile": "De quienes emigraron, qué proporción está en Chile, el destino "
                  "más frecuente de la emigración boliviana.",
 "pct_chiquitano": "Personas que se autoidentifican como chiquitanas o chiquitanos, "
                   "un pueblo concentrado en la Chiquitania cruceña.",
 "dependencia_capital": "Personas ocupadas que van a trabajar a la capital de su "
                        "departamento; mide cuánto depende el municipio de esa ciudad.",
 # ⚠️ NO ES UNA NACIONALIZACIÓN: es un duplicado que hay que dejar de esconder.
 #    `tam_hogar` y `pers_x_vivienda` son el MISMO número en los 343 municipios
 #    —comprobado comparando los 215 indicadores entre sí, y son el único par
 #    idéntico—: los dos declaran `media(tot_pers)` sobre las viviendas
 #    particulares ocupadas. El Atlas los publica en dos categorías distintas y
 #    con definiciones que suenan a dos cosas («en cada hogar» / «en cada
 #    vivienda»), que es justo lo que vuelve invisible la repetición.
 #    Cuál de los dos se queda es una decisión de producto, todavía abierta;
 #    hasta que se tome, la tarjeta lo dice en vez de disimularlo.
 "pers_x_vivienda": "Cuántas personas viven, en promedio, en cada vivienda ocupada. "
                    "Es la misma cuenta que «Personas por hogar»: el censo toma "
                    "cada vivienda particular ocupada como un hogar.",
}

# ── LOS CINCO SIN UNIVERSO ───────────────────────────────────────────────────
# No tienen par en el tablero metropolitano, así que su universo se escribe acá,
# leído del `den` que ya declara el catálogo del Atlas.
UNIVERSOS = {
 "pct_analfabetismo_mujeres": "sobre las mujeres de 15 años o más",
 "tasa_participacion_fem": "sobre las mujeres en edad de trabajar (15 años o más)",
 "tasa_ocupacion_fem": "sobre las mujeres en edad de trabajar (15 años o más)",
 "pct_telefono_fijo": "sobre las viviendas particulares ocupadas",
 "pct_muertes_covid": "sobre las personas fallecidas declaradas en el período",
}

# ── UNIVERSOS QUE HEREDAMOS MAL ──────────────────────────────────────────────
# Salieron de cruzar la frase contra el TOTAL NACIONAL de la columna de
# denominador que cada indicador usa para agregar, y de leer el motor cuando la
# cuenta no cerraba. No son matices de redacción: cada uno le cambia al lector
# la magnitud que está mirando.
#
#   ⚠️ La columna de denominador se DEDUPLICA POR VALOR y queda bautizada con el
#      nombre del primer indicador que la usó. Por eso `pct_quechua` aparece
#      bajo `den_tasa_participacion`: no es un error de agregación —el vector es
#      el correcto, población de 15 años o más— es que el NOMBRE engaña. La
#      identidad de un denominador se mide por su total, no se lee de su nombre.
#
#   · Pueblos e idiomas (5) — el censo pregunta la autoidentificación desde los
#     15 años (`pct(d.indigena, res & (d.edad >= 15), …)`), y el denominador
#     suma 8.217.441 = 0,723 de la población. Decir «sobre la población» hace
#     leer «41 % de los bolivianos» donde el dato dice «41 % de los adultos».
#   · Destinos de emigración (6) — el denominador suma 329.047: son las personas
#     que EMIGRARON, no la población. «34,5 % está en Chile» es de los
#     emigrantes; sobre la población serían 2,9 %.
#   · Edad al fallecer — denominador 351.815, las muertes declaradas.
#   · Hijos fallecidos — el motor lo dice en su propia línea: «el universo son
#     los HIJOS» (denominador 9.225.710 nacidos vivos), no las mujeres.
#   · Asistencia 18–24 — denominador 1.371.345: es la franja 18 a 24, no «18 o
#     más» (que serían unos 7 millones).
#   · Chozas y departamentos — se miden sobre las viviendas OCUPADAS; la frase
#     heredada decía «todas las viviendas particulares», que es el universo de
#     `pct_vivienda_desocupada` y sólo de ése.
#   · Edad al primer hijo — mujeres que declararon esa edad, no la población.
UNIVERSOS_CORREGIDOS = {
 "pct_autoident_indigena": "sobre la población de 15 años o más",
 "pct_quechua": "sobre la población de 15 años o más",
 "pct_aymara": "sobre la población de 15 años o más",
 "pct_guarani": "sobre la población de 15 años o más",
 "pct_chiquitano": "sobre la población de 15 años o más",
 "pct_emi_argentina": "sobre las personas que emigraron al exterior",
 "pct_emi_espana": "sobre las personas que emigraron al exterior",
 "pct_emi_brasil": "sobre las personas que emigraron al exterior",
 "pct_emi_chile": "sobre las personas que emigraron al exterior",
 "pct_emi_eeuu": "sobre las personas que emigraron al exterior",
 "edad_prom_emigracion": "sobre las personas que emigraron al exterior",
 "edad_prom_fallecimiento": "sobre las personas fallecidas declaradas en el período",
 "pct_hijos_fallecidos": "sobre los hijos nacidos vivos declarados",
 "tasa_asistencia_18_24": "sobre la población de 18 a 24 años",
 "pct_choza": "sobre las viviendas particulares ocupadas",
 "pct_departamento": "sobre las viviendas particulares ocupadas",
 "edad_1er_hijo": "sobre las mujeres que declararon la edad a su primer hijo",
}

# «medido sobre X» y «sobre X» son la misma frase escrita de dos maneras; en una
# tarjeta puestas una debajo de otra se leen como si distinguieran algo.
NORMALIZA = re.compile(r"^medido sobre ", re.I)

# lo que no puede sobrevivir a la nacionalización, para que el chequeo final
# falle en vez de publicar una frase cruceña en un atlas de Bolivia
PROHIBIDO = re.compile(
    r"RMSC|metropolitan|Santa Cruz|Warnes|Montero|Cotoca|Porongo|Pail[oó]n|"
    r"La Guardia|El Torno|Colpa B|de la regi[oó]n", re.I)


def fuente_metro():
    """Las definiciones ya redactadas, tomadas de los catálogos publicados del
    tablero. Se leen los tres porque ninguno solo cubre las 215 claves."""
    src = {}
    for f in ("catalogo_municipal.json", "catalogo_manzana.json", "catalogo_tablero.json"):
        ruta = METRO / f
        if not ruta.exists():
            continue
        c = json.loads(ruta.read_text(encoding="utf-8"))
        for g in c["grupos"]:
            for i in g["indicadores"]:
                src.setdefault(i["key"], i)
    return src


def laminas():
    """Clave del Atlas → lámina de la Galería POPULI.

    ★ EL PUENTE YA EXISTÍA Y NADIE LO CRUZÓ. Cada mapa censal de la Galería se
      generó con el mismo `atlas_muni_343.topojson` y desde el mismo indicador
      que este Atlas dibuja, y su ficha declara la clave en `tags`. Son dos
      formas del mismo dato: acá se explora, allá se descarga listo para pegar
      en un informe. El enlace se arma de la clave, no de una lista a mano.

    ⚠️ NO TODOS TIENEN. La Galería tiene 135 mapas censales y el Atlas 215
      indicadores: el botón aparece sólo donde hay lámina, y el propio script
      informa cuántos quedan sin ella para que el hueco sea visible."""
    gal = PROY / "galeria-populi" / "data" / "catalogo"
    if not gal.exists():
        return {}
    por_clave = {}
    for f in sorted(gal.glob("censo-*.json")):
        j = json.loads(f.read_text(encoding="utf-8"))
        # la ficha declara el PNG que publica; si no lo declara no hay qué enlazar
        if not j.get("imagen"):
            continue
        for t in j.get("tags", []):
            por_clave.setdefault(t, j["slug"])
    return por_clave


def auditar_universos(cat):
    """La frase del universo contra el TOTAL NACIONAL del denominador que ese
    indicador usa de verdad para agregar.

    No aborta: quedan tres casos donde el denominador y la frase discrepan por
    algo que NO se arregla escribiendo mejor —hay que tocar el dato— y prefiero
    que salgan impresos cada vez que corre esto, antes que enterrarlos en un
    comentario. Ver el informe al final de la corrida."""
    dj, gj = REPO / "denominadores.json", REPO / "data.json"
    if not (dj.exists() and gj.exists()):
        return
    DN = json.loads(dj.read_text(encoding="utf-8"))
    D = json.loads(gj.read_text(encoding="utf-8"))
    orden, muni = DN["orden"], DN["municipios"]
    total = {nm: sum(muni[k][j] for k in muni if muni[k][j] is not None)
             for j, nm in enumerate(orden)}
    pob = sum(r["pob_total"] for r in D.values())

    pares = {}
    for g in cat["grupos"]:
        for i in g["indicadores"]:
            pares.setdefault((i.get("den"), i.get("universo")), []).append(i["key"])
    ambiguos = {}
    for (den, uni), ks in pares.items():
        ambiguos.setdefault(den, set()).add(uni)

    print("\n--- universo declarado contra el denominador que se usa al agregar ---")
    for den in sorted(ambiguos, key=str):
        if len(ambiguos[den]) < 2:
            continue
        t = total.get(den)
        marca = f"{t:,} ({t / pob:.3f} de la población)" if t else "sin columna propia"
        print(f"  {den}  =  {marca}")
        for (d2, uni), ks in sorted(pares.items(), key=lambda x: -len(x[1])):
            if d2 == den:
                print(f"     · {uni:<52} {len(ks):>3}  ej {ks[0]}")


def main(escribir):
    cat = json.loads((REPO / "catalogo.json").read_text(encoding="utf-8"))
    src = fuente_metro()
    LAM = laminas()
    print(f"  definiciones disponibles en el metropolitano: {len(src)}")
    print(f"  láminas censales en la Galería: {len(set(LAM.values()))}")

    cambios, sin_par, sin_universo, sin_lamina = [], [], [], []
    n = 0
    for g in cat["grupos"]:
        for ind in g["indicadores"]:
            n += 1
            k = ind["key"]
            # la lámina se busca por la clave del ATLAS: así se nombran los tags
            if LAM.get(k):
                ind["lam"] = LAM[k]
            else:
                ind.pop("lam", None)
                sin_lamina.append(k)
            s = src.get(ATLAS.get(k, k))
            if not s:
                sin_par.append(k)
                continue

            nueva = NACIONALIZADAS.get(k) or s.get("desc")
            if nueva and nueva.strip() != ind.get("desc", "").strip():
                cambios.append((k, ind.get("desc", ""), nueva))
                ind["desc"] = nueva.strip()

            uni = (UNIVERSOS_CORREGIDOS.get(k) or UNIVERSOS.get(k)
                   or s.get("universo"))
            if uni:
                ind["universo"] = NORMALIZA.sub("sobre ", uni).strip()
            else:
                sin_universo.append(k)

    print(f"  indicadores recorridos: {n}")
    print(f"  descripciones reescritas: {len(cambios)}")
    print(f"  sin par en el metropolitano: {len(sin_par)} {sin_par}")
    print(f"  sin universo: {len(sin_universo)} {sin_universo}")
    # el hueco se INFORMA, no se disimula: un botón que aparece en unos
    # indicadores y en otros no se lee como un fallo si nadie dijo cuántos son
    print(f"  con lámina en la Galería: {n - len(sin_lamina)} de {n} "
          f"· sin lámina: {len(sin_lamina)}")

    # ── CHEQUEOS QUE ABORTAN ─────────────────────────────────────────────────
    # Escribir un catálogo a medias es peor que no escribirlo: el sitio degrada
    # en silencio y el hueco no se ve hasta que alguien lee la tarjeta.
    fallos = []
    todos = [i for g in cat["grupos"] for i in g["indicadores"]]
    faltan_desc = [i["key"] for i in todos if not i.get("desc", "").strip()]
    faltan_uni = [i["key"] for i in todos if not i.get("universo", "").strip()]
    if faltan_desc:
        fallos.append(f"sin descripción: {faltan_desc}")
    if faltan_uni:
        fallos.append(f"sin universo: {faltan_uni}")
    for i in todos:
        for campo in ("desc", "universo"):
            t = i.get(campo, "")
            if PROHIBIDO.search(t):
                fallos.append(f"lenguaje metropolitano en {i['key']}.{campo}: «{t}»")
            if re.search(r"[★✓]|Verificado:|OJO|TODO", t):
                fallos.append(f"nota interna en {i['key']}.{campo}: «{t}»")

    print()
    for c in fallos:
        print(f"  ⛔ {c}")
    if fallos:
        print(f"\n⛔ {len(fallos)} problemas: NO se escribe nada.")
        return 1

    print("  ✅ 215/215 con descripción y universo · sin lenguaje regional · sin notas internas")
    auditar_universos(cat)
    print("\n--- una muestra de lo que cambia ---")
    for k, viejo, nuevo in cambios[:6]:
        print(f"\n  {k}\n    antes: {viejo[:110]}\n    ahora: {nuevo[:110]}")

    if escribir:
        (REPO / "catalogo.json").write_text(
            json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ escrito {REPO / 'catalogo.json'}")
    else:
        print("\n(ensayo: no se escribió. Volvé a correr con --escribir)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--escribir" in sys.argv))
