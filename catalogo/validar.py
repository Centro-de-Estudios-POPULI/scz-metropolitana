# -*- coding: utf-8 -*-
"""
VALIDACIÓN — cada indicador contra el tabulado publicado del INE, en los dos censos.

Compara CONTEOS, no porcentajes: numerador y denominador municipio por municipio.
Un porcentaje puede coincidir por casualidad; dos conteos, no.

Las columnas de los Excel se ubican POR NOMBRE dentro del bloque del año, nunca
por posición: el ancho del bloque cambia entre hojas y entre años (la hoja 6 trae
4 categorías en 2012 y 3 en 2024) y contar columnas compara el total de un año
contra el numerador de otro.
"""
import pathlib, csv, sys
import pandas as pd, numpy as np
import lector
from lector import norm

AQUI = pathlib.Path(__file__).parent
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

# indicador -> (archivo, hoja, categorías 2024, categorías 2012)
# Si las categorías difieren entre años es porque el cuestionario cambió; se
# declara explícitamente en vez de asumir que son las mismas.
CASOS = [
 ("pct_agua_caneria",       "servicios_basicos", "4",  ["tiene caneria de red"], ["tiene caneria de red"]),
 ("pct_agua_interior",      "servicios_basicos", "6",  ["por caneria dentro"], ["por caneria dentro"]),
 ("pct_electricidad",       "servicios_basicos", "1",  ["tiene"], ["tiene"]),
 ("pct_elec_red",           "servicios_basicos", "3",  ["servicio publico"], ["red de empresa"]),
 ("pct_panel_solar",        "servicios_basicos", "3",  ["panel solar"], ["panel solar"]),
 ("pct_motor_propio",       "servicios_basicos", "3",  ["motor propio"], ["motor propio"]),
 ("pct_alcantarillado",     "servicios_basicos", "9",  ["tiene"], ["tiene"]),
 ("pct_camara_septica",     "servicios_basicos", "10", ["camara septica"], ["camara septica"]),
 ("pct_pozo_ciego",         "servicios_basicos", "10", ["pozo ciego"], ["pozo ciego"]),
 ("pct_servicio_sanitario", "servicios_basicos", "8",  ["uso privado", "uso compartido"],
                                                       ["uso privado", "uso compartido"]),
 ("pct_gas_garrafa",        "servicios_basicos", "12", ["gas en garrafa"], ["gas en garrafa"]),
 ("pct_gas_red",            "servicios_basicos", "12", ["gas por caneria", "gas domiciliario"],
                                                       ["gas domiciliario", "gas por caneria"]),
 ("pct_lena_guano",         "servicios_basicos", "12", ["lena", "guano"], ["lena", "guano"]),
 # ⚠️ El tabulado rotula el bloque 2012 con el vocabulario de 2024: la columna se
 # llama "Carro basurero", no "servicio público de recolección" como en el
 # cuestionario de 2012. Las categorías del INE no siguen al cuestionario del año.
 ("pct_basura_formal",      "servicios_basicos", "13", ["basurero publico", "carro basurero"],
                                                       ["basurero publico", "carro basurero"]),
 ("pct_basura_quema",       "servicios_basicos", "13", ["queman"], ["queman"]),
 ("pct_basura_entierra",    "servicios_basicos", "13", ["entierran"], ["entierran"]),
 ("pct_pared_ladrillo",     "vivienda_hogar",    "8",  ["ladrillo"], ["ladrillo"]),
 ("pct_pared_adobe",        "vivienda_hogar",    "8",  ["adobe"], ["adobe"]),
 ("pct_pared_madera",       "vivienda_hogar",    "8",  ["madera"], ["madera"]),
 ("pct_techo_calamina",     "vivienda_hogar",    "9",  ["calamina"], ["calamina"]),
 ("pct_techo_teja",         "vivienda_hogar",    "9",  ["teja"], ["teja"]),
 ("pct_techo_losa",         "vivienda_hogar",    "9",  ["losa"], ["losa"]),
 ("pct_techo_paja",         "vivienda_hogar",    "9",  ["paja"], ["paja"]),
 ("pct_piso_tierra",        "vivienda_hogar",    "10", ["tierra"], ["tierra"]),
 ("pct_piso_cemento",       "vivienda_hogar",    "10", ["cemento"], ["cemento"]),
 ("pct_monoambiente",       "vivienda_hogar",    "11", ["1 cuarto"], ["1 cuarto"]),
 ("pct_cocina_exclusiva",   "vivienda_hogar",    "16", ["tiene"], ["tiene"]),
 ("pct_viv_propia",         "vivienda_hogar",    "17", ["propia"], ["propia"]),
 ("pct_viv_alquilada",      "vivienda_hogar",    "17", ["alquilada"], ["alquilada"]),

 # ── AMPLIACIÓN 2026-08-13 ────────────────────────────────────────────────────
 # ★ TIC: hoja de DOS EJES (dispositivo × tiene/no tiene) ⇒ tuplas.
 #   ⚠️ Los rótulos CAMBIAN entre censos y no por capricho: 2012 dice "radio" y
 #   2024 "radio o equipo de sonido"; 2012 "computadora" y 2024 "computadora,
 #   laptop o tablet". Y 2012 NO desagrega internet fijo/móvil, TV cable,
 #   telefonía fija ni celular por separado — que es exactamente por lo que esos
 #   indicadores van VACÍOS en 2012 y no en 0%.
 ("pct_radio",         "tic", "1", [("radio o equipo de sonido", "tiene")], [("radio", "tiene")]),
 ("pct_computadora",   "tic", "1", [("computadora, laptop o tablet", "tiene")], [("computadora", "tiene")]),
 ("pct_internet",      "tic", "1",
    [('servicio de internet "internet fijo en la vivienda" o "internet movil megas o datos "', "tiene")],
    [("servicio de internet", "tiene")]),
 ("pct_telefonia",     "tic", "1", [("servicio de telefonia fija o telefono celular", "tiene")],
                                   [("servicio de telefonia fija o celular", "tiene")]),
 ("pct_internet_fijo", "tic", "1", [("internet fijo en la vivienda", "tiene")], None),
 ("pct_internet_movil","tic", "1", [("internet movil mega o datos", "tiene")], None),
 ("pct_tv_cable",      "tic", "1", [("servicio de tv cable o satelital", "tiene")], None),
 ("pct_telefono_fijo", "tic", "1", [("servicio de telefonia fija", "tiene")], None),
 ("pct_celular",       "tic", "1", [("telefono celular", "tiene")], None),
 # ── medios de transporte ──
 # ⚠️ El INE escribe "cuatratrack" en 2024 y "cuadratrack" en 2012: es un typo
 #    del propio archivo, no una categoría distinta.
 ("pct_bicicleta", "equipamiento_hogar", "1", [("bicicleta", "tiene")], [("bicicleta", "tiene")]),
 ("pct_auto",      "equipamiento_hogar", "1", [("vehiculo automotor", "tiene")], [("vehiculo automotor", "tiene")]),
 ("pct_moto",      "equipamiento_hogar", "1", [("motocicleta o cuatratrack", "tiene")],
                                              [("motocicleta o cuadratrack", "tiene")]),
 ("pct_bote",      "equipamiento_hogar", "1", [("deslizador, balsa, canoa o bote", "tiene")],
                                              [("deslizador, balsa, canoa o bote", "tiene")]),
 # ── tipo de vivienda y agua ──
 ("pct_departamento",     "vivienda_hogar", "7", ["departamento"], ["departamento"]),
 ("pct_choza",            "vivienda_hogar", "7", ["choza, pahuichi"], None),
 ("pct_agua_lote",        "servicios_basicos", "6",
    ["por caneria fuera de la vivienda pero dentro del lote o terreno"],
    ["por caneria fuera de la vivienda pero dentro del lote o terreno"]),
 # ⚠️ Las categorías de procedencia del agua CAMBIAN de nombre y de corte entre
 #    censos: 2012 dice "pozo o noria con/sin bomba" donde 2024 dice "pozo
 #    excavado o perforado", y 2012 junta "lluvia, río, vertiente, acequia" en
 #    una sola categoría que 2024 abre en tres. Por eso van declaradas aparte.
 # ⚠️ 2012 va sin dato A PROPÓSITO: su categoría "lluvia, río, vertiente,
 #    acequia" mezcla fuentes protegidas con no protegidas, así que el indicador
 #    no es decidible en ese censo. Ver NO_SEPARABLE en motor.py.
 ("pct_agua_no_mejorada", "servicios_basicos", "5",
    ["pozo no protegido o sin bomba", "rio, acequia o vertiente no protegida",
     "carro repartidor aguatero"],
    None),
 ("pct_agua_pozo",        "servicios_basicos", "5",
    ["pozo excavado o perforado con bomba", "pozo no protegido o sin bomba"],
    ["pozo o noria con bomba", "pozo o noria sin bomba"]),

 # ── TANDA 2 (2026-08-13): el resto del bloque de vivienda ───────────────────
 # procedencia del agua
 ("pct_agua_pileta",     "servicios_basicos", "5", ["pileta publica"], ["pileta publica"]),
 ("pct_agua_carro",      "servicios_basicos", "5", ["carro repartidor aguatero"],
                                                   ["carro repartidor aguatero"]),
 ("pct_agua_pozo_bomba", "servicios_basicos", "5", ["pozo excavado o perforado con bomba"],
                                                   ["pozo o noria con bomba"]),
 # ⚠️ río y lluvia NO son separables en 2012 (van fundidos en una categoría)
 ("pct_agua_rio",        "servicios_basicos", "5", ["rio, acequia o vertiente no protegida"], None),
 ("pct_agua_lluvia",     "servicios_basicos", "5", ["cosecha de agua de lluvia"], None),
 # ⚠️ 2012 abre en CUATRO lo que 2024 da en tres: separa "por cañería fuera de
 #    la vivienda, del lote o terreno", que en 2024 cae en "no se distribuye".
 ("pct_agua_sin_caneria","servicios_basicos", "6", ["no se distribuye por caneria"],
    ["no se distribuye por caneria", "por caneria fuera de la vivienda, del lote o terreno"]),
 # sanitario
 ("pct_sanitario_exclusivo",  "servicios_basicos", "8", ["uso privado"], ["uso privado"]),
 ("pct_sanitario_compartido", "servicios_basicos", "8", ["uso compartido"], ["uso compartido"]),
 ("pct_sin_sanitario",        "servicios_basicos", "8", ["no tiene"], ["no tiene"]),
 # ⚠️ 2012 desagrega en calle / quebrada-río / lago, que 2024 junta en "superficie"
 ("pct_desague_superficie",   "servicios_basicos", "10", ["superficie"],
    ["a la calle", "a la quebrada, rio", "a un lago, laguna, curichi"]),
 # energía y cocina
 ("pct_sin_energia", "servicios_basicos", "1",  ["no tiene"], ["no tiene"]),
 ("pct_no_cocina",   "servicios_basicos", "12", ["no cocina"], ["no cocina"]),
 # residuos
 ("pct_basura_carro",      "servicios_basicos", "13", ["carro basurero"], ["carro basurero"]),
 ("pct_basura_contenedor", "servicios_basicos", "13", ["contenedor"], ["contenedor"]),
 # tipología de hogar (sólo 2024: 2012 no la trae derivada)
 # `pct_hogar_unipersonal` se valida en validar_persona.py (allí se calcula)
 ("pct_hogar_nuclear",      "vivienda_hogar", "19", ["nuclear"], None),
 ("pct_hogar_monoparental", "vivienda_hogar", "19", ["monoparental"], None),
 ("pct_hogar_extendido",    "vivienda_hogar", "19", ["extendido"], None),
 ("pct_hogar_compuesto",    "vivienda_hogar", "19", ["compuesto"], None),
 # materiales y espacio
 ("pct_revoque",        "vivienda_hogar", "8",  ["si tiene revoque"], ["si tiene revoque"]),
 # ⚠️ El motor suma cerámica Y mosaico/baldosa bajo el nombre `pct_piso_ceramica`
 #    (ver REGLAS en motor.py); el INE los publica separados. Y 2012 rotula
 #    "cerámica" a secas, sin "porcelanato".
 ("pct_piso_ceramica",  "vivienda_hogar", "10", ["ceramica, porcelanato"], ["ceramica"]),
 ("pct_piso_mosaico",   "vivienda_hogar", "10", ["mosaico, baldosa"], ["mosaico, baldosa"]),
 # ★ El glosario del INE define "alto" como relación personas/dormitorios MAYOR
 #   A TRES, que es exactamente nuestra regla. Un intento previo sumaba también
 #   "medio" y por eso daba 0/343: el fallo era del CASO, no del indicador.
 ("pct_hacinamiento",   "vivienda_hogar", "14", ["con hacinamiento alto"],
                                                ["con hacinamiento alto"]),
 # tenencia
 ("pct_viv_anticretico", "vivienda_hogar", "17", ["anticretico"], ["anticretico"]),
 # ⚠️ El motor junta prestada Y cedida en `prestada_cedida`; el INE los separa.
 ("pct_viv_prestada",    "vivienda_hogar", "17", ["prestada por parientes o amigos"],
                                             ["prestada por parientes o amigos"]),
 ("pct_viv_cedida",      "vivienda_hogar", "17", ["cedida por servicios"],
                                             ["cedida por servicios"]),
 # ⚠️ `pct_vivienda_desocupada` NO entra: su denominador son TODAS las viviendas
 #    particulares y este validador divide por las ocupadas. Necesita un caso con
 #    denominador propio; queda pendiente.
 # tenencia de televisor (la hoja de TIC)
 ("pct_televisor", "tic", "1", [("televisor", "tiene")], [("televisor", "tiene")]),
 ("pct_carreta",   "equipamiento_hogar", "1", [("carreta o carreton", "tiene")],
                                              [("carreta o carreton", "tiene")]),

 # ── 2026-08-15: los dos indicadores de HOGAR del bloque emigración/mortalidad ──
 # Salen de este motor (su denominador son las viviendas ocupadas), pero no
 # tenían caso cableado, así que quedaban sin contrastar igual que el resto del
 # bloque. El de emigrantes por país y la tasa de mortalidad —cuyo denominador es
 # otro— se validan aparte, en `validar_otros.py`.
 ("pct_con_emigrante",   "emigracion_internacional", "1", ["con emigrantes"],
                                                          ["con emigrantes"]),
 ("pct_hogar_fallecido", "mortalidad", "1", ["con personas fallecidas declaradas"],
                                            ["con personas fallecidas declaradas"]),
]

def leer(arch, hoja, cats, anio):
    """(total, numerador) por municipio, apoyado en el LECTOR GENÉRICO.

    Antes acá vivía un lector propio con las columnas cableadas a la disposición
    de `servicios_basicos`. Al pasar a `lector.abrir` la misma tabla de casos
    sigue dando 100%, y además queda una sola implementación para las 143 hojas.
    """
    h = lector.abrir(arch, hoja)
    if h is None or h.error or anio not in h.anios:
        return None
    c_tot = h.total(anio)
    if c_tot is None:
        return None
    # Las categorías se buscan de a una y se SUMAN (unión): `pct_servicio_sanitario`
    # es "uso privado" + "uso compartido".
    # ★ Si una entrada es una TUPLA, sus patrones se cruzan (AND). Hace falta en
    #   las hojas de dos ejes como `tic/1`, donde la columna se identifica por
    #   dispositivo Y respuesta: ("telefono celular", "tiene").
    idx = sorted({j for c in cats
                  for j in h.columnas(anio, list(c) if isinstance(c, tuple) else [c])})
    idx = [j for j in idx if j != c_tot]
    if not idx:
        return ("SIN_CATEGORIA", h.categorias(anio)[:10])
    return {k: (float(f[c_tot]), sum(float(f[j] or 0) for j in idx))
            for k, f in h.filas.items() if len(f) > c_tot and f[c_tot] is not None}

sp = list(csv.DictReader(open(SPINE, encoding="utf-8")))
clave = {}
for r in sp:
    for nm in {norm(r["nombre_censo"]), norm(r["nombre"])}:
        clave[(norm(r["dpto"]), nm)] = r["cod_ine"]

res = {a: pd.read_csv(AQUI / f"municipal_{a}.csv", index_col=0, dtype={0: str})
       for a in (2024, 2012)}
for a in res:
    res[a].index = res[a].index.astype(str).str.zfill(6)

print(f"{'indicador':<26}{'2024':>18}{'2012':>18}")
print("=" * 62)
resumen = {2024: [0, 0], 2012: [0, 0]}
problemas = []
for ind, arch, hoja, c24, c12 in CASOS:
    fila = f"{ind:<26}"
    for anio, cats in ((2024, c24), (2012, c12)):
        # `None` = ese censo no publica la categoría (p. ej. el celular por
        # separado en 2012). No es un fallo: es una ausencia declarada.
        if cats is None:
            fila += f"{'no existe':>18}"; continue
        ine = leer(arch, hoja, cats, anio)
        if ine is None:
            fila += f"{'sin año':>18}"; continue
        if isinstance(ine, tuple):
            fila += f"{'sin categoría':>18}"
            problemas.append((ind, anio, ine[1][:8])); continue
        r = res[anio]
        ok = tot = 0
        for k, (t_ine, n_ine) in ine.items():
            ci = clave.get(k)
            if ci is None or ci not in r.index: continue
            # un indicador declarado NO SEPARABLE en este censo llega vacío: no
            # es un fallo, es una ausencia deliberada y no debe contarse
            if pd.isna(r.at[ci, ind]):
                continue
            tot += 1
            t_mic = r.at[ci, "n_viviendas"]
            n_mic = round(r.at[ci, ind] / 100 * t_mic)
            if abs(t_mic - t_ine) < 0.5 and abs(n_mic - n_ine) <= 1:
                ok += 1
        resumen[anio][0] += ok; resumen[anio][1] += tot
        marca = "✓" if ok == tot else "✗"
        fila += f"{marca + ' ' + str(ok) + '/' + str(tot):>18}"
    print(fila)

print("=" * 62)
for a in (2024, 2012):
    ok, tot = resumen[a]
    print(f"  {a}: {ok}/{tot} comparaciones municipio×indicador idénticas al registro"
          f"  ({100*ok/tot if tot else 0:.1f}%)")
if problemas:
    print("\n  categorías no encontradas en el encabezado:")
    for ind, anio, cols in problemas:
        print(f"    {ind} ({anio}) — hay: {cols}")
