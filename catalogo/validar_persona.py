# -*- coding: utf-8 -*-
"""
VALIDACIÓN DEL BLOQUE DE PERSONAS contra los tabulados del INE, en los dos censos.

Estas hojas son más difíciles que las de vivienda: el encabezado tiene TRES
niveles (año → categoría → Total/Hombres/Mujeres) con celdas combinadas, y la
fila donde empieza cada nivel cambia de archivo en archivo. El lector los
detecta en vez de suponerlos:
  · se busca la fila donde se repite "Total/Hombres/Mujeres" → es el nivel de sexo
  · las dos filas de arriba son categoría y año, y se rellenan hacia la derecha
    (las celdas combinadas sólo traen valor en la primera columna del bloque)
  · el bloque de conteos termina donde empieza "DISTRIBUCIÓN PORCENTUAL"
"""
import pathlib, unicodedata, csv, re
import pandas as pd, numpy as np, openpyxl

AQUI = pathlib.Path(__file__).parent
TAB = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\Retrato_Censal_2024\Censo2024_Tabulados")
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

# ⚠️ UNA SOLA NORMALIZACIÓN PARA TODO. Antes había una acá y otra en el lector:
#    ésta convertía el guion ASCII en espacio y la del lector no, así que las
#    claves de la espina y las filas de la hoja se escribían distinto y los TRES
#    TIOC (Raqaypampa, Jatun Ayllu Yura, Territorio Indígena Multiétnico) nunca
#    se cruzaban — las hojas quedaban en 340 de 343 sin que nada fallara.
from lector import norm

def rellenar(fila, hasta):
    out, ult = [], ""
    for i in range(hasta):
        v = fila[i] if i < len(fila) else None
        if v not in (None, ""):
            ult = norm(v)
        out.append(ult)
    return out

_cache = {}
def leer(arch, hoja):
    """{(año, categoría): {(dpto,mun): (col_total)}} — devuelve columnas y filas."""
    if (arch, hoja) in _cache:
        return _cache[(arch, hoja)]
    wb = openpyxl.load_workbook(TAB / f"{arch}.xlsx", read_only=True, data_only=True)
    ws = wb[hoja]
    cab = list(ws.iter_rows(min_row=1, max_row=10, values_only=True))
    ancho = max(len(f) for f in cab)
    # fila de sexo: la que repite Total/Hombres/Mujeres
    rs = None
    for i, f in enumerate(cab):
        v = [norm(c) for c in f if c]
        if v.count("hombres") >= 2 and v.count("mujeres") >= 2:
            rs = i
    if rs is None or rs < 2:
        # ── variante de DOS niveles (año → categoría, sin corte por sexo).
        #    Es el formato de salud/2, donde además las categorías CAMBIAN entre
        #    censos: 2012 trae "Seguro de salud privado" y 2024, en su lugar,
        #    "Atención médica en domicilio".
        ry = None
        for i, f in enumerate(cab):
            if sum(1 for c in f if str(c).strip() in ("2001", "2012", "2024")) >= 2:
                ry = i
        if ry is None or ry + 1 >= len(cab):
            wb.close(); _cache[(arch, hoja)] = None; return None
        fin = ancho
        for f in cab:
            for i, c in enumerate(f):
                if i >= 7 and c and "PORCENTAJE" in str(c).upper():
                    fin = min(fin, i)
        años = rellenar(cab[ry], fin)
        cats = [norm(c) for c in cab[ry + 1][:fin]] + [""] * max(0, fin - len(cab[ry + 1]))
        cols = {}
        for i in range(fin):
            a = re.search(r"\b(2001|2012|2024)\b", años[i] or "")
            if a and cats[i]:
                cols[(int(a.group(1)), cats[i])] = i
        filas, ctx = {}, None
        for f in ws.iter_rows(min_row=ry + 2, values_only=True):
            if f[2] and str(f[2]).startswith("Municipio"):
                ctx = (norm(f[3]), norm(f[5]))
            if ctx and f[6] and norm(f[6]) == ctx[1]:
                filas[ctx] = f
        wb.close()
        _cache[(arch, hoja)] = (cols, filas)
        return _cache[(arch, hoja)]
    # fin del bloque de conteos
    # ⚠️ Buscar sólo a partir de la columna 7: el subtítulo de la fila 4 dice
    #    "(En número y porcentaje)" en la columna 1, y tomarlo como inicio de la
    #    sección de porcentajes deja `fin = 1` y ninguna columna detectada.
    fin = ancho
    for f in cab:
        for i, c in enumerate(f):
            if i >= 7 and c and "PORCENTUAL" in str(c).upper():
                fin = min(fin, i)
    años = rellenar(cab[rs - 2], fin)
    cats = rellenar(cab[rs - 1], fin)
    sexo = [norm(c) for c in cab[rs][:fin]] + [""] * max(0, fin - len(cab[rs]))
    cols = {}
    for i in range(fin):
        a = re.search(r"\b(2001|2012|2024)\b", años[i] or "")
        if a and sexo[i] == "total":
            cols[(int(a.group(1)), cats[i])] = i
    filas, ctx = {}, None
    for f in ws.iter_rows(min_row=rs + 2, values_only=True):
        if f[2] and str(f[2]).startswith("Municipio"):
            ctx = (norm(f[3]), norm(f[5]))
        if ctx and f[6] and norm(f[6]) == ctx[1]:
            filas[ctx] = f
    wb.close()
    _cache[(arch, hoja)] = (cols, filas)
    return _cache[(arch, hoja)]

# indicador nuestro -> (archivo, hoja, categorías del INE, denominador, modo)
#   modo "conteo"      compara numerador y denominador
#   modo "tasa"        la hoja publica la TASA, no el conteo (educación 1 y 2)
#   modo "tasa_compl"  ídem, pero nuestro indicador es el complemento
E, C, S = "educacion", "economia", "salud"
CASOS = [
 ("pct_edu_ninguno",    E, "3", ["ninguno"],    "total poblacion", "conteo"),
 ("pct_edu_primaria",   E, "3", ["primaria"],   "total poblacion", "conteo"),
 ("pct_edu_secundaria", E, "3", ["secundaria"], "total poblacion", "conteo"),
 ("pct_edu_superior",   E, "3", ["superior"],   "total poblacion", "conteo"),
 ("pct_analfabetismo",   E, "1", ["tasa de alfabetismo"], "poblacion", "tasa_compl"),
 ("pct_asistencia_4_17", E, "2", ["tasa de asistencia"],  "poblacion", "tasa"),
 # nivel alcanzado: secundaria o más = secundaria + superior (mismo denominador
 # que los `pct_edu_*`, que ya validan al 343/343)
 ("pct_secundaria_mas", E, "3", ["secundaria", "superior"], "total poblacion", "conteo"),
 ("pct_catocu_cuenta_propia",     C, "4", ["trabajadora or por cuenta propia"], "total", "conteo"),
 ("pct_catocu_asalariado_amplio", C, "4", ["empleada o u obrera o"],            "total", "conteo"),
 ("pct_catocu_cooperativista",    C, "4", ["cooperativista"],                   "total", "conteo"),
 ("pct_catocu_empleador",         C, "4", ["empleadora or o socia o"],          "total", "conteo"),
 ("pct_catocu_familiar",          C, "4", ["trabajadora or familiar"],          "total", "conteo"),
 ("pct_ocu_profesionales", C, "6", ["directores y gerentes",
                                    "profesionales cientificos",
                                    "tecnicos de nivel medio"], "total", "conteo"),
 ("pct_ocu_no_calificado", C, "6", ["trabajadores no calificados"], "total", "conteo"),
 ("pct_rama_agricultura",  C, "9", ["agricultura, ganaderia"],        "total", "conteo"),
 ("pct_rama_mineria",      C, "9", ["explotacion de minas"],          "total", "conteo"),
 ("pct_rama_manufactura",  C, "9", ["industrias manufactureras"],     "total", "conteo"),
 ("pct_rama_construccion", C, "9", ["construccion"],                  "total", "conteo"),
 ("pct_rama_comercio",     C, "9", ["venta al por mayor"],            "total", "conteo"),
 ("pct_rama_transporte",   C, "9", ["transporte y almacenamiento"],   "total", "conteo"),
 ("pct_rama_alojamiento",  C, "9", ["actividades de alojamiento"],    "total", "conteo"),
 ("pct_rama_adm_publica",  C, "9", ["administracion publica"],        "total", "conteo"),
 ("pct_rama_ensenanza",    C, "9", ["ensenanza"],                     "total", "conteo"),
 ("pct_rama_salud",        C, "9", ["actividades de atencion de la salud"], "total", "conteo"),
 # ── sectores: agrupaciones de las mismas ramas que ya validan una por una ──
 ("pct_sector_primario",   C, "9", ["agricultura, ganaderia", "explotacion de minas"],
                                   "total", "conteo"),
 ("pct_sector_secundario", C, "9", ["industrias manufactureras",
                                    "suministro de electricidad", "suministro de agua",
                                    "construccion"], "total", "conteo"),
 # ── salud: los rótulos cambian entre censos, así que se declaran los dos
 #    (el buscador toma el que exista en el año que corresponda)
 ("pct_salud_publica", S, "2", ["establecimiento de salud publico",
                                "puesto/centro/hospital"],       "poblacion", "conteo"),
 ("pct_salud_caja",    S, "2", ["caja de salud"],                "poblacion", "conteo"),
 ("pct_salud_privada", S, "2", ["establecimiento de salud privado",
                                "consultorio/clinica/hospital"], "poblacion", "conteo"),
 ("pct_salud_tradic",  S, "2", ["medico tradicional",
                                "medica o tradicional"],         "poblacion", "conteo"),
 ("pct_salud_autome",  S, "2", ["farmacia o se automedica",
                                "farmacia sin receta"],          "poblacion", "conteo"),
 ("pct_salud_casera",  S, "2", ["soluciones caseras",
                                "remedios caseros"],             "poblacion", "conteo"),
 # ★ Se calcula en motor_persona.py (el motor de vivienda no conoce el
 #   parentesco) pero se valida contra la hoja de VIVIENDA, que es donde el INE
 #   publica la tipología de hogar. Sólo se pudo cablear al migrar este bucle al
 #   lector genérico: el lector viejo no sabía leer esta hoja.
 ("pct_hogar_unipersonal", "vivienda_hogar", "19", ["hogar unipersonal"], "total", "pct_aprox"),
]

# ── AMPLIACIÓN 2026-08-13: hojas que publican EL VALOR, no el conteo ─────────
# Demografía es el grupo más grande sin validar y el que abre el Atlas. Estas
# hojas del INE ya traen calculado el índice, así que se comparan de frente
# contra el nuestro (modo "valor") en vez de reconstruir numerador/denominador.
P = "poblacion"
CASOS_VALOR = [
 ("indice_masculinidad",   P, "6",  "indice de masculinidad", 0.05),
 ("edad_mediana",          P, "7",  "total", 0.05),
 ("indice_juventud",       P, "9",  "total", 0.05),
 ("indice_envejecimiento", P, "10", "total", 0.05),
 ("razon_dependencia",     P, "14", "total", 0.05),
 # ── EDUCACIÓN Y SALUD (2026-08-13) ──
 # ⚠️ PENDIENTES, y el motivo es concreto: `educacion/4` y `salud/6` traen DOS
 #    bloques —el conteo de población y el indicador ya calculado— y el patrón
 #    "total" cae en el primero, así que compara años de estudio contra una
 #    población. Hace falta que `columnas()` sepa elegir el bloque (o declarar
 #    la ruta completa, p. ej. ("anos promedio de estudio", 2024, "total")).
 #    Se dejan comentados para no ensuciar el resultado con un fallo de cableado
 #    que se confundiría con una divergencia real de definición.
 ("prom_anios_estudio",    E, "4",  ["anos promedio de estudio", "total"], 0.05),
 ("paridez_media",         S, "6",  ["paridez media"], 0.05),
 # ★ La brecha del INE es de ALFABETISMO (hombres − mujeres) y la nuestra de
 #   ANALFABETISMO (mujeres − hombres): son el MISMO número, porque
 #   (H_alf − M_alf) = (M_analf − H_analf). No hay que invertir el signo.
 ("brecha_alfabetismo",    E, "1",  "brecha hombres - mujeres", 0.05),
]
# ── y las que publican CONTEOS de población ──
# ⚠️ acá van los nombres del MOTOR (`poblacion`, `n_mujeres`), no los del
#    catálogo: este validador lee los CSV crudos, sin pasar por `alias`.
CASOS_CONTEO_POB = [
 ("poblacion",   P, "1", ["total"]),
 ("n_mujeres",   P, "1", ["mujeres"]),
 ("pob_hombres", P, "1", ["hombres"]),
]

# ── IDIOMAS: el tabulado tiene OTRA disposición y necesita su propio lector ──
# `idiomas_1` no lleva la columna vacía inicial de los demás archivos, así que
# todo está corrido un lugar (NIVEL en f[1], no en f[2]), y el corte por sexo no
# va en columnas sino en FILAS: cada municipio ocupa tres, y la del total repite
# el nombre del municipio en la columna SEXO.
# El encabezado tiene tres niveles: año (fila 4) → grupo (fila 5) → idioma
# (fila 6). El bloque "Idiomas oficiales" es el que define qué cuenta como
# originario: son los códigos 1..37 del microdato, más Afroboliviano,
# Joaquiniano y "Otras declaraciones" en 2024.
def leer_idiomas():
    """{(año, clave): {(dpto, mun): valor}} con clave en {total, castellano, oficiales}."""
    wb = openpyxl.load_workbook(TAB / "idiomas_1.xlsx", read_only=True, data_only=True)
    ws = wb["1"]
    cab = list(ws.iter_rows(min_row=1, max_row=8, values_only=True))
    ancho = max(len(f) for f in cab)
    años = rellenar(cab[4], ancho)
    grupos = rellenar(cab[5], ancho)
    idioma = [norm(c) for c in cab[6][:ancho]] + [""] * max(0, ancho - len(cab[6]))
    cols = {}
    for i in range(6, ancho):
        a = re.search(r"\b(2012|2024)\b", años[i] or "")
        if not a:
            continue
        a = int(a.group(1))
        g = grupos[i]
        if g == "total":
            cols[(a, "total")] = [i]
        # ⚠️ NO usar `startswith("idioma")`: matchea también "Idiomas
        #    extranjeros" y entonces el bloque de oficiales se lleva puestos a
        #    los hablantes de idioma extranjero. Con ese error sólo validaban
        #    los municipios que no tienen ninguno (71 de 343). La palabra
        #    "oficial" aparece únicamente en el grupo que buscamos, y sirve para
        #    los dos rótulos del INE: "Idiomas oficiales" (2012) e "Idioma
        #    oficiales" (2024, con el desliz de número incluido).
        elif "oficial" in g:
            cols.setdefault((a, "oficiales"), []).append(i)
            if idioma[i] == "castellano":
                cols[(a, "castellano")] = [i]
    filas = {}
    for f in ws.iter_rows(min_row=9, values_only=True):
        if not f[1] or not str(f[1]).startswith("Municipio"):
            continue
        # la fila del TOTAL del municipio es la que repite su nombre en SEXO;
        # las otras dos son Hombres y Mujeres
        if f[4] and f[5] and norm(f[5]) == norm(f[4]):
            filas[(norm(f[2]), norm(f[4]))] = f
    wb.close()
    return cols, filas


def validar_idiomas(res, clave):
    """Compara castellano y originario contra idiomas_1, cuadro 1."""
    cols, filas = leer_idiomas()
    salida = []
    for ind, calc in (("pct_idioma_castellano", lambda c, o: c),
                      # originario = oficiales − castellano, que es exactamente
                      # como lo arma el motor a partir de los códigos
                      ("pct_idioma_materno_originario", lambda c, o: o - c)):
        fila = f"{ind:<28}"
        for anio in (2024, 2012):
            i_tot = cols.get((anio, "total"))
            i_cas = cols.get((anio, "castellano"))
            i_ofi = cols.get((anio, "oficiales"))
            if not (i_tot and i_cas and i_ofi):
                fila += f"{'sin columna':>16}"; continue
            r = res[anio]
            ok = tot = 0
            for k, f in filas.items():
                cod = clave.get(k)
                if cod is None or cod not in r.index:
                    continue
                den = f[i_tot[0]]
                if den in (None, 0):
                    continue
                tot += 1
                # el denominador tiene que coincidir primero: si el universo no
                # es el mismo (población de 4+), comparar el numerador no dice nada
                d_mic = r.at[cod, "_den_" + ind]
                if pd.isna(d_mic) or abs(d_mic - float(den)) >= 0.5:
                    continue
                cas = sum(float(f[i] or 0) for i in i_cas)
                ofi = sum(float(f[i] or 0) for i in i_ofi)
                n_ine = calc(cas, ofi)
                n_mic = round(r.at[cod, ind] / 100 * d_mic) if d_mic else 0
                if abs(n_mic - n_ine) <= 1:
                    ok += 1
            salida.append((anio, ok, tot))
            fila += f"{('✓ ' if ok == tot and tot else '✗ ') + str(ok) + '/' + str(tot):>16}"
        print(fila)
    return salida


sp = list(csv.DictReader(open(SPINE, encoding="utf-8")))
clave = {}
for r in sp:
    for nm in {norm(r["nombre_censo"]), norm(r["nombre"])}:
        clave[(norm(r["dpto"]), nm)] = r["cod_ine"]

res = {}
for a in (2024, 2012):
    df = pd.read_csv(AQUI / f"personas_{a}.csv", index_col=0, dtype={0: str})
    df.index = df.index.astype(str).str.zfill(6)
    res[a] = df

def main():
  print(f"{'indicador':<28}{'2024':>16}{'2012':>16}")
  print("=" * 60)
  resumen = {2024: [0, 0], 2012: [0, 0]}
  for ind, arch, hoja, cats, den_cat, modo in CASOS:
    # ★ MIGRADO AL LECTOR GENÉRICO (2026-08-13): antes acá vivía un tercer lector
    #   propio, con la disposición de `educacion`/`economia` cableada. Con
    #   `lector.abrir` la misma tabla de casos sigue dando 100% y queda UNA sola
    #   implementación para las 143 hojas — lo que además destraba las hojas que
    #   el lector viejo no sabía leer.
    import lector as _L
    h = _L.abrir(arch, hoja)
    fila = f"{ind:<28}"
    if h is None or h.error:
        print(fila + "   no pude leer la hoja"); continue
    filas = h.filas
    for anio in (2024, 2012):
        # ⚠️ Estas hojas abren cada categoría en Total/Hombres/Mujeres. El lector
        #   devuelve LAS TRES, así que sumarlas contaba a todo el mundo por
        #   duplicado (el resultado cayó de 98% a 40,7%). Hay que quedarse con la
        #   columna del TOTAL, que es lo que hacía el lector viejo al exigir
        #   `sexo == "total"`. Las hojas sin corte por sexo no tienen ese tramo,
        #   así que se cae a la búsqueda sin él.
        def _cols(c):
            return h.columnas(anio, [c, "total"]) or h.columnas(anio, [c])
        idx = sorted({j for c in cats for j in _cols(c)})
        den = _cols(den_cat)
        ci_den = den[0] if den else h.total(anio)
        idx = [j for j in idx if j != ci_den]
        if not idx or ci_den is None:
            fila += f"{'sin columna':>16}"; continue
        r = res[anio]
        col_den = "_den_" + ind
        ok = tot = 0
        for k, f in filas.items():
            cod = clave.get(k)
            if cod is None or cod not in r.index: continue
            if len(f) <= ci_den or f[ci_den] is None: continue
            tot += 1
            d_mic = r.at[cod, col_den]
            if modo == "pct_aprox":
                # ★ El universo difiere POR CONSTRUCCIÓN, no por error: nuestros
                #   "hogares" salen de agrupar PERSONAS por vivienda y los del
                #   INE son viviendas particulares ocupadas (Sucre 92.735 vs
                #   92.531, 0,2%). Exigir que el denominador coincida al
                #   individuo es imposible acá, así que se compara el PORCENTAJE
                #   con tolerancia estrecha. Se declara caso por caso, nunca
                #   como default: aflojar el control en general escondería
                #   errores reales.
                v = 100 * sum(float(f[i] or 0) for i in idx) / float(f[ci_den])
                if pd.notna(r.at[cod, ind]) and abs(float(r.at[cod, ind]) - v) < 0.5:
                    ok += 1
                continue
            if abs(d_mic - float(f[ci_den])) >= 0.5:
                continue                       # el denominador ya no coincide
            v_ine = sum(float(f[i] or 0) for i in idx)
            if modo == "conteo":
                n_mic = round(r.at[cod, ind] / 100 * d_mic) if d_mic else 0
                if abs(n_mic - v_ine) <= 1: ok += 1
            else:
                p_mic = r.at[cod, ind]
                if modo == "tasa_compl": v_ine = 100 - v_ine
                if pd.notna(p_mic) and abs(p_mic - v_ine) < 0.05: ok += 1
        resumen[anio][0] += ok; resumen[anio][1] += tot
        fila += f"{('✓ ' if ok == tot else '✗ ') + str(ok) + '/' + str(tot):>16}"
    print(fila)

  for anio, ok, tot in validar_idiomas(res, clave):
    resumen[anio][0] += ok; resumen[anio][1] += tot

  # ── demografía: el INE publica el valor ya calculado ──
  import lector
  for ind, arch, hoja, cat, tol in CASOS_VALOR:
    fila = f"{ind:<28}"
    for anio in (2024, 2012):
        h = lector.abrir(arch, hoja)
        # ★ `cat` puede ser una LISTA de patrones, y `columnas()` los CRUZA. Es
        #   lo que hace falta en las hojas de DOS BLOQUES: `educacion/4` trae
        #   ('2024','poblacion','total') y ('2024','anos promedio de estudio',
        #   'total'), así que pedir sólo "total" caía en el primero y comparaba
        #   años de estudio contra una población.
        pat = list(cat) if isinstance(cat, (list, tuple)) else [cat]
        cols = h.columnas(anio, pat) if h and not h.error else []
        if not cols:
            fila += f"{'sin columna':>16}"; continue
        r, ok, tot = res[anio], 0, 0
        for k, f in h.filas.items():
            cod = clave.get(k)
            if cod is None or cod not in r.index or len(f) <= cols[0]:
                continue
            v = f[cols[0]]
            if v is None or pd.isna(r.at[cod, ind]):
                continue
            tot += 1
            if abs(float(r.at[cod, ind]) - float(v)) < tol:
                ok += 1
        resumen[anio][0] += ok; resumen[anio][1] += tot
        fila += f"{('✓ ' if ok == tot and tot else '✗ ') + str(ok) + '/' + str(tot):>16}"
    print(fila)

  # ── conteos de población ──
  for ind, arch, hoja, cats in CASOS_CONTEO_POB:
    fila = f"{ind:<28}"
    for anio in (2024, 2012):
        h = lector.abrir(arch, hoja)
        # ⚠️ En `poblacion/1` el bloque entero se llama "Total", así que buscar
        #    el patrón "total" devolvía además las columnas de hombres y de
        #    mujeres y las sumaba: el total daba el doble. Para el denominador
        #    hay que usar `h.total()`, que exige que sea el ÚLTIMO tramo.
        if h and not h.error:
            cols = ([h.total(anio)] if cats == ["total"]
                    else sorted({j for c in cats for j in h.columnas(anio, [c])}))
            cols = [c for c in cols if c is not None]
        else:
            cols = []
        if not cols:
            fila += f"{'sin columna':>16}"; continue
        r, ok, tot = res[anio], 0, 0
        for k, f in h.filas.items():
            cod = clave.get(k)
            if cod is None or cod not in r.index or len(f) <= cols[0]:
                continue
            v = sum(float(f[j] or 0) for j in cols)
            tot += 1
            if abs(float(r.at[cod, ind]) - v) <= 1:
                ok += 1
        resumen[anio][0] += ok; resumen[anio][1] += tot
        fila += f"{('✓ ' if ok == tot and tot else '✗ ') + str(ok) + '/' + str(tot):>16}"
    print(fila)

  print("=" * 60)
  for a in (2024, 2012):
    ok, tot = resumen[a]
    print(f"  {a}: {ok}/{tot} idénticas al registro ({100*ok/tot if tot else 0:.1f}%)")


if __name__ == "__main__":
    main()
