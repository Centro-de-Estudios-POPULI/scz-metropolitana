# -*- coding: utf-8 -*-
"""
MOTOR DE CÁLCULO — una regla por indicador, los dos censos.
===========================================================

El problema que resuelve: los códigos de respuesta CAMBIARON entre 2012 y 2024.
Escribir `combustible == 1` da "gas domiciliario" en 2012 y "garrafa" en 2024.
No falla, no avisa: devuelve otro indicador.

Solución: una capa de ARMONIZACIÓN. Cada variable se traduce a códigos canónicos
con nombre, y las reglas se escriben una sola vez contra esos nombres.

★ DIFERENCIAS REALES ENCONTRADAS (leídas de los diccionarios, no supuestas):
  · combustible  2012 1=domiciliario 2=garrafa 3=elec 4=solar 5=leña 6=guano
                 2024 1=garrafa 2=domiciliario 3=leña 4=guano 5=elec 6=solar
  · tenencia     2012 1=propia          2024 1=propia pagada, 2=propia pagando
                 2012 5=cedida 6=prestada   2024 3=prestada 7=cedida
  · piso         2012 separa machihembre(3) y parquet(4); 2024 los junta en 3
                 ⇒ desde ahí TODO se corre un lugar
  · agua         2012 3=carro repartidor;  2024 8=carro repartidor
                 2012 6 junta "lluvia, río, vertiente, acequia" que 2024 abre en 3, 6 y 7
  · desagüe      2012 4,5,6 (calle / río / lago) = 2024 5 (superficie)
  · distribución 2012 tiene 4 categorías (separa "fuera del lote"); 2024 tiene 3
  · tipo viv.    2012 junta Casa/Choza/Pahuichi en 1; 2024 las separa en 1 y 2

Lo que NO es separable en 2012 queda declarado como tal, no forzado.
"""
import pathlib, sys, json, numpy as np, pandas as pd

CPV24 = pathlib.Path(r"C:\Users\HP\cpv2024")
CPV12 = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones"
                     r"\upre-nbi\datos\crudo\CPV2012 343M\baser")
sys.path.insert(0, r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones\upre-nbi\scripts")

# ── códigos canónicos ────────────────────────────────────────────────────────
# valor canónico -> {códigos de 2024}, {códigos de 2012}.  None = no separable.
MAPEO = {
 "agua": {
   "red":            ({1},   {1}),
   "pileta":         ({2},   {2}),
   "lluvia":         ({3},   None),      # 2012 la mezcla con río/vertiente
   "pozo_bomba":     ({4},   {4}),
   "pozo_sin_bomba": ({5},   {5}),
   "vertiente_prot": ({6},   None),
   "rio_acequia":    ({7},   None),
   "carro":          ({8},   {3}),       # ⚠ código distinto
   "otro":           ({9},   {7}),
   "superficie_2012":(set(), {6, 7}),    # el agregado que 2012 sí permite
 },
 "agua_dist": {
   "dentro":  ({1}, {1}),
   "en_lote": ({2}, {2}),
   "sin_red": ({3}, {3, 4}),             # 2012 separa "fuera del lote"
 },
 "servsan": {"exclusivo": ({1}, {1}), "compartido": ({2}, {2}), "no_tiene": ({3}, {3})},
 "desague": {
   "alcantarillado": ({1}, {1}),
   "camara":         ({2}, {2}),
   "pozo_ciego":     ({3}, {3}),
   "absorcion":      ({4}, None),
   "superficie":     ({5}, {4, 5, 6}),   # 2012: calle / río / lago
   "ecologico":      ({6}, None),
 },
 "energia": {"red": ({1}, {1}), "motor": ({2}, {2}), "solar": ({3}, {3}),
             "otra": ({4}, {4}), "no_tiene": ({5}, {5})},
 "combus": {                              # ⚠ el más traicionero
   "garrafa":     ({1}, {2}),
   "domiciliario":({2}, {1}),
   "lena":        ({3}, {5}),
   "guano":       ({4}, {6}),
   "electricidad":({5}, {3}),
   "solar":       ({6}, {4}),
   "otro":        ({7}, {7}),
   "no_cocina":   ({8}, {8}),
 },
 "basura": {"contenedor": ({1}, {1}), "carro": ({2}, {2}), "baldio": ({3}, {3}),
            "rio": ({4}, {4}), "quema": ({5}, {5}), "entierra": ({6}, {6}),
            "otra": ({7}, {7})},
 "tenencia": {
   "propia":    ({1, 2}, {1}),           # 2024 la parte en pagada/pagando
   "alquilada": ({4},    {2}),
   "anticretico": ({5, 6}, {3, 4}),
   # ⚠️ SEPARADAS (2026-08-13): el INE las publica aparte y juntarlas hacía que
   #    `pct_viv_prestada` prometiera menos de lo que medía.
   #    2024 3=prestada 7=cedida · 2012 6=prestada 5=cedida
   "prestada": ({3}, {6}),
   "cedida":   ({7}, {5}),
   "otra":      ({8},    {7}),
 },
 "pared": {"ladrillo": ({1}, {1}), "adobe": ({2}, {2}), "tabique": ({3}, {3}),
           "piedra": ({4}, {4}), "madera": ({5}, {5}), "cana": ({6}, {6}),
           "otro": ({7}, {7})},
 "techo": {"calamina": ({1}, {1}), "teja": ({2}, {2}), "losa": ({3}, {3}),
           "paja": ({4}, {4}), "otro": ({5}, {5})},
 "piso": {                                # ⚠ desde el 3 todo se corre
   "tierra": ({1}, {1}), "tablon": ({2}, {2}),
   "machimbre_parquet": ({3}, {3, 4}),
   "ceramica": ({4}, {5}), "cemento": ({5}, {6}),
   "mosaico": ({6}, {7}), "ladrillo": ({7}, {8}),
   "flotante": ({8}, None), "otro": ({9}, {9}),
 },
 "cocina": {"si": ({1}, {1}), "no": ({2}, {2})},
 # ⚠️ tipo de vivienda: 2012 junta "Casa/Choza/Pahuichi" en el código 1, así que
 #    desde ahí todo se corre y `choza` no es separable en ese censo.
 "tipoviv": {
   "casa":         ({1}, {1}),
   "choza":        ({2}, None),
   "departamento": ({3}, {2}),
   "cuarto":       ({4}, {3}),
   "improvisada":  ({5}, {4}),
   "local":        ({6}, {5}),
 },
 "revoque": {"si": ({1}, {1}), "no": ({2}, {2})},
 "emigrante": {"si": ({1}, {1}), "no": ({2}, {2})},
 "fallecido": {"si": ({1}, {1}), "no": ({2}, {2})},
 "urbrur": {"urbana": ({1}, {1}), "rural": ({2}, {2})},
 # TIC y equipamiento: 1=Sí, 2=No, 9=Sin especificar en los dos censos
 **{k: {"si": ({1}, {1}), "no": ({2}, {2})} for k in
    ("radio", "tv", "compu", "internet", "telefono",
     "auto", "bici", "moto", "carreta", "bote")},
 # sólo 2024 — el censo de 2012 no preguntaba por estos bienes
 **{k: {"si": ({1}, set()), "no": ({2}, set())} for k in
    ("celular", "inetfijo", "inetmovil", "tvcable", "telfijo",
     "refri", "micro", "calefon", "aire", "lavadora")},
}

COLS24 = {"agua": "v07_aguapro", "agua_dist": "v08_aguadist", "servsan": "v15_servsan",
          "desague": "v16_desague", "energia": "v09_energia", "combus": "v10_combus",
          "basura": "v11_basura", "tenencia": "v17_tenencia", "pared": "v03_pared",
          "techo": "v05_techo", "piso": "v06_piso", "cocina": "v12_cocina",
          "urbrur": "urbrur", "revoque": "v04_revoq", "tipoviv": "v01_tipoviv",
          "emigrante": "v20a_emi", "fallecido": "v21a_fal",
          "radio": "v19a_radio", "tv": "v19b_tv", "compu": "v19c_compu",
          "celular": "v19d_celular", "inetfijo": "v19e_inetfijo",
          "inetmovil": "v19f_inetmovil", "tvcable": "v19g_tvcable",
          "telfijo": "v19h_telfijo", "auto": "v18c_auto", "bici": "v18a_bici",
          "moto": "v18b_moto", "carreta": "v18d_carreta", "bote": "v18e_bote",
          "refri": "v18f_refri", "micro": "v18g_micro", "calefon": "v18h_calefon",
          "aire": "v18i_aire", "lavadora": "v18j_lavadora"}
COLS12 = {"agua": "P07", "agua_dist": "P08", "servsan": "P09", "desague": "P10",
          "energia": "P11", "combus": "P12", "basura": "P16", "tenencia": "P19",
          "pared": "P03", "techo": "P05", "piso": "P06", "cocina": "P13",
          "urbrur": "URBRUR", "revoque": "P04", "tipoviv": "P01",
          "emigrante": "P20A", "fallecido": "P21A",
          # ⚠️ 2012 junta telefonía fija y celular en UNA pregunta (P17E) y no
          #    separa internet fijo de móvil (P17D): esos indicadores sólo son
          #    comparables al nivel agregado.
          "radio": "P17A", "tv": "P17B", "compu": "P17C", "internet": "P17D",
          "telefono": "P17E", "auto": "P18A", "bici": "P18B", "moto": "P18C",
          "carreta": "P18D", "bote": "P18E"}


def _canon(serie, mapa, censo):
    """Traduce códigos crudos a canónicos. Devuelve Series de strings."""
    i = 0 if censo == 2024 else 1
    out = pd.Series(np.full(len(serie), "", dtype=object), index=serie.index)
    for nombre, pares in mapa.items():
        cods = pares[i]
        if not cods:
            continue
        out[serie.isin(list(cods))] = nombre
    return out


def _derivar_24(v):
    d = pd.DataFrame(index=v.index)
    d["cod_ine"] = v.idep.str.zfill(2) + v.iprov.str.zfill(2) + v.imun.str.zfill(2)
    d["tip_hog"] = pd.to_numeric(v["tip_hog"], errors="coerce")
    for c, dest in [("v01_tipoviv", "tipo"), ("v02_condocup", "ocup"),
                    ("tot_pers", "tot_pers"), ("v13_habitac", "habitac"),
                    ("v14_dormit", "dormit")]:
        d[dest] = pd.to_numeric(v[c], errors="coerce")
    for canon, col in COLS24.items():
        d[canon] = _canon(pd.to_numeric(v[col], errors="coerce"), MAPEO[canon], 2024)
    # universo: particular (1..6) y ocupada con personas presentes
    d["univ"] = d.tipo.between(1, 6) & d.ocup.isin([0, 1])
    return d


def cargar_2024():
    """Lectura POR BLOQUES, derivando en cada uno. Acumular las ~40 columnas de
    texto de 4,5 M de viviendas antes de derivar agota la memoria — y más aún si
    hay otro motor corriendo en paralelo."""
    cols = ["idep", "iprov", "imun", "v01_tipoviv", "v02_condocup", "tot_pers",
            "v13_habitac", "v14_dormit", "tip_hog"] + list(COLS24.values())
    partes = []
    for ch in pd.read_csv(CPV24 / "Vivienda_CPV-2024.csv", sep=";", usecols=cols,
                          dtype=str, encoding="latin-1", chunksize=1_500_000,
                          low_memory=False):
        partes.append(_derivar_24(ch))
    d = pd.concat(partes, ignore_index=True)
    return _completar(d)


def _completar(d):
    """Toda variable canónica que el censo no tenga se crea vacía. Sin esto, una
    regla que menciona `celular` —que no existe en 2012— revienta con
    AttributeError en vez de devolver 0%."""
    for canon in MAPEO:
        if canon not in d.columns:
            d[canon] = ""
    # ★ las ~40 columnas canónicas son texto repetido: como `category` ocupan una
    #   fracción. Sin esto el motor se queda sin memoria al crecer el catálogo
    #   ("Unable to allocate ... MiB").
    for canon in MAPEO:
        d[canon] = d[canon].astype("category")
    for c in ("tipo", "ocup", "habitac", "dormit", "tip_hog"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").astype("float32")
    d["tot_pers"] = pd.to_numeric(d["tot_pers"], errors="coerce").astype("float32")
    return d


def cargar_2012():
    from redatam import RedatamDB
    db = RedatamDB(str(CPV12))
    cods = db.codigos_municipio()
    mun = db.municipio_de("VIVIENDA")
    d = pd.DataFrame({"cod_ine": pd.Categorical.from_codes(mun, cods).astype(str)})
    d["tipo"] = db.leer("VIVIENDA:P01")
    d["ocup"] = db.leer("VIVIENDA:P02")
    d["tot_pers"] = db.leer("VIVIENDA:TOTPERS_VIV")
    d["tip_hog"] = np.nan   # 2012 no trae la tipología de hogar derivada
    d["habitac"] = db.leer("VIVIENDA:P14")
    d["dormit"] = db.leer("VIVIENDA:P15")
    for canon, col in COLS12.items():
        d[canon] = _canon(pd.Series(db.leer("VIVIENDA:" + col)), MAPEO[canon], 2012)
    # ★ universo POSICIONAL: la categoría 5 es "Local no destinado para vivienda"
    #   y SÍ es particular — filtrarla por el rótulo deja fuera 12.861 viviendas.
    d["univ"] = d.tipo.between(1, 5) & d.ocup.isin([0, 1])
    return _completar(d)


# ── reglas: UNA por indicador, escritas contra códigos canónicos ─────────────
R = lambda f: f


def U(f):
    """Regla de UNIÓN deliberada.

    `pct_internet` y `pct_telefonia` mencionan a propósito variables que un censo
    no tiene (internet fijo/móvil no existen en 2012): suman lo que haya en cada
    censo para que la serie sea legítima. La guarda de `calcular` anula un
    indicador cuando toca una variable ausente; estas quedan exceptuadas.
    """
    f.union = True
    return f


# ── indicadores que un censo NO PUEDE SEPARAR aunque la variable exista ──────
# ⚠️ No es que valgan 0: es que la categoría está FUNDIDA con otra en ese censo,
#    y publicar 0,00% inventa una caída intercensal que nunca ocurrió.
#    · 2012 junta "Casa / Choza / Pahuichi" en una sola categoría.
#    · el código 6 de agua en 2012 junta "lluvia, río, vertiente, acequia",
#      que 2024 abre en tres.
NO_SEPARABLE = {2012: {"pct_choza", "pct_agua_rio", "pct_agua_lluvia",
                       # ★ DESCUBIERTO AL VALIDAR (2026-08-13): daba 3/343 contra
                       #   el tabulado. La causa es la misma categoría fundida:
                       #   "lluvia, río, vertiente, acequia" mezcla fuentes
                       #   PROTEGIDAS y NO PROTEGIDAS, así que en 2012 no se
                       #   puede decidir de qué lado cae. Incluirla sobrecuenta
                       #   (mete vertiente protegida y cosecha de lluvia) y
                       #   excluirla subcuenta, que es lo que hacía el motor.
                       #   No hay respuesta correcta: el indicador no es
                       #   comparable en 2012 y va sin dato.
                       "pct_agua_no_mejorada", "pct_agua_mejorada"}}
REGLAS = {
 "pct_agua_caneria":       R(lambda d: d.agua == "red"),
 "pct_agua_pileta":        R(lambda d: d.agua == "pileta"),
 "pct_agua_pozo":          R(lambda d: d.agua.isin(["pozo_bomba", "pozo_sin_bomba"])),
 "pct_agua_pozo_bomba":    R(lambda d: d.agua == "pozo_bomba"),
 "pct_agua_carro":         R(lambda d: d.agua == "carro"),
 "pct_agua_interior":      R(lambda d: d.agua_dist == "dentro"),
 "pct_agua_lote":          R(lambda d: d.agua_dist == "en_lote"),
 "pct_agua_sin_caneria":   R(lambda d: d.agua_dist == "sin_red"),
 "pct_servicio_sanitario": R(lambda d: d.servsan.isin(["exclusivo", "compartido"])),
 "pct_sanitario_exclusivo":R(lambda d: d.servsan == "exclusivo"),
 "pct_sanitario_compartido":R(lambda d: d.servsan == "compartido"),
 "pct_sin_sanitario":      R(lambda d: d.servsan == "no_tiene"),
 "pct_alcantarillado":     R(lambda d: d.desague == "alcantarillado"),
 "pct_camara_septica":     R(lambda d: d.desague == "camara"),
 "pct_pozo_ciego":         R(lambda d: d.desague == "pozo_ciego"),
 "pct_desague_superficie": R(lambda d: d.desague == "superficie"),
 "pct_electricidad":       R(lambda d: d.energia.isin(["red", "motor", "solar", "otra"])),
 "pct_elec_red":           R(lambda d: d.energia == "red"),
 "pct_panel_solar":        R(lambda d: d.energia == "solar"),
 "pct_motor_propio":       R(lambda d: d.energia == "motor"),
 "pct_sin_energia":        R(lambda d: d.energia == "no_tiene"),
 "pct_gas_red":            R(lambda d: d.combus == "domiciliario"),
 "pct_gas_garrafa":        R(lambda d: d.combus == "garrafa"),
 "pct_lena_guano":         R(lambda d: d.combus.isin(["lena", "guano"])),
 "pct_combustible_limpio": R(lambda d: d.combus.isin(["garrafa", "domiciliario",
                                                      "electricidad", "solar"])),
 "pct_no_cocina":          R(lambda d: d.combus == "no_cocina"),
 "pct_cocina_exclusiva":   R(lambda d: d.cocina == "si"),
 "pct_basura_formal":      R(lambda d: d.basura.isin(["contenedor", "carro"])),
 "pct_basura_carro":       R(lambda d: d.basura == "carro"),
 "pct_basura_contenedor":  R(lambda d: d.basura == "contenedor"),
 "pct_basura_quema":       R(lambda d: d.basura == "quema"),
 "pct_basura_entierra":    R(lambda d: d.basura == "entierra"),
 "pct_basura_informal":    R(lambda d: d.basura.isin(["baldio", "rio"])),
 "pct_viv_propia":         R(lambda d: d.tenencia == "propia"),
 "pct_viv_alquilada":      R(lambda d: d.tenencia == "alquilada"),
 "pct_viv_anticretico":    R(lambda d: d.tenencia == "anticretico"),
 "pct_viv_prestada":       R(lambda d: d.tenencia == "prestada"),
 "pct_viv_cedida":         R(lambda d: d.tenencia == "cedida"),
 "pct_pared_ladrillo":     R(lambda d: d.pared == "ladrillo"),
 "pct_pared_adobe":        R(lambda d: d.pared == "adobe"),
 "pct_pared_madera":       R(lambda d: d.pared == "madera"),
 "pct_pared_precaria":     R(lambda d: d.pared == "cana"),
 "pct_techo_calamina":     R(lambda d: d.techo == "calamina"),
 "pct_techo_teja":         R(lambda d: d.techo == "teja"),
 "pct_techo_losa":         R(lambda d: d.techo == "losa"),
 "pct_techo_paja":         R(lambda d: d.techo == "paja"),
 "pct_piso_tierra":        R(lambda d: d.piso == "tierra"),
 "pct_piso_cemento":       R(lambda d: d.piso == "cemento"),
 # ⚠️ SEPARADOS (2026-08-13): sumarlos bajo el nombre "cerámica" era engañoso.
 "pct_piso_ceramica":      R(lambda d: d.piso == "ceramica"),
 "pct_piso_mosaico":       R(lambda d: d.piso == "mosaico"),
 "pct_monoambiente":       R(lambda d: d.habitac == 1),
 "pct_urbano":             R(lambda d: d.urbrur == "urbana"),
 # ⚠️ `pct_hogar_unipersonal` SE MUDÓ a motor_persona.py: el glosario del INE
 #    exige que la persona sea JEFA/JEFE de hogar, y este motor no conoce el
 #    parentesco. Con `tot_pers == 1` a secas validaba 141/343.
 "pct_revoque":            R(lambda d: d.revoque == "si"),
 # tipología de hogar: sólo 2024 (2012 no la trae derivada; se podría construir
 # desde el parentesco a nivel persona, que es otro trabajo)
 "pct_hogar_nuclear":      R(lambda d: d.tip_hog.isin([2, 4])),
 "pct_hogar_monoparental": R(lambda d: d.tip_hog == 3),
 "pct_hogar_extendido":    R(lambda d: d.tip_hog == 5),
 "pct_hogar_compuesto":    R(lambda d: d.tip_hog == 6),
 "pct_departamento":       R(lambda d: d.tipoviv == "departamento"),
 "pct_con_emigrante":      R(lambda d: d.emigrante == "si"),
 "pct_hogar_fallecido":    R(lambda d: d.fallecido == "si"),
 # hacinamiento: más de 3 personas por dormitorio (dormitorios en 0 = sin dato)
 # ★ GLOSARIO DEL INE: la relación personas/dormitorios es "bajo o sin
 #   hacinamiento hasta dos · medio más de dos hasta tres · ALTO MAYOR A TRES".
 #   Nuestro umbral (>3) YA era el suyo; lo que fallaba eran las viviendas SIN
 #   DORMITORIO, que `replace(0, nan)` mandaba a NaN y quedaban fuera. Un hogar
 #   sin ningún cuarto para dormir es el caso máximo de hacinamiento, no un
 #   dato faltante.
 "pct_hacinamiento":       R(lambda d: (d.dormit == 0)
                                       | ((d.tot_pers / d.dormit.replace(0, np.nan)) > 3)),
 # ⚠️ `pct_choza` NO es separable en 2012: ese censo junta "Casa/Choza/Pahuichi"
 #    en una sola categoría. Queda como indicador sólo-2024.
 "pct_choza":              R(lambda d: d.tipoviv == "choza"),
 "pct_agua_rio":           R(lambda d: d.agua == "rio_acequia"),
 "pct_agua_lluvia":        R(lambda d: d.agua == "lluvia"),
 "pct_agua_no_mejorada":   R(lambda d: d.agua.isin(["pozo_sin_bomba", "rio_acequia", "carro"])),
 "pct_agua_mejorada":      R(lambda d: ~d.agua.isin(["pozo_sin_bomba", "rio_acequia", "carro", ""])),
 "pct_saneamiento_mejorado": R(lambda d: d.desague.isin(["alcantarillado", "camara"])
                                          & (d.servsan == "exclusivo")),
 # ── TIC y equipamiento ──
 "pct_radio":       R(lambda d: d.radio == "si"),
 "pct_televisor":   R(lambda d: d.tv == "si"),
 "pct_computadora": R(lambda d: d.compu == "si"),
 "pct_auto":        R(lambda d: d.auto == "si"),
 "pct_bicicleta":   R(lambda d: d.bici == "si"),
 "pct_moto":        R(lambda d: d.moto == "si"),
 "pct_carreta":     R(lambda d: d.carreta == "si"),
 "pct_bote":        R(lambda d: d.bote == "si"),
 # internet y telefonía: en 2012 vienen agregados, así que la regla usa el
 # agregado en los dos censos para que la serie sea legítima (ver `U`)
 "pct_internet":    U(lambda d: (d.internet == "si") | (d.inetfijo == "si") | (d.inetmovil == "si")),
 "pct_telefonia":   U(lambda d: (d.telefono == "si") | (d.celular == "si") | (d.telfijo == "si")),
 # sólo 2024 (el censo de 2012 no preguntaba por estos bienes)
 "pct_celular":     R(lambda d: d.celular == "si"),
 "pct_internet_fijo":  R(lambda d: d.inetfijo == "si"),
 "pct_internet_movil": R(lambda d: d.inetmovil == "si"),
 "pct_tv_cable":    R(lambda d: d.tvcable == "si"),
 "pct_telefono_fijo": R(lambda d: d.telfijo == "si"),
 "pct_refrigerador":R(lambda d: d.refri == "si"),
 "pct_microondas":  R(lambda d: d.micro == "si"),
 "pct_calefon":     R(lambda d: d.calefon == "si"),
 "pct_aire_acond":  R(lambda d: d.aire == "si"),
 "pct_lavadora":    R(lambda d: d.lavadora == "si"),
}
# indicadores que no son una proporción de viviendas: son RAZONES DE DOS TOTALES.
#
# ★★ NO SON PROMEDIOS DE RAZONES (corregido y VALIDADO el 2026-08-15, 343/343).
#    El INE publica los tres en `vivienda_hogar/15` y su cuenta es
#    **suma(personas) / suma(dormitorios)**, con las personas de TODAS las
#    viviendas del universo en el numerador —incluidas las que declaran CERO
#    dormitorios, que aportan gente pero no dormitorios (139.293 viviendas)—.
#    Se probaron cuatro definiciones contra el tabulado antes de tocar nada:
#      · media de razones por vivienda   3/343  (+0,195: una casa de 1 persona en
#        1 dormitorio pesa igual que una de 8 en 2, así que infla)
#      · totales excluyendo las de 0 dor 0/343  (−0,078)
#      · las de 0 dor contadas como 1    1/343  (−0,062)
#      · **totales, 0 dor sin denominador  343/343  (exacto)**
#    `tam_hogar` ya cerraba 343/343 porque su denominador es el CONTEO de
#    viviendas, y ahí promediar y dividir totales son la misma cuenta.
#
# ⚠️ `pers_x_vivienda` es UN DUPLICADO EXACTO de `tam_hogar` —los dos declaran
#    `media(tot_pers)`— y el Atlas publica los dos con el mismo número bajo dos
#    nombres. Queda una decisión de producto: cuál de los dos se queda.
#
#   clave                numerador             denominador (None = contar viviendas)
RAZONES_VIV = {
 "tam_hogar":        (lambda d: d.tot_pers,  None),
 "pers_x_vivienda":  (lambda d: d.tot_pers,  None),
 "pers_x_dormitorio":(lambda d: d.tot_pers,  lambda d: d.dormit),
 "pers_x_habitacion":(lambda d: d.tot_pers,  lambda d: d.habitac),
}


def _ausentes(d):
    """Columnas que ESTE censo no trae.

    Se detecta por el DATO —`_completar` las dejó vacías— y no por una lista a
    mano, para que no se desincronice cuando el catálogo crezca.
    """
    out = set()
    for c in d.columns:
        s = d[c]
        if s.isna().all():          # numéricas que el censo no trae (tip_hog)
            out.add(c)
            continue
        # ⚠️ Esta versión de pandas usa un dtype `str` NATIVO (`dtype.name ==
        #    "str"`), no `object`. Preguntar por "object"/"category" dejaba
        #    fuera TODAS las columnas de texto y el guard no se disparaba:
        #    `pct_celular` seguía saliendo 0,00% en 2012. Se pregunta por lo que
        #    la columna NO es —numérica— en vez de enumerar dtypes de texto.
        if not pd.api.types.is_numeric_dtype(s) and (s.astype(str) == "").all():
            out.add(c)
    return out


def calcular(d, anio=None):
    """Devuelve DataFrame municipio × indicador para un censo ya cargado."""
    u = d[d.univ]
    tot = u.groupby("cod_ine").size()
    out = {"n_viviendas": tot}
    # ⚠️ Un indicador cuya variable este censo no preguntó tiene que salir VACÍO,
    #    no en 0,00%. Un 0 se lee como "ninguna vivienda lo tenía" y en la serie
    #    intercensal fabrica un salto: `pct_celular` daba 0% en 2012 y 41% en
    #    2024, o sea "+41 pp", cuando el censo de 2012 ni preguntaba por celular.
    falt = _ausentes(d) | {"__nada__"}
    vacio = pd.Series(np.nan, index=tot.index)
    for k, f in REGLAS.items():
        toca_ausente = set(f.__code__.co_names) & falt
        if (toca_ausente and not getattr(f, "union", False)) \
           or k in NO_SEPARABLE.get(anio, set()):
            out[k] = vacio
            continue
        out[k] = 100 * u[f(u)].groupby("cod_ine").size().reindex(tot.index, fill_value=0) / tot
    # ★ universo propio: se mide sobre TODAS las viviendas particulares, no sólo
    #   las ocupadas — si no, el indicador sería idénticamente cero.
    m_part = d.tipo.between(1, 6) if d.tipo.max() > 5 else d.tipo.between(1, 5)
    m_desoc = m_part & d.ocup.isin([3, 4, 5])
    out["pct_vivienda_desocupada"] = (
        100 * d.loc[m_desoc].groupby("cod_ine").size()
        / d.loc[m_part].groupby("cod_ine").size()).reindex(tot.index)
    for k, (f_num, f_den) in RAZONES_VIV.items():
        num = f_num(u)
        if f_den is None:                      # denominador = cantidad de viviendas
            out[k] = num.groupby(u.cod_ine).mean()
            out["_den_" + k] = tot
            continue
        # ⚠️ SIN filtrar por denominador > 0: las viviendas que declaran cero
        #    dormitorios entran al numerador con su gente y no suman dormitorios.
        #    Excluirlas da 0/343 contra el tabulado; incluirlas, 343/343.
        den = f_den(u).groupby(u.cod_ine).sum().reindex(tot.index)
        out[k] = num.groupby(u.cod_ine).sum().reindex(tot.index) / den
        out["_den_" + k] = den
    return pd.DataFrame(out)


if __name__ == "__main__":
    print("cargando 2024 …", flush=True)
    d24 = cargar_2024()
    print("cargando 2012 …", flush=True)
    d12 = cargar_2012()
    salida = pathlib.Path(__file__).parent
    for anio, d in ((2024, d24), (2012, d12)):
        r = calcular(d, anio)
        r.to_csv(salida / f"municipal_{anio}.csv", encoding="utf-8")
        print(f"{anio}: {int(r.n_viviendas.sum()):,} viviendas · {len(r)} municipios "
              f"· {len(r.columns)} indicadores")
        # ★ AGREGADO URBANO — la cifra del medio del Tablero 2. Es el único
        #   universo estrictamente comparable con las fichas por manzana, que
        #   cubren sólo el área urbana censada. La distancia entre esta cifra y
        #   la municipal ES el sesgo urbano, medido en vez de advertido.
        ru = calcular(d[d.urbrur == "urbana"], anio)
        ru.to_csv(salida / f"municipal_urbano_{anio}.csv", encoding="utf-8")
        print(f"      urbano: {int(ru.n_viviendas.sum()):,} viviendas · {len(ru)} municipios")
    print("→ municipal_{2024,2012}.csv · municipal_urbano_{2024,2012}.csv")
