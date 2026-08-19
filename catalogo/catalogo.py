# -*- coding: utf-8 -*-
"""
CATÁLOGO DECLARATIVO DE INDICADORES — Atlas Metropolitano de Santa Cruz
=======================================================================

Este archivo ES la definición. No hay definiciones escondidas dentro de un
script de extracción: el motor lee de acá y calcula. Agregar un indicador es
agregar una fila, no editar código.

Cada fila declara:
    k    clave interna
    l    etiqueta visible
    u    unidad  (% · hab · viv · años · pers · h/100m · pp · ‰ · hab/ha · índice)
    d    dirección: -1 = más es peor · 0 = neutro · +1 = más es mejor
    n    nivel: "mun" (sólo municipio) · "mun+mz" (baja a manzana)
    s    admite corte por sexo
    y12  ¿hay dato 2012?  "si" · "no" · "ajuste" (existe pero requiere armonizar)
    uni  universo (clave de UNIVERSOS)
    e24  cómo se calcula con el microdato 2024
    e12  cómo se calcula con el microdato 2012 (None si no existe)
    val  hoja del tabulado del INE contra la que se valida (None si no hay)
    nota advertencias

ORIGEN DE LOS DATOS — todo se procesa desde microdato salvo lo que se marque:
    · 2024  Persona/Vivienda/Emigracion/Mortalidad CSV  (C:\\Users\\HP\\cpv2024)
    · 2012  Redatam CPV2012 343M, leído con scripts/redatam.py
    · Los tabulados del INE son CONTROL, no fuente. Única excepción: los 13 NBI,
      que hoy se leen de `pobreza.xlsx` porque replicar la metodología oficial
      es un proyecto en sí mismo (marcados fuente="tabulado").
    · El nivel MANZANA no sale del microdato y no puede salir: el microdato no
      trae identificador de manzano. Viene de las fichas del geoportal.
    · `densidad` sale de la geometría, no del censo.

★ UNIVERSO — el error que costó caro (ver docs): la cobertura de servicios se
  calcula sobre VIVIENDAS PARTICULARES OCUPADAS CON PERSONAS PRESENTES, que es
  lo que declara el INE en el título de sus cuadros. Dividir por todas las
  viviendas subestima entre 10 y 18 puntos.
"""

# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSOS. La clave está en que el mismo universo se exprese para los dos
# censos: si un universo no se puede replicar en 2012, sus indicadores no
# pueden tener columna intercensal.
# ─────────────────────────────────────────────────────────────────────────────
UNIVERSOS = {
    "viv_ocu": dict(
        label="Viviendas particulares ocupadas con personas presentes",
        e24="v01_tipoviv in 1..6 and v02_condocup in {0,1}",
        # ⚠️ 2012: el corte es POSICIONAL, no por rótulo. La categoría 5 se llama
        # "Local no destinado para vivienda" y SÍ es particular (su análoga de
        # 2024 entra en el tramo 1-6). Filtrarla por el nombre dejaba fuera
        # 12.861 viviendas y ninguna cifra cerraba.
        e12="P01 in 1..5 and P02 in {0,1}",
        n24=3_623_711, n12=2_803_982,
    ),
    "viv_part": dict(
        label="Viviendas particulares (ocupadas o no)",
        e24="v01_tipoviv in 1..6", e12="P01 in 1..5",
    ),
    "personas": dict(
        label="Toda la población empadronada",
        e24="todos los registros de Persona", e12="entidad PERSONA",
        n24=11_365_333, n12=10_059_856,
    ),
    "p6_17":  dict(label="Población de 6 a 17 años", e24="p26_edad 6..17", e12="P25 6..17"),
    "p4_5":   dict(label="Niñas y niños de 4 y 5 años", e24="p26_edad 4..5", e12="P25 4..5"),
    "p15mas": dict(label="Población de 15 años o más", e24="p26_edad >= 15", e12="P25 >= 15"),
    "p18mas": dict(label="Población de 18 años o más", e24="p26_edad >= 18", e12="P25 >= 18"),
    "p19mas": dict(label="Población de 19 años o más", e24="p26_edad >= 19", e12="P25 >= 19"),
    "p25mas": dict(label="Población de 25 años o más", e24="p26_edad >= 25", e12="P25 >= 25"),
    # ⚠️ PEA/PET NO se toman de las derivadas del INE: en 2012 la base es "10 años
    # o más" y en 2024 "7 o más". Se recalcula desde la edad con un corte común
    # de 15 años, que existe en las dos bases. Sin esto las tasas de empleo no
    # son comparables entre censos.
    "pet15":  dict(label="Población en edad de trabajar (15+, corte propio armonizado)",
                   e24="p26_edad >= 15", e12="P25 >= 15"),
    "ocupados": dict(label="Población ocupada de 15 años o más",
                     e24="p26_edad>=15 and condact_19 == 1", e12="P25>=15 and PEA==1 and P39/P40 ocupado"),
    "mef":    dict(label="Mujeres de 15 a 49 años", e24="p25_sexo==2 and p26_edad 15..49",
                   e12="P24==2 and P25 15..49"),
    "muj12":  dict(label="Mujeres de 12 años o más", e24="p25_sexo==2 and p26_edad>=12",
                   e12="P24==2 and P25>=12"),
    "hogares": dict(label="Hogares (= viviendas ocupadas con personas presentes)",
                    e24="idem viv_ocu", e12="idem viv_ocu"),
    "manzana": dict(label="Manzano censado con ficha publicada",
                    e24="ficha del geoportal", e12=None,
                    nota="Sólo 2024 y sólo urbano: 25.698 de 38.892 manzanos (66%), "
                         "que concentran el 93,8% de la población."),
}

# ─────────────────────────────────────────────────────────────────────────────
def I(k, l, u, d, g, *, n="mun", s=False, y12="si", uni="viv_ocu",
      e24=None, e12=None, val=None, nota=None, fuente="microdato"):
    return dict(k=k, l=l, u=u, d=d, g=g, n=n, s=s, y12=y12, uni=uni,
                e24=e24, e12=e12, val=val, nota=nota, fuente=fuente)


CATALOGO = []
A = CATALOGO.append

# ═══════════════════════════════════════════════════════════════════════════
G = "Demografía y estructura"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pob_total", "Población total", "hab", 0, G, n="mun+mz", s=True, uni="personas",
    e24="count(Persona)", e12="count(PERSONA)", val="poblacion/1"))
A(I("pob_hombres", "Hombres", "hab", 0, G, uni="personas",
    e24="p25_sexo==1", e12="P24==1", val="poblacion/1"))
A(I("pob_mujeres", "Mujeres", "hab", 0, G, uni="personas",
    e24="p25_sexo==2", e12="P24==2", val="poblacion/1"))
A(I("crec_intercensal", "Crecimiento 2012→2024", "%", 0, G, y12="ajuste", uni="personas",
    e24="derivado", e12="derivado", nota="Tasa anual equivalente; requiere las dos columnas."))
A(I("pct_0_4", "Primera infancia (0-4)", "%", 0, G, n="mun+mz", s=True, uni="personas",
    e24="p26_edad 0..4", e12="P25 0..4"))
A(I("pct_0_14", "Población 0–14 años", "%", 0, G, s=True, uni="personas",
    e24="p26_edad 0..14", e12="P25 0..14", val="poblacion/3"))
A(I("pct_menor20", "Menores de 20 años", "%", 0, G, n="mun+mz", s=True, uni="personas",
    e24="p26_edad < 20", e12="P25 < 20",
    nota="Es el corte de las fichas por manzana. Convive con pct_0_14, que es el del INE."))
A(I("pct_15_29", "Jóvenes (15-29)", "%", 0, G, s=True, uni="personas",
    e24="p26_edad 15..29", e12="P25 15..29"))
A(I("pct_15_64", "Población en edad activa (15-64)", "%", 0, G, s=True, uni="personas",
    e24="p26_edad 15..64", e12="P25 15..64"))
A(I("pct_60_mas", "60 años y más", "%", 0, G, n="mun+mz", s=True, uni="personas",
    e24="p26_edad >= 60", e12="P25 >= 60", val="poblacion/11"))
A(I("pct_65_mas", "Adultos mayores (65+)", "%", 0, G, s=True, uni="personas",
    e24="p26_edad >= 65", e12="P25 >= 65", val="poblacion/10"))
A(I("pct_80_mas", "Cuarta edad (80+)", "%", 0, G, s=True, uni="personas",
    e24="p26_edad >= 80", e12="P25 >= 80", val="poblacion/12"))
A(I("edad_mediana", "Edad mediana", "años", 0, G, s=True, uni="personas",
    e24="mediana(p26_edad)", e12="mediana(P25)", val="poblacion/7"))
A(I("edad_promedio", "Edad promedio", "años", 0, G, s=True, uni="personas",
    e24="media(p26_edad)", e12="media(P25)"))
A(I("indice_masculinidad", "Índice de masculinidad", "h/100m", 0, G, n="mun+mz", uni="personas",
    e24="100 * hombres / mujeres", e12="idem", val="poblacion/6"))
A(I("razon_dependencia", "Razón de dependencia", "%", -1, G, n="mun+mz", uni="personas",
    e24="100 * (0-14 + 65+) / 15-64", e12="idem", val="poblacion/14"))
A(I("dep_juvenil", "Dependencia juvenil", "%", 0, G, uni="personas",
    e24="100 * 0-14 / 15-64", e12="idem"))
A(I("dep_senil", "Dependencia senil", "%", 0, G, uni="personas",
    e24="100 * 65+ / 15-64", e12="idem"))
A(I("indice_envejecimiento", "Índice de envejecimiento", "índice", 0, G, uni="personas",
    e24="100 * 65+ / 0-14", e12="idem", val="poblacion/10"))
A(I("indice_juventud", "Índice de juventud", "índice", 0, G, uni="personas",
    e24="100 * 15-29 / total", e12="idem", val="poblacion/9"))
A(I("pct_urbano", "Urbanización", "%", 0, G, uni="viv_ocu",
    e24="urbrur == 1", e12="URBRUR == 1", val="poblacion/2"))
A(I("densidad", "Densidad", "hab/ha", 0, G, n="mun+mz", y12="ajuste", uni="personas",
    e24="personas / superficie", e12="personas / superficie", fuente="geometría",
    nota="Única que no sale del censo: la superficie viene del mapa maestro."))

# ── hogares ────────────────────────────────────────────────────────────────
G = "Hogares y jefatura"
A(I("tam_hogar", "Personas por hogar", "pers", -1, G, n="mun+mz", uni="hogares",
    e24="media(tot_pers)", e12="media(TOTPERS_VIV)", val="vivienda_hogar/22",
    nota="⚠️ El Atlas lo dividía por TODAS las viviendas pese a llamarse 'por vivienda ocupada'."))
A(I("pct_hogar_unipersonal", "Hogares unipersonales", "%", 0, G, n="mun+mz", uni="hogares",
    e24="tip_hog == 1", e12="TOTPERS_VIV == 1", val="vivienda_hogar/19"))
A(I("pct_hogar_nuclear", "Hogares nucleares", "%", 0, G, n="mun+mz", uni="hogares",
    e24="tip_hog in {2,4}", e12="derivar de P23", val="vivienda_hogar/19"))
A(I("pct_hogar_monoparental", "Hogares monoparentales", "%", 0, G, n="mun+mz", uni="hogares",
    e24="tip_hog == 3", e12="derivar de P23", val="vivienda_hogar/19"))
A(I("pct_hogar_extendido", "Hogares extendidos", "%", 0, G, n="mun+mz", uni="hogares",
    e24="tip_hog == 5", e12="derivar de P23", val="vivienda_hogar/19"))
A(I("pct_hogar_compuesto", "Hogares compuestos", "%", 0, G, n="mun+mz", uni="hogares",
    e24="tip_hog == 6", e12="derivar de P23", val="vivienda_hogar/19"))
A(I("pct_jefatura_femenina", "Jefatura femenina", "%", 0, G, uni="hogares",
    e24="jefe(p24_parentes==1) and p25_sexo==2", e12="jefe(P23==1) and P24==2",
    val="vivienda_hogar/21", nota="Indicador nuevo: no está en los 136 actuales."))
A(I("pct_hogar_con_menores", "Hogares con menores de 15", "%", 0, G, uni="hogares",
    e24="hogar con alguna persona de 0-14", e12="idem"))
A(I("pct_hogar_con_am", "Hogares con adulto mayor", "%", 0, G, uni="hogares",
    e24="hogar con alguna persona 65+", e12="idem"))
A(I("pct_am_solo", "Adultos mayores viviendo solos", "%", -1, G, uni="hogares",
    e24="tot_pers==1 and la persona tiene 65+", e12="idem",
    nota="Indicador nuevo. Señal de vulnerabilidad que hoy no se mide."))

# ═══════════════════════════════════════════════════════════════════════════
G = "Agua"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_agua_caneria", "Agua por cañería de red", "%", 1, G, n="mun+mz",
    e24="v07_aguapro == 1", e12="P07 == 1", val="servicios_basicos/4"))
A(I("pct_agua_interior", "Agua dentro de la vivienda", "%", 1, G,
    e24="v08_aguadist == 1", e12="P08 == 1", val="servicios_basicos/6"))
A(I("pct_agua_lote", "Agua por cañería fuera pero en el lote", "%", 0, G,
    e24="v08_aguadist == 2", e12="P08 == 2", val="servicios_basicos/6"))
A(I("pct_agua_sin_caneria", "Sin distribución por cañería", "%", -1, G,
    e24="v08_aguadist == 3", e12="P08 == 3", val="servicios_basicos/6"))
A(I("pct_agua_pileta", "Pileta pública", "%", -1, G, n="mun+mz",
    e24="v07_aguapro == 2", e12="P07 == 2", val="servicios_basicos/5"))
A(I("pct_agua_pozo", "Agua de pozo", "%", 0, G, n="mun+mz",
    e24="v07_aguapro in {4,5}", e12="P07 in {4,5}", val="servicios_basicos/5"))
A(I("pct_agua_pozo_bomba", "Pozo con bomba", "%", 0, G, n="mun+mz",
    e24="v07_aguapro == 4", e12="P07 == 4", val="servicios_basicos/5"))
A(I("pct_agua_rio", "Río, acequia o vertiente no protegida", "%", -1, G,
    e24="v07_aguapro == 7", e12="P07 == 7", val="servicios_basicos/5"))
A(I("pct_agua_carro", "Carro repartidor (aguatero)", "%", -1, G, n="mun+mz",
    e24="v07_aguapro == 8", e12="P07 == 8", val="servicios_basicos/5"))
A(I("pct_agua_lluvia", "Cosecha de agua de lluvia", "%", 0, G, n="mun+mz",
    e24="v07_aguapro == 3", e12="P07 == 3", val="servicios_basicos/5"))
A(I("pct_agua_no_mejorada", "Fuente no mejorada", "%", -1, G,
    e24="v07_aguapro in {5,7,8}", e12="P07 in {5,7,8}", val="servicios_basicos/7"))
A(I("pct_agua_mejorada", "Acceso a fuente mejorada", "%", 1, G, n="mun+mz",
    e24="complemento de no mejorada", e12="idem", val="servicios_basicos/7",
    nota="El INE lo publica sobre POBLACIÓN, no sobre viviendas: validar contra esa hoja."))

# ═══════════════════════════════════════════════════════════════════════════
G = "Saneamiento"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_servicio_sanitario", "Con baño o letrina", "%", 1, G,
    e24="v15_servsan in {1,2}", e12="P09 in {1,2}", val="servicios_basicos/8"))
A(I("pct_sanitario_exclusivo", "Baño de uso exclusivo del hogar", "%", 1, G,
    e24="v15_servsan == 1", e12="P09 == 1", val="servicios_basicos/8"))
A(I("pct_sanitario_compartido", "Baño compartido", "%", -1, G,
    e24="v15_servsan == 2", e12="P09 == 2", val="servicios_basicos/8"))
A(I("pct_sin_sanitario", "Sin baño ni letrina", "%", -1, G,
    e24="v15_servsan == 3", e12="P09 == 3", val="servicios_basicos/8"))
A(I("pct_alcantarillado", "Desagüe a alcantarillado", "%", 1, G, n="mun+mz",
    e24="v16_desague == 1", e12="P10 == 1", val="servicios_basicos/9"))
A(I("pct_camara_septica", "Desagüe a cámara séptica", "%", 0, G, n="mun+mz",
    e24="v16_desague == 2", e12="P10 == 2", val="servicios_basicos/10"))
A(I("pct_pozo_ciego", "Desagüe a pozo ciego", "%", -1, G, n="mun+mz",
    e24="v16_desague == 3", e12="P10 == 3", val="servicios_basicos/10"))
A(I("pct_desague_superficie", "Desagüe a la superficie", "%", -1, G, n="mun+mz",
    e24="v16_desague == 5", e12="P10 == 5", val="servicios_basicos/10"))
A(I("pct_sin_desague", "Sin desagüe", "%", -1, G, n="mun+mz",
    e24="v15_servsan == 3", e12="P09 == 3", val="servicios_basicos/8"))
A(I("pct_saneamiento_mejorado", "Saneamiento mejorado", "%", 1, G,
    e24="v16_desague in {1,2} y baño exclusivo", e12="idem", val="servicios_basicos/11",
    nota="Definición ODS 6.2.1; el INE la publica sobre población."))

# ═══════════════════════════════════════════════════════════════════════════
G = "Energía y cocina"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_electricidad", "Con energía eléctrica", "%", 1, G, n="mun+mz",
    e24="v09_energia in {1,2,3,4}", e12="P11 != 'no tiene'", val="servicios_basicos/1"))
A(I("pct_elec_red", "Energía de la red pública", "%", 1, G, n="mun+mz",
    e24="v09_energia == 1", e12="P11 == 1", val="servicios_basicos/3"))
A(I("pct_panel_solar", "Energía por panel solar", "%", 0, G, n="mun+mz",
    e24="v09_energia == 3", e12="P11 == 3", val="servicios_basicos/3"))
A(I("pct_motor_propio", "Motor propio o generador", "%", 0, G,
    e24="v09_energia == 2", e12="P11 == 2", val="servicios_basicos/3"))
A(I("pct_sin_energia", "Sin energía eléctrica", "%", -1, G, n="mun+mz",
    e24="v09_energia == 5", e12="P11 == 'no tiene'", val="servicios_basicos/1"))
A(I("pct_gas_red", "Gas por cañería a domicilio", "%", 1, G, n="mun+mz",
    e24="v10_combus == 2", e12="P12 gas por cañería", val="servicios_basicos/12"))
A(I("pct_gas_garrafa", "Cocina con gas en garrafa", "%", 0, G, n="mun+mz",
    e24="v10_combus == 1", e12="P12 garrafa", val="servicios_basicos/12"))
A(I("pct_lena_guano", "Cocina con leña o guano", "%", -1, G, n="mun+mz",
    e24="v10_combus in {3,4}", e12="P12 leña/guano", val="servicios_basicos/12"))
A(I("pct_combustible_limpio", "Combustible limpio para cocinar", "%", 1, G,
    e24="v10_combus in {1,2,5,6}", e12="idem", val="ods_pdes/7.1.2",
    nota="Definición ODS 7.1.2."))
A(I("pct_cocina_exclusiva", "Cuarto sólo para cocinar", "%", 1, G,
    e24="v12_cocina == 1", e12="P13 == 1", val="vivienda_hogar/16"))
A(I("pct_no_cocina", "No cocina en la vivienda", "%", 0, G, n="mun+mz",
    e24="v10_combus == 8", e12="P12 no cocina", val="servicios_basicos/12"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Residuos"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_basura_formal", "Recojo formal de basura", "%", 1, G, n="mun+mz",
    e24="v11_basura in {1,2}", e12="P16 contenedor/carro", val="servicios_basicos/13"))
A(I("pct_basura_carro", "Entrega al carro basurero", "%", 1, G, n="mun+mz",
    e24="v11_basura == 2", e12="P16 carro", val="servicios_basicos/13"))
A(I("pct_basura_contenedor", "Deposita en contenedor público", "%", 1, G,
    e24="v11_basura == 1", e12="P16 contenedor", val="servicios_basicos/13"))
A(I("pct_basura_quema", "Quema la basura", "%", -1, G, n="mun+mz",
    e24="v11_basura == 5", e12="P16 quema", val="servicios_basicos/13"))
A(I("pct_basura_entierra", "Entierra la basura", "%", -1, G, n="mun+mz",
    e24="v11_basura == 6", e12="P16 entierra", val="servicios_basicos/13"))
A(I("pct_basura_informal", "Basura a terreno baldío, calle o río", "%", -1, G, n="mun+mz",
    e24="v11_basura in {3,4}", e12="P16 calle/río", val="servicios_basicos/13"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Vivienda y materiales"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_pared_ladrillo", "Paredes de ladrillo o bloque", "%", 1, G, n="mun+mz",
    e24="v03_pared == 1", e12="P03 ladrillo", val="vivienda_hogar/8"))
A(I("pct_pared_adobe", "Paredes de adobe o tapial", "%", -1, G, n="mun+mz",
    e24="v03_pared == 2", e12="P03 adobe", val="vivienda_hogar/8"))
A(I("pct_pared_madera", "Paredes de madera", "%", 0, G, n="mun+mz",
    e24="v03_pared == 5", e12="P03 madera", val="vivienda_hogar/8"))
A(I("pct_pared_precaria", "Paredes precarias (caña, palma, tronco)", "%", -1, G,
    e24="v03_pared == 6", e12="P03 caña/palma", val="vivienda_hogar/8"))
A(I("pct_revoque", "Paredes con revoque", "%", 1, G, n="mun+mz",
    e24="v04_revoq == 1", e12="P04 == 1", val="vivienda_hogar/8"))
A(I("pct_techo_calamina", "Techo de calamina", "%", 0, G, n="mun+mz",
    e24="v05_techo == 1", e12="P05 calamina", val="vivienda_hogar/9"))
A(I("pct_techo_teja", "Techo de teja", "%", 1, G, n="mun+mz",
    e24="v05_techo == 2", e12="P05 teja", val="vivienda_hogar/9"))
A(I("pct_techo_losa", "Techo de losa de hormigón", "%", 1, G, n="mun+mz",
    e24="v05_techo == 3", e12="P05 losa", val="vivienda_hogar/9"))
A(I("pct_techo_paja", "Techo de paja o palma", "%", -1, G, n="mun+mz",
    e24="v05_techo == 4", e12="P05 paja", val="vivienda_hogar/9"))
A(I("pct_piso_tierra", "Piso de tierra", "%", -1, G, n="mun+mz",
    e24="v06_piso == 1", e12="P06 tierra", val="vivienda_hogar/10"))
A(I("pct_piso_cemento", "Piso de cemento", "%", 0, G, n="mun+mz",
    e24="v06_piso == 5", e12="P06 cemento", val="vivienda_hogar/10"))
A(I("pct_piso_ceramica", "Piso de cerámica o porcelanato", "%", 1, G, n="mun+mz",
    e24="v06_piso in {4,6}", e12="P06 cerámica/mosaico", val="vivienda_hogar/10"))
A(I("pct_monoambiente", "Viviendas de un solo cuarto", "%", -1, G,
    e24="v13_habitac == 1", e12="P14 == 1", val="vivienda_hogar/11"))
A(I("pct_hacinamiento", "Hacinamiento (>3 personas por dormitorio)", "%", -1, G, n="mun+mz",
    e24="tot_pers / v14_dormit > 3", e12="TOTPERS_VIV / P15 > 3", val="vivienda_hogar/14",
    nota="⚠️ Verificar el umbral exacto del INE antes de publicar: el nuestro no reproduce el tabulado."))
A(I("pers_x_dormitorio", "Personas por dormitorio", "pers", -1, G,
    e24="suma(tot_pers) / suma(v14_dormit)", e12="suma(TOTPERS_VIV) / suma(P15)",
    val="vivienda_hogar/15",
    nota="Razón de dos totales, no promedio de razones. Las viviendas con CERO "
         "dormitorios aportan sus personas al numerador y nada al denominador: "
         "así reproduce el tabulado del INE en los 343."))
A(I("pct_choza", "Chozas o pahuichis", "%", -1, G, y12="ajuste",
    e24="v01_tipoviv == 2", e12="—", uni="viv_part", val="vivienda_hogar/7",
    nota="⚠️ 2012 junta 'Casa/Choza/Pahuichi' en una sola categoría: NO separable."))
A(I("pct_departamento", "Departamentos", "%", 0, G, uni="viv_part",
    e24="v01_tipoviv == 3", e12="P01 == 2", val="vivienda_hogar/7"))
A(I("pct_vivienda_desocupada", "Viviendas desocupadas", "%", 0, G, n="mun+mz", uni="viv_part",
    e24="v02_condocup in {3,4,5}", e12="P02 in {3,4,5}", val="vivienda_hogar/6"))
A(I("viviendas", "Viviendas", "viv", 0, G, n="mun+mz", uni="viv_ocu",
    e24="count", e12="count", val="vivienda_hogar/1"))
A(I("pers_x_vivienda", "Personas por vivienda", "pers", -1, G, n="mun+mz", uni="hogares",
    e24="media(tot_pers)", e12="media(TOTPERS_VIV)",
    nota="⚠️ DUPLICADO EXACTO de `tam_hogar`: misma regla y mismo número. "
         "Decisión de producto pendiente: cuál de los dos se queda."))
A(I("pers_x_habitacion", "Personas por habitación", "pers", -1, G, uni="hogares",
    e24="suma(tot_pers) / suma(v13_habitac)", e12="suma(TOTPERS_VIV) / suma(P14)",
    val="vivienda_hogar/15",
    nota="El tercer promedio que publica el INE. Habitaciones = cuartos sin contar "
         "baño ni cocina (preg. 13); los dormitorios son un subconjunto (preg. 14)."))

G = "Tenencia"
A(I("pct_viv_propia", "Vivienda propia", "%", 1, G, n="mun+mz",
    e24="v17_tenencia in {1,2}", e12="P19 propia", val="vivienda_hogar/17"))
A(I("pct_viv_alquilada", "Vivienda en alquiler", "%", 0, G, n="mun+mz",
    e24="v17_tenencia == 4", e12="P19 alquilada", val="vivienda_hogar/17"))
A(I("pct_viv_anticretico", "Vivienda en anticrético", "%", 0, G, n="mun+mz",
    e24="v17_tenencia in {5,6}", e12="P19 anticrético", val="vivienda_hogar/17"))
A(I("pct_viv_prestada", "Vivienda prestada o cedida", "%", 0, G, n="mun+mz",
    e24="v17_tenencia in {3,7}", e12="P19 prestada/cedida", val="vivienda_hogar/17"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Educación"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_analfabetismo", "Analfabetismo (15+)", "%", -1, G, s=True, uni="p15mas",
    e24="p40_lee == 2", e12="P35 == 2", val="educacion/1"))
A(I("pct_sin_educacion", "Sin nivel educativo (19+)", "%", -1, G, n="mun+mz", s=True, uni="p19mas",
    e24="nivel_edu == 1", e12="P37A ninguno", val="educacion/3",
    nota="★ El universo es 19+, no 15+: así lo define el INE. El extractor viejo usaba 15+."))
A(I("pct_edu_primaria", "Sólo primaria (19+)", "%", 0, G, n="mun+mz", s=True, uni="p19mas",
    e24="nivel_edu == 2", e12="P37A primaria", val="educacion/3"))
A(I("pct_edu_secundaria", "Secundaria (19+)", "%", 0, G, n="mun+mz", s=True, uni="p19mas",
    e24="nivel_edu == 3", e12="P37A secundaria", val="educacion/3"))
A(I("pct_edu_superior", "Educación superior (19+)", "%", 1, G, n="mun+mz", s=True, uni="p19mas",
    e24="nivel_edu == 4", e12="P37A superior", val="educacion/3"))
A(I("prom_anios_estudio", "Años promedio de estudio (19+)", "años", 1, G, s=True, uni="p19mas",
    e24="media(aestudio)", e12="derivar de P37A/P37B", val="educacion/4"))
A(I("pct_asistencia_escolar", "Asistencia escolar (6–17)", "%", 1, G, s=True, uni="p6_17",
    e24="asiste == 1", e12="P36 == 1", val="educacion/2"))
A(I("tasa_asistencia_4_5", "Asistencia inicial (4-5)", "%", 1, G, s=True, uni="p4_5",
    e24="asiste == 1", e12="P36 == 1", val="ods_pdes/4.2.2"))
A(I("tasa_asistencia_18_24", "Asistencia 18-24", "%", 1, G, s=True, uni="p18mas",
    e24="asiste==1 and edad 18..24", e12="idem"))
A(I("pct_secundaria_mas", "Secundaria o más (19+)", "%", 1, G, s=True, uni="p19mas",
    e24="nivel_edu >= 3", e12="idem", val="educacion/3"))
A(I("pct_primaria_completa", "Completó primaria (19+)", "%", 1, G, s=True, uni="p19mas",
    e24="nivel_edu>=2 and curso>=6", e12="idem", val="ods_pdes/4.6.1"))
A(I("pct_rezago_escolar", "Rezago escolar (12-17)", "%", -1, G, s=True, uni="p6_17",
    e24="curso aprobado por debajo del esperado para la edad", e12="idem",
    val="ods_pdes/4.1.1", nota="Indicador nuevo, de la familia ODS."))
A(I("pct_educacion_publica", "Estudia en sistema público", "%", 0, G, s=True, y12="si",
    uni="p6_17", e24="p39_tipoest == pública", e12="P36 == 1",
    nota="Corregido 2026-08-12: yo había anotado que era sólo de 2024 y ESTÁ MAL. "
         "En 2012 la pregunta de asistencia (P36) responde pública / privada / de "
         "convenio, así que el tipo de establecimiento sí tiene serie intercensal."))
A(I("brecha_alfabetismo", "Brecha de género en alfabetismo", "pp", -1, G, uni="p15mas",
    e24="mujeres − hombres", e12="idem", val="educacion/1"))
A(I("brecha_edu_superior", "Brecha de género en educación superior", "pp", 0, G, n="mun+mz",
    uni="p19mas", e24="mujeres − hombres", e12="idem"))
A(I("brecha_anios_estudio", "Brecha de género en años de estudio", "años", 0, G, uni="p19mas",
    e24="mujeres − hombres", e12="idem", val="educacion/4"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Salud"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_salud_publica", "Acude a establecimiento público", "%", 0, G, n="mun+mz", s=True, uni="personas",
    e24="p30a_public == 1", e12="P28C == 1", val="salud/2"))
A(I("pct_caja_salud", "Acude a caja de salud", "%", 0, G, s=True, uni="personas",
    e24="p30b_caja == 1", e12="P28A == 1", val="salud/2"))
A(I("pct_salud_privada", "Acude a salud privada", "%", 0, G, n="mun+mz", s=True, uni="personas",
    e24="p30c_privad == 1", e12="P28D == 1", val="salud/2"))
A(I("pct_salud_tradicional", "Acude a medicina tradicional", "%", 0, G, n="mun+mz", s=True,
    uni="personas", e24="p30e_tradic == 1", e12="P28E == 1", val="salud/2"))
A(I("pct_automedicacion", "Se automedica o va a la farmacia", "%", -1, G, n="mun+mz", s=True,
    uni="personas", e24="p30f_autome == 1", e12="P28G == 1", val="salud/2"))
A(I("pct_remedios_caseros", "Soluciones caseras", "%", 0, G, s=True, uni="personas",
    e24="p30g_casera == 1", e12="P28F == 1", val="salud/2"))
A(I("pct_seguro_salud", "Con seguro de salud", "%", 1, G, s=True, y12="no", uni="personas",
    e24="p31_afiliado in {1,2,3}", e12=None,
    nota="⚠️ Sólo 2024: en 2012 no se preguntaba afiliación y el SUS no existía."))
A(I("pct_sus", "Afiliados al SUS", "%", 0, G, n="mun+mz", s=True, y12="no", uni="personas",
    e24="p31_afiliado == 1", e12=None, nota="⚠️ Sólo 2024: el SUS se crea en 2019."))
A(I("pct_seguro_privado", "Con seguro privado", "%", 0, G, n="mun+mz", s=True, y12="no",
    uni="personas", e24="p31_afiliado == 3", e12=None, nota="⚠️ Sólo 2024."))
A(I("pct_sin_seguro", "Sin afiliación a salud", "%", -1, G, n="mun+mz", s=True, y12="no",
    uni="personas", e24="p31_afiliado == 4", e12=None, nota="⚠️ Sólo 2024."))
A(I("fecundidad", "Hijos por mujer (15-49)", "hijos", 0, G, uni="mef",
    e24="media(p54_hvtot)", e12="media(P46)", val="salud/6"))
A(I("paridez_media", "Paridez media (12+)", "hijos", 0, G, uni="muj12",
    e24="media(p54_hvtot)", e12="media(P46)", val="salud/6"))
A(I("pct_madres_adolescentes", "Madres adolescentes (15-19)", "%", -1, G, uni="mef",
    e24="mujeres 15-19 con al menos un hijo", e12="idem", val="ods_pdes/3.7.2"))
A(I("pct_hijos_fallecidos", "Hijos fallecidos", "%", -1, G, uni="muj12",
    e24="1 − p55_hstot / p54_hvtot", e12="1 − P47 / P46", val="salud/6"))
A(I("pct_parto_calificado", "Parto con personal calificado", "%", 1, G, uni="mef",
    e24="p59_atparto médico/enfermera", e12="P49B establecimiento", val="salud/6"))
A(I("edad_1er_hijo", "Edad promedio al primer hijo", "años", 0, G, uni="mef",
    e24="derivado", e12="derivado"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Empleo"
# ═══════════════════════════════════════════════════════════════════════════
A(I("tasa_participacion", "Tasa de participación (15+)", "%", 0, G, s=True, y12="ajuste",
    uni="pet15", e24="ocupados+desocupados / 15+", e12="idem", val="economia/3",
    nota="★ NO usar pea_13/PEA: la base cambió (10+ en 2012, 7+ en 2024). Corte propio a 15+."))
A(I("tasa_ocupacion", "Tasa de ocupación (15+)", "%", 1, G, s=True, y12="ajuste",
    uni="pet15", e24="ocupados / 15+", e12="idem", val="economia/3"))
A(I("tasa_desocupacion", "Tasa de desocupación", "%", -1, G, s=True, y12="ajuste",
    uni="pet15", e24="desocupados / PEA", e12="idem", val="economia/3"))
A(I("pct_asalariados", "Asalariados", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="p50_catocu_13 obrero/empleado", e12="P43 obrero/empleado", val="economia/4"))
A(I("pct_cuenta_propia", "Trabajadores por cuenta propia", "%", 0, G, n="mun+mz", s=True,
    uni="ocupados", e24="p50_catocu_13 cuenta propia", e12="P43 cuenta propia", val="economia/4"))
A(I("pct_empleadores", "Empleadores", "%", 0, G, s=True, uni="ocupados",
    e24="p50_catocu_13 empleador", e12="P43 empleador", val="economia/4"))
A(I("pct_trab_familiar", "Trabajo familiar sin pago", "%", -1, G, s=True, uni="ocupados",
    e24="p50_catocu_13 familiar", e12="P43 familiar", val="economia/4"))
A(I("pct_sector_primario", "Sector primario", "%", 0, G, s=True, uni="ocupados",
    e24="act_eco_2d_19 agricultura+minería", e12="P44 idem", val="economia/9"))
A(I("pct_sector_secundario", "Sector secundario", "%", 0, G, s=True, uni="ocupados",
    e24="act_eco manufactura+construcción", e12="idem", val="economia/9"))
A(I("pct_sector_servicios", "Sector servicios", "%", 0, G, s=True, uni="ocupados",
    e24="act_eco servicios", e12="idem", val="economia/9"))
A(I("pct_agricultura", "Ocupados en agricultura", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="act_eco_2d_13 == agricultura", e12="P44 agricultura", val="economia/9",
    nota="★ TODO el bloque de empleo va con la 13ª CIET, no la 19ª. El tabulado del "
         "INE usa la 13 (es la que permite comparar con 2012) y la 19 saca de la "
         "ocupación a los productores agrícolas de autoconsumo: con `act_eco_2d_19` "
         "faltaban 444.396 agricultores y el indicador no cerraba."))
A(I("pct_comercio", "Ocupados en comercio", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="act_eco_2d_19 == comercio", e12="P44 comercio", val="economia/9"))
A(I("pct_manufactura", "Ocupados en manufactura", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="act_eco_2d_19 == manufactura", e12="P44 manufactura", val="ods_pdes/9.2.2"))
A(I("pct_construccion", "Ocupados en construcción", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="act_eco_2d_19 == construcción", e12="P44 construcción", val="economia/9"))
A(I("pct_transporte", "Ocupados en transporte", "%", 0, G, n="mun+mz", s=True, uni="ocupados",
    e24="act_eco_2d_19 == transporte", e12="P44 transporte", val="economia/9"))
A(I("pct_alojamiento", "Ocupados en alojamiento y comida", "%", 0, G, n="mun+mz", s=True,
    uni="ocupados", e24="act_eco_2d_19 == alojamiento", e12="P44 idem", val="economia/9"))
A(I("pct_admin_publica", "Empleo en administración pública", "%", 0, G, s=True, uni="ocupados",
    e24="act_eco_2d_19 == adm. pública", e12="P44 idem", val="economia/9"))
A(I("pct_ocu_profesionales", "Profesionales y técnicos", "%", 1, G, s=True, uni="ocupados",
    e24="ocu_1d_13 in {1,2,3}", e12="P42 in {1,2,3}", val="economia/6",
    nota="Indicador nuevo: usa el grupo ocupacional, que hoy no se explota. "
         "★ USAR LA 13ª CIET, no la 19ª — ver la nota de rama."))
A(I("pct_ocu_no_calificado", "Trabajadores no calificados", "%", -1, G, s=True, uni="ocupados",
    e24="ocu_1d_13 == 9", e12="P42 == 9", val="economia/6"))
A(I("brecha_participacion", "Brecha de género en participación", "pp", -1, G, y12="ajuste",
    uni="pet15", e24="hombres − mujeres", e12="idem", val="economia/3"))
A(I("brecha_cuentapropia", "Brecha de género en cuenta propia", "pp", 0, G, n="mun+mz",
    uni="ocupados", e24="mujeres − hombres", e12="idem"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Migración y territorio"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_nacido_otro_municipio", "Nacidos en otro municipio", "%", 0, G, n="mun+mz", s=True,
    uni="personas", e24="mun_nac_cod != municipio", e12="P32H != municipio", val="migracion/2"))
A(I("pct_nacido_extranjero", "Nacidos en el extranjero", "%", 0, G, n="mun+mz", s=True,
    uni="personas", e24="p35_lugnac == otro país", e12="P32A == otro país", val="migracion/7"))
A(I("pct_migrante_reciente", "Migrantes recientes (últimos 5 años)", "%", 0, G, n="mun+mz", s=True,
    uni="personas", e24="mun_res5_cod != municipio", e12="P34G != municipio", val="migracion/2"))
A(I("pct_residia_otro_mun", "Residía en otro municipio", "%", 0, G, n="mun+mz", s=True,
    uni="personas", e24="mun_res_cod != municipio", e12="P33G != municipio"))
A(I("saldo_migratorio", "Saldo migratorio absoluto", "hab", 0, G, uni="personas",
    e24="inmigrantes − emigrantes internos", e12="idem", val="migracion/2",
    nota="Indicador nuevo: requiere la matriz origen-destino completa."))
A(I("pct_trabaja_fuera", "Trabaja fuera del municipio", "%", 0, G, y12="no", uni="ocupados",
    e24="mun_lab_cod != municipio", e12=None,
    nota="⚠️ Sólo 2024: la pregunta por municipio de trabajo no existe en 2012."))

G = "Flujos metropolitanos"
A(I("autocontencion_laboral", "Autocontención laboral", "%", 0, G, y12="no", uni="ocupados",
    e24="trabaja en su propio municipio", e12=None,
    nota="★ El indicador que define una región metropolitana. Sólo 2024."))
A(I("dependencia_capital", "Ocupados que trabajan en la capital", "%", 0, G, y12="no",
    uni="ocupados", e24="mun_lab_cod == 070101", e12=None,
    nota="★ Verificado: Porongo 25,9% · Montero 2,4%. Sólo 2024."))
A(I("poblacion_flotante", "Población flotante diurna", "hab", 0, G, y12="no", uni="ocupados",
    e24="entrantes − salientes por trabajo", e12=None, nota="★ Sólo 2024."))
A(I("matriz_conmutacion", "Matriz de conmutación (9×9)", "hab", 0, G, y12="no", uni="ocupados",
    e24="vive × trabaja", e12=None, val="movilidad_cotidiana/1",
    nota="★ No es un coroplético: necesita vista de flujo. Cubre el 44% de los destinos."))
A(I("matriz_migracion_nac", "Matriz migratoria por nacimiento", "hab", 0, G, uni="personas",
    e24="municipio de nacimiento × residencia", e12="P32H × municipio",
    nota="★ SÍ existe en los dos censos: permite ver cómo cambió el origen del anillo."))
A(I("matriz_migracion_5a", "Matriz migratoria de los últimos 5 años", "hab", 0, G, uni="personas",
    e24="mun_res5_cod × residencia", e12="P34G × municipio",
    nota="★ En los dos censos."))

# ═══════════════════════════════════════════════════════════════════════════
G = "Pueblos, idiomas y ciudadanía"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_autoident_indigena", "Autoidentificación indígena", "%", 0, G, s=True, uni="personas",
    e24="p32_pueblo_per == sí", e12="P29A == sí", val="idiomas_1"))
A(I("pct_quechua", "Autoidentificación quechua", "%", 0, G, uni="personas",
    e24="p32_pueblo_cod == quechua", e12="P29C == quechua", val="idiomas_1"))
A(I("pct_aymara", "Autoidentificación aymara", "%", 0, G, uni="personas",
    e24="p32_pueblo_cod == aymara", e12="P29C == aymara", val="idiomas_1"))
A(I("pct_guarani", "Autoidentificación guaraní", "%", 0, G, uni="personas",
    e24="p32_pueblo_cod == guaraní", e12="P29C == guaraní", val="idiomas_1"))
A(I("pct_chiquitano", "Autoidentificación chiquitano", "%", 0, G, uni="personas",
    e24="p32_pueblo_cod == chiquitano", e12="P29C == chiquitano", val="idiomas_1",
    nota="Pueblo mayoritario del oriente: pertinente acá aunque no esté en los 136."))
A(I("pct_idioma_materno_originario", "Idioma materno originario", "%", 0, G, s=True,
    uni="personas", e24="idioma_mat originario", e12="P30B originario", val="idiomas_2"))
A(I("pct_idioma_materno_castellano", "Idioma materno castellano", "%", 0, G, s=True,
    uni="personas", e24="idioma_mat == castellano", e12="P30B == castellano", val="idiomas_2"))
A(I("pct_bilingue", "Habla dos o más idiomas", "%", 0, G, s=True, uni="personas",
    e24="p331..p333 con 2+", e12="P31B1..P31B5 con 2+", val="idiomas_2",
    nota="Indicador nuevo."))
A(I("pct_registro_civil", "Inscritos en registro civil", "%", 1, G, s=True, uni="personas",
    e24="p28_cn == sí", e12="P26 == sí", val="ciudadania"))
A(I("pct_cedula_identidad", "Con cédula de identidad", "%", 1, G, s=True, uni="personas",
    e24="p29_ci == sí", e12="P27 == sí", val="ciudadania"))
A(I("pct_registro_menores5", "Nacimientos inscritos (menores de 5)", "%", 1, G, uni="personas",
    e24="p28_cn == sí and edad < 5", e12="idem", val="ods_pdes/16.9.1"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Tecnología y equipamiento"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_internet", "Hogares con internet", "%", 1, G, n="mun+mz", y12="ajuste",
    e24="v19e_inetfijo==1 or v19f_inetmovil==1", e12="P17D == 1", val="ods_pdes/9.c.1",
    nota="⚠️ 2012 pregunta 'servicio de internet' sin separar fijo/móvil: comparar sólo el agregado."))
A(I("pct_internet_fijo", "Internet fijo", "%", 1, G, y12="no",
    e24="v19e_inetfijo == 1", e12=None, val="tic/1", nota="⚠️ Sólo 2024."))
A(I("pct_internet_movil", "Internet móvil", "%", 1, G, y12="no",
    e24="v19f_inetmovil == 1", e12=None, val="tic/1", nota="⚠️ Sólo 2024."))
A(I("pct_computadora", "Hogares con computadora", "%", 1, G,
    e24="v19c_compu == 1", e12="P17C == 1", val="tic/1"))
A(I("pct_celular", "Hogares con celular", "%", 1, G, n="mun+mz", y12="ajuste",
    e24="v19d_celular == 1", e12="P17E (fija o celular junta)", val="tic/1",
    nota="⚠️ 2012 junta telefonía fija y celular en una sola pregunta."))
A(I("pct_tv_cable", "Hogares con TV por cable", "%", 0, G, y12="no",
    e24="v19g_tvcable == 1", e12=None, val="tic/1", nota="⚠️ Sólo 2024."))
A(I("pct_televisor", "Hogares con televisor", "%", 0, G, n="mun+mz",
    e24="v19b_tv == 1", e12="P17B == 1", val="tic/1"))
A(I("pct_radio", "Hogares con radio", "%", 0, G, n="mun+mz",
    e24="v19a_radio == 1", e12="P17A == 1", val="tic/1"))
A(I("pct_auto", "Hogares con vehículo automotor", "%", 1, G,
    e24="v18c_auto == 1", e12="P18A == 1", val="equipamiento_hogar/1"))
A(I("pct_moto", "Hogares con motocicleta", "%", 0, G,
    e24="v18b_moto == 1", e12="P18C == 1", val="equipamiento_hogar/1"))
A(I("pct_bicicleta", "Hogares con bicicleta", "%", 0, G,
    e24="v18a_bici == 1", e12="P18B == 1", val="equipamiento_hogar/1"))
A(I("pct_carreta", "Hogares con carreta o carretón", "%", 0, G,
    e24="v18d_carreta == 1", e12="P18D == 1", val="equipamiento_hogar/1"))
A(I("pct_bote", "Hogares con bote o canoa", "%", 0, G,
    e24="v18e_bote == 1", e12="P18E == 1", val="equipamiento_hogar/1"))
A(I("pct_refrigerador", "Hogares con refrigerador", "%", 1, G, y12="no",
    e24="v18f_refri == 1", e12=None, nota="⚠️ Sólo 2024."))
A(I("pct_lavadora", "Hogares con lavadora", "%", 1, G, y12="no",
    e24="v18j_lavadora == 1", e12=None, nota="⚠️ Sólo 2024."))
A(I("pct_microondas", "Hogares con microondas", "%", 0, G, y12="no",
    e24="v18g_micro == 1", e12=None, nota="⚠️ Sólo 2024."))
A(I("pct_aire_acond", "Hogares con aire acondicionado", "%", 0, G, y12="no",
    e24="v18i_aire == 1", e12=None, nota="⚠️ Sólo 2024."))

# ═══════════════════════════════════════════════════════════════════════════
G = "Discapacidad"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_discapacidad", "Con alguna discapacidad", "%", -1, G, s=True, y12="ajuste",
    uni="personas", e24="p42_discap == sí", e12="entidad DISCAP / P22A", val="discapacidad/1",
    nota="⚠️ 2012 lo capta a nivel hogar (P22A) + una entidad aparte; 2024 por persona."))
A(I("pct_disc_ver", "Dificultad severa para ver", "%", -1, G, s=True, y12="ajuste",
    uni="personas", e24="p42a_ver severa", e12="DISCAP", val="discapacidad/1"))
A(I("pct_disc_oir", "Dificultad severa para oír", "%", -1, G, s=True, y12="ajuste",
    uni="personas", e24="p42b_oir severa", e12="DISCAP", val="discapacidad/1"))
A(I("pct_disc_caminar", "Dificultad severa para caminar", "%", -1, G, s=True, y12="ajuste",
    uni="personas", e24="p42c_camina severa", e12="DISCAP", val="discapacidad/1"))
A(I("pct_disc_comunicar", "Dificultad severa para comunicarse", "%", -1, G, s=True, y12="ajuste",
    uni="personas", e24="p42d_comuni severa", e12="DISCAP", val="discapacidad/1"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Pobreza (NBI)"
# ═══════════════════════════════════════════════════════════════════════════
for k, l, d in [("pct_nbi_pobre", "Población pobre (NBI)", -1),
                ("pct_nbi_no_pobre", "Población no pobre (NBI)", 1),
                ("pct_nbi_satisfechas", "Necesidades básicas satisfechas", 1),
                ("pct_nbi_umbral", "En el umbral de pobreza", 0),
                ("pct_nbi_moderada", "Pobreza moderada", -1),
                ("pct_nbi_indigente", "Indigencia", -1),
                ("pct_nbi_marginal", "Marginalidad", -1)]:
    A(I(k, l, "%", d, G, uni="personas", fuente="tabulado", val="pobreza/1",
        e24="pobreza.xlsx", e12="pobreza.xlsx",
        nota="No sale del microdato: se lee del Excel del INE. Replicar la metodología "
             "oficial del NBI es un proyecto aparte."))
for k, l in [("pct_nbi_materiales", "NBI: materiales de la vivienda"),
             ("pct_nbi_espacios", "NBI: espacios de la vivienda"),
             ("pct_nbi_agua_sanea", "NBI: agua y saneamiento"),
             ("pct_nbi_energia", "NBI: insumos energéticos"),
             ("pct_nbi_educacion", "NBI: educación"),
             ("pct_nbi_salud", "NBI: atención en salud")]:
    A(I(k, l, "%", -1, "Componentes NBI", uni="personas", fuente="tabulado", val="pobreza/3",
        e24="pobreza.xlsx", e12="pobreza.xlsx"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Emigración internacional y mortalidad"
# ═══════════════════════════════════════════════════════════════════════════
A(I("pct_con_emigrante", "Hogares con emigrante", "%", 0, G, uni="hogares",
    e24="v20a_emi == sí", e12="P20A == sí", val="emigracion_internacional/1"))
A(I("emigrantes_x1000", "Emigrantes por 1.000 habitantes", "‰", 0, G, uni="personas",
    e24="Emigracion_CPV-2024.csv", e12="entidad EMIGRA", val="emigracion_internacional/1"))
for k, l in [("pct_emi_argentina", "Emigrantes en Argentina"),
             ("pct_emi_espana", "Emigrantes en España"),
             ("pct_emi_brasil", "Emigrantes en Brasil"),
             ("pct_emi_chile", "Emigrantes en Chile"),
             ("pct_emi_eeuu", "Emigrantes en EE.UU.")]:
    A(I(k, l, "%", 0, G, uni="personas", e24="Emigracion_CPV-2024.csv", e12="entidad EMIGRA",
        val="emigracion_internacional/2"))
A(I("edad_prom_emigracion", "Edad promedio al emigrar", "años", 0, G, uni="personas",
    e24="Emigracion_CPV-2024.csv", e12="entidad EMIGRA"))
A(I("pct_hogar_fallecido", "Hogares con fallecido reciente", "%", -1, G, uni="hogares",
    e24="v21a_fal == sí", e12="P21A == sí", val="mortalidad/1"))
A(I("tasa_mortalidad", "Tasa de mortalidad declarada", "‰", -1, G, uni="personas",
    e24="Mortalidad_CPV-2024.csv", e12="entidad MORTA", val="mortalidad/1"))
A(I("edad_prom_fallecimiento", "Edad promedio de fallecimiento", "años", 0, G, uni="personas",
    e24="Mortalidad_CPV-2024.csv", e12="entidad MORTA", val="mortalidad/2"))

# ═══════════════════════════════════════════════════════════════════════════
G = "Índices compuestos"
# ═══════════════════════════════════════════════════════════════════════════
A(I("idx_carencia", "Índice de carencia de servicios", "índice", -1, G, n="mun+mz",
    e24="0-100 sobre agua, desagüe, electricidad, basura y combustible",
    e12="idem", nota="Construcción propia; se calcula igual en los dos censos y en manzana."))
A(I("idx_calidad_vivienda", "Índice de calidad de la vivienda", "índice", 1, G,
    e24="paredes, techo, piso y hacinamiento", e12="idem", val="vivienda_hogar/18"))


# ─────────────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# SÓLO MANZANA — la ficha del geoportal trae 127 categorías y el motor usaba 63
# ═══════════════════════════════════════════════════════════════════════════
# Estos indicadores NO tienen contraparte municipal: el microdato no los separa
# igual, o directamente no se calcularon nunca a ese nivel. Entran al tablero
# rotulados como "sólo manzana" (decisión de Carlos, 2026-08-19), que es lo
# honesto: al subir de nivel el mapa se queda sin ellos, y eso hay que decirlo
# en vez de disimularlo.
# Ninguno tiene serie 2012: las fichas por manzano son sólo de 2024.
G = "Demografía y estructura"
A(I("pct_20_39", "De 20 a 39 años", "%", 0, G, n="mz", y12="no", uni="personas",
    fuente="ficha", e24="edad_20a39 / total de la manzana",
    nota="La ficha parte la edad en cuatro tramos; el municipal usa otros cortes."))
A(I("pct_40_59", "De 40 a 59 años", "%", 0, G, n="mz", y12="no", uni="personas",
    fuente="ficha", e24="edad_40a59 / total de la manzana"))

G = "Agua"
A(I("pct_agua_vertiente", "Agua de vertiente", "%", -1, G, n="mz", y12="no",
    fuente="ficha", e24="vertienteprotegida + vertientenoprotegida",
    nota="La ficha separa vertiente protegida de no protegida; el microdato de "
         "2012 no, y por eso el indicador municipal no existe."))

G = "Energía y cocina"
A(I("pct_cocina_electricidad", "Cocina con electricidad", "%", 1, G, n="mz",
    y12="no", fuente="ficha", e24="combustible_electricidad"))
A(I("pct_cocina_solar", "Cocina con energía solar", "%", 1, G, n="mz",
    y12="no", fuente="ficha", e24="combustible_energíasolar"))

G = "Vivienda y materiales"
A(I("pct_hacinamiento_medio", "Hacinamiento medio", "%", -1, G, n="mz", y12="no",
    fuente="ficha", e24="hacinamiento_medio",
    nota="Más de dos y hasta tres personas por dormitorio, según el glosario "
         "del INE. El tramo 'alto' es el que se publica como pct_hacinamiento."))
A(I("pct_pared_tabique", "Paredes de tabique o quinche", "%", -1, G, n="mz",
    y12="no", fuente="ficha", e24="material_paredes_tabique"))
A(I("pct_piso_madera", "Piso de madera o machihembre", "%", 1, G, n="mz",
    y12="no", fuente="ficha", e24="material_piso_madera + machimbre"))
A(I("pct_piso_ladrillo", "Piso de ladrillo", "%", 0, G, n="mz", y12="no",
    fuente="ficha", e24="material_piso_ladrillo"))
A(I("pct_viv_colectiva", "Viviendas colectivas", "%", 0, G, n="mz", y12="no",
    uni="viv_part", fuente="ficha", e24="viviendatipo_colectiva",
    nota="Cuarteles, conventos, hoteles, hospitales. Se cuentan sobre el total "
         "de viviendas del manzano."))

G = "Hogares y jefatura"
A(I("pct_hogar_sin_jefe", "Hogares sin jefe declarado", "%", 0, G, n="mz",
    y12="no", uni="hogares", fuente="ficha", e24="hogar_sinjefe",
    nota="Categoría propia de la tipología del INE. Es la que explicaba el "
         "desajuste de pct_hogar_unipersonal contra el tabulado."))

G = "Empleo"
A(I("pct_rama_ensenanza", "Trabaja en enseñanza", "%", 0, G, n="mz", y12="no",
    uni="ocupados", fuente="ficha", e24="actividad_enseñanza"))
A(I("pct_rama_salud", "Trabaja en salud y asistencia", "%", 0, G, n="mz",
    y12="no", uni="ocupados", fuente="ficha", e24="actividad_saludyasistencia"))

G = "Migración y territorio"
A(I("pct_res5_extranjero", "Vivía en otro país hace 5 años", "%", 0, G, n="mz",
    y12="no", uni="personas", fuente="ficha", e24="residencia_otropais"))

# ── brechas de género ───────────────────────────────────────────────────────
# ★ La ficha parte 43 categorías por sexo, así que la brecha se puede medir
#   DENTRO de la manzana. Cada mitad se calcula sobre su propio denominador y
#   se restan: son puntos porcentuales de mujeres menos hombres.
#   ⚠️ En manzanas chicas la brecha es ruidosa por construcción (con 20 personas,
#   una sola cambia el número varios puntos). Se publican las cuatro que tienen
#   lectura territorial y no las 43 posibles.
G = "Educación"
A(I("brecha_edu_ninguno", "Brecha de género: sin educación", "pp", -1, G, n="mz",
    y12="no", s=True, uni="personas", fuente="ficha",
    e24="pp de mujeres sin educación menos pp de hombres"))
G = "Salud"
A(I("brecha_sin_seguro", "Brecha de género: sin seguro de salud", "pp", -1, G,
    n="mz", y12="no", s=True, uni="personas", fuente="ficha",
    e24="pp de mujeres sin seguro menos pp de hombres"))
G = "Empleo"
A(I("brecha_cuenta_propia", "Brecha de género: cuenta propia", "pp", 0, G,
    n="mz", y12="no", s=True, uni="ocupados", fuente="ficha",
    e24="pp de mujeres por cuenta propia menos pp de hombres"))


if __name__ == "__main__":
    import collections, json, pathlib, sys
    n = len(CATALOGO)
    claves = [i["k"] for i in CATALOGO]
    dup = [k for k, c in collections.Counter(claves).items() if c > 1]
    grupos = collections.Counter(i["g"] for i in CATALOGO)
    y12 = collections.Counter(i["y12"] for i in CATALOGO)

    print(f"CATÁLOGO — {n} indicadores en {len(grupos)} grupos")
    if dup:
        print(f"  ⛔ CLAVES DUPLICADAS: {dup}")
        sys.exit(1)
    print(f"\n{'grupo':<38}{'n':>4}{'con 2012':>10}{'manzana':>9}{'sexo':>7}")
    for g, c in grupos.most_common():
        d = [i for i in CATALOGO if i["g"] == g]
        print(f"  {g:<36}{c:>4}{sum(1 for i in d if i['y12']=='si'):>10}"
              f"{sum(1 for i in d if i['n']=='mun+mz'):>9}{sum(1 for i in d if i['s']):>7}")
    print(f"\n  serie 2012: {y12['si']} directos · {y12['ajuste']} con armonización · {y12['no']} sólo 2024")
    print(f"  bajan a manzana: {sum(1 for i in CATALOGO if i['n']=='mun+mz')}")
    print(f"  admiten corte por sexo: {sum(1 for i in CATALOGO if i['s'])}")
    print(f"  fuente microdato: {sum(1 for i in CATALOGO if i['fuente']=='microdato')}"
          f" · tabulado: {sum(1 for i in CATALOGO if i['fuente']=='tabulado')}"
          f" · geometría: {sum(1 for i in CATALOGO if i['fuente']=='geometría')}")
    print(f"  con hoja de validación declarada: {sum(1 for i in CATALOGO if i['val'])}")

    salida = pathlib.Path(__file__).parent / "catalogo.json"
    salida.write_text(json.dumps({"universos": UNIVERSOS, "indicadores": CATALOGO},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {salida}")
