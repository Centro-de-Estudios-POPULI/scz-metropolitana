"""
Región Metropolitana de Santa Cruz — indicadores censales por manzana.

Deriva indicadores desde las 137 variables CRUDAS del Censo 2024 a nivel de
manzano (mauforonda/atlasurbano, que a su vez las baja del geoportal del INE) y
produce, para los 9 municipios de la región:

    datos/manzanas_<municipio>.geojson   una por municipio, para cargar por zoom
    datos/catalogo.json                  grupos + indicadores con `dir` editorial
    datos/municipios.json                agregado municipal (el piso de arriba)

Estructura del catálogo = la del Atlas Socioeconómico / Fiscal, a propósito: el
motor de mapa ya sabe leer ese esquema (clave, label, unit, dir, desc) y aplica
la escala divergente con ancla real y rampa orientada por `dir`.

DENOMINADORES. Las fichas son CONTEOS. Cada familia de variables tiene su propio
universo y se cierra sobre sí misma: los porcentajes de educación se calculan
sobre el total de personas con dato educativo, los de agua sobre el total de
viviendas con dato de agua, etc. NO se usa `personas` como denominador
universal — daría porcentajes que no suman 100 y no son comparables entre
familias.

COBERTURA. El INE sólo publica ficha completa donde hay suficientes personas
(privacidad). En los 9 municipios eso es el 66% de las manzanas, pero el 93,8%
de la población. Las manzanas sin ficha se conservan en el GeoJSON con los
indicadores en null: aparecer en gris ES información —dice que la manzana
existe y que el censo no la publicó— y desaparecerlas dejaría agujeros que el
lector leería como "no hay nadie".
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkb

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "fuente"
SALIDA = RAIZ / "datos"
# Censo municipal del Atlas Socioeconómico: 343 municipios × 136 indicadores,
# cobertura TOTAL del territorio. Es el piso de arriba del tablero.
ATLAS_MUNICIPAL = (RAIZ.parent / "Observatorio de Presupuesto Fiscal Departamental"
                   / "_github_atlas_fiscal" / "data.json")

# ── Los 9 ────────────────────────────────────────────────────────────────────
# Núcleo legal de la Región Metropolitana (Ley Departamental 339 / "Santa Cruz
# Metrópoli") + 3 de área de influencia. El nombre es el que usa el parquet;
# `sigep` es la clave de la espina madre (bo-geo-maestro), que es como se une
# con el Atlas Fiscal.
MUNICIPIOS = [
    # (nombre canónico,             sigep, cod_ine, ámbito)
    ("Santa Cruz de la Sierra",     "1701", "070101", "núcleo"),
    ("Cotoca",                      "1702", "070102", "núcleo"),
    ("Porongo",                     "1703", "070103", "núcleo"),
    ("La Guardia",                  "1704", "070104", "núcleo"),
    ("El Torno",                    "1705", "070105", "núcleo"),
    ("Warnes",                      "1706", "070201", "núcleo"),
    ("Montero",                     "1734", "071001", "influencia"),
    ("Pailón",                      "1714", "070502", "influencia"),
    ("Colpa Bélgica",               "1756", "070603", "influencia"),
]

def _norm(s):
    """Clave de cruce robusta: sin tildes, sin caja, sin espacios de más.
    El parquet escribe 'Santa Cruz De La Sierra' (con De mayúscula) y el nombre
    canónico es 'de la'; cruzar por cadena exacta dejaba a la capital afuera en
    silencio, con el 76% de la población de la región. Si el INE vuelve a cambiar
    la capitalización, esto lo absorbe."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


NOMBRE_A_META = {n: {"sigep": s, "cod_ine": c, "ambito": a} for n, s, c, a in MUNICIPIOS}
NORM_A_NOMBRE = {_norm(n): n for n in NOMBRE_A_META}

# ── Catálogo de indicadores ──────────────────────────────────────────────────
# `dir`:  +1 más es mejor · −1 más es peor · 0 sin lado favorable (contexto).
# `div`:  la variable cruza el cero y el pivote con sentido es el CERO.
# `num`/`den`: listas de columnas crudas que se suman. El indicador es num/den.
# `expr`: derivación especial (se resuelve a mano abajo).
def _sx(base, opciones):
    """Expande una familia a sus columnas por sexo."""
    return [f"{base}_{o}_{s}" for o in opciones for s in ("hombre", "mujer")]


EDU_TODOS = _sx("educacion", ["ninguno", "primaria", "secundaria", "superior", "sinespecificar"])
SAL_TODOS = _sx("saludafiliacion", ["sus", "cajadesalud", "seguroprivado", "ninguno", "sinespecificar"])
ATE_TODOS = _sx("salud", ["centropublico", "cajadesalud", "centroprivado", "atenciondomicilio",
                          "medicinatradicional", "farmaciasinreceta", "remedioscaseros"])
OCU_TODOS = _sx("ocupacion", ["empleado", "cuentapropia", "otros", "sinespecificar"])
ACT_OPC = ["agricultura", "comercio", "manufactura", "construccion", "transporte",
           "alojamientoycomida", "enseñanza", "saludyasistencia", "otras", "sinespecificar"]
ACT_TODOS = _sx("actividad", ACT_OPC)
NAC_TODOS = _sx("nacimiento", ["aqui", "otromunicipio", "otropais", "sinespecificar"])
RES_TODOS = _sx("residencia", ["aqui", "otromunicipio", "otropais", "sinespecificar"])
EDAD_TODOS = _sx("edad", ["0a19", "20a39", "40a59", "60omas"])

VIV_TEN = [f"viviendatenencia_{o}" for o in ("propia", "alquilada", "anticretico", "prestada", "otra")]
VIV_TIPO = [f"viviendatipo_{o}" for o in ("particular", "personaspresentes", "personasausentes",
                                          "particulardesocupada", "colectiva")]
ENE = [f"energiaelectrica_{o}" for o in ("serviciopublico", "motorpropio", "panelsolar", "otra", "notiene")]
AGUA = [f"agua_{o}" for o in ("cañería", "piletapública", "carrorepartidor", "pozoconbomba",
                              "pozosinbomba", "vertientenoprotegida", "vertienteprotegida",
                              "cosechadelluvia", "otra")]
DES = [f"desague_{o}" for o in ("alcantarillado", "camaraséptica", "pozociego", "superficie",
                                "pozodeabsorción", "bañoecológico", "notiene")]
COMB = [f"combustible_{o}" for o in ("gasgarrafa", "gascañería", "leña", "guano", "electricidad",
                                     "energíasolar", "otro", "nococina")]
BAS = [f"basura_{o}" for o in ("basureropúblico", "carrobasurero", "calle", "río", "quema",
                               "entierra", "otro")]

CATALOGO = [
 ("poblacion", "Población y hogar", [
   ("personas",        "Personas",                    "hab",    0, None, None, "Población censada en la manzana."),
   ("viviendas",       "Viviendas",                   "viv",    0, None, None, "Viviendas censadas en la manzana."),
   ("pers_x_vivienda", "Personas por vivienda",       "pers",  -1, None, None, "Personas por vivienda ocupada. Valores altos indican hacinamiento potencial."),
   ("densidad",        "Densidad",                    "hab/ha", 0, None, None, "Personas por hectárea de superficie de la manzana."),
   ("pct_menor20",     "Menores de 20 años",          "%",      0, _sx("edad", ["0a19"]), EDAD_TODOS, "Peso de la población de 0 a 19 años."),
   ("pct_60mas",       "60 años y más",               "%",      0, _sx("edad", ["60omas"]), EDAD_TODOS, "Peso de la población de 60 años o más."),
   ("dependencia",     "Razón de dependencia",        "%",     -1, None, None, "Población de 0-19 y 60+ por cada 100 personas de 20 a 59 años."),
   ("masculinidad",    "Índice de masculinidad",      "h/100m", 0, None, None, "Hombres por cada 100 mujeres."),
 ]),
 ("migracion", "Migración", [
   ("pct_nacido_otro_mun", "Nacidos en otro municipio", "%", 0, _sx("nacimiento", ["otromunicipio"]), NAC_TODOS, "Personas nacidas en otro municipio del país."),
   ("pct_nacido_exterior", "Nacidos en el exterior",    "%", 0, _sx("nacimiento", ["otropais"]),      NAC_TODOS, "Personas nacidas en otro país."),
   ("pct_residia_otro_mun","Residía en otro municipio", "%", 0, _sx("residencia", ["otromunicipio"]), RES_TODOS, "Migración reciente: residía en otro municipio."),
 ]),
 ("educacion", "Educación", [
   ("pct_educ_superior",   "Educación superior",       "%",  1, _sx("educacion", ["superior"]), EDU_TODOS, "Personas con nivel educativo superior alcanzado."),
   ("pct_sin_educacion",   "Sin nivel educativo",      "%", -1, _sx("educacion", ["ninguno"]),  EDU_TODOS, "Personas sin ningún nivel educativo alcanzado."),
   ("brecha_educ_superior","Brecha de género: superior","pp", 0, None, None, "Puntos porcentuales de diferencia (hombres − mujeres) en educación superior. Positivo = ventaja masculina."),
   ("brecha_sin_educacion","Brecha de género: sin educación","pp",0, None, None, "Puntos porcentuales de diferencia (hombres − mujeres) sin nivel educativo. Negativo = las mujeres están peor."),
 ]),
 ("salud", "Salud", [
   ("pct_sin_seguro",     "Sin afiliación a salud",   "%", -1, _sx("saludafiliacion", ["ninguno"]),       SAL_TODOS, "Personas sin ninguna afiliación a un seguro de salud."),
   ("pct_sus",            "Afiliados al SUS",         "%",  0, _sx("saludafiliacion", ["sus"]),           SAL_TODOS, "Personas afiliadas al Sistema Único de Salud."),
   ("pct_seguro_privado", "Seguro privado",           "%",  0, _sx("saludafiliacion", ["seguroprivado"]), SAL_TODOS, "Personas con seguro de salud privado."),
   ("pct_automedicacion", "Automedicación",           "%", -1, _sx("salud", ["farmaciasinreceta"]),       ATE_TODOS, "Personas que ante una enfermedad acuden a la farmacia sin receta."),
   ("pct_med_tradicional","Medicina tradicional",     "%",  0, _sx("salud", ["medicinatradicional"]),     ATE_TODOS, "Personas que acuden a la medicina tradicional."),
   ("brecha_sin_seguro",  "Brecha de género: sin seguro","pp",0, None, None, "Puntos porcentuales (hombres − mujeres) sin afiliación a salud."),
 ]),
 ("trabajo", "Trabajo", [
   ("pct_empleado",      "Asalariados",               "%",  1, _sx("ocupacion", ["empleado"]),     OCU_TODOS, "Ocupados en condición de empleado o asalariado."),
   ("pct_cuentapropia",  "Trabajo por cuenta propia", "%", -1, _sx("ocupacion", ["cuentapropia"]), OCU_TODOS, "Ocupados por cuenta propia. Es la mejor aproximación censal a la informalidad."),
   ("brecha_cuentapropia","Brecha de género: cuenta propia","pp",0, None, None, "Puntos porcentuales (hombres − mujeres) en trabajo por cuenta propia."),
   ("pct_comercio",      "Comercio",                  "%",  0, _sx("actividad", ["comercio"]),          ACT_TODOS, "Ocupados en comercio."),
   ("pct_manufactura",   "Manufactura",               "%",  0, _sx("actividad", ["manufactura"]),       ACT_TODOS, "Ocupados en industria manufacturera."),
   ("pct_construccion",  "Construcción",              "%",  0, _sx("actividad", ["construccion"]),      ACT_TODOS, "Ocupados en construcción."),
   ("pct_agricultura",   "Agricultura",               "%",  0, _sx("actividad", ["agricultura"]),       ACT_TODOS, "Ocupados en agricultura, ganadería y silvicultura."),
   ("pct_transporte",    "Transporte",                "%",  0, _sx("actividad", ["transporte"]),        ACT_TODOS, "Ocupados en transporte y almacenamiento."),
   ("pct_alojamiento",   "Alojamiento y comida",      "%",  0, _sx("actividad", ["alojamientoycomida"]),ACT_TODOS, "Ocupados en alojamiento y servicios de comida."),
 ]),
 ("vivienda", "Vivienda", [
   ("pct_viv_propia",     "Vivienda propia",     "%", 0, ["viviendatenencia_propia"],      VIV_TEN,  "Viviendas ocupadas por sus propietarios."),
   ("pct_viv_alquilada",  "Alquiler",            "%", 0, ["viviendatenencia_alquilada"],   VIV_TEN,  "Viviendas en alquiler."),
   ("pct_viv_anticretico","Anticrético",         "%", 0, ["viviendatenencia_anticretico"], VIV_TEN,  "Viviendas en anticrético."),
   ("pct_viv_desocupada", "Viviendas desocupadas","%",0, ["viviendatipo_particulardesocupada"], VIV_TIPO, "Viviendas particulares desocupadas al momento del censo."),
 ]),
 ("servicios", "Servicios básicos", [
   ("pct_agua_red",       "Agua por cañería de red","%", 1, ["agua_cañería"],        AGUA, "Viviendas con agua por cañería de red."),
   ("pct_agua_pozo",      "Agua de pozo",          "%", -1, ["agua_pozoconbomba", "agua_pozosinbomba"], AGUA, "Viviendas que se abastecen de pozo."),
   ("pct_alcantarillado", "Alcantarillado",        "%",  1, ["desague_alcantarillado"], DES, "Viviendas con desagüe conectado a la red de alcantarillado."),
   ("pct_camara_septica", "Cámara séptica",        "%",  0, ["desague_camaraséptica"], DES, "Viviendas con desagüe a cámara séptica."),
   ("pct_pozo_ciego",     "Pozo ciego",            "%", -1, ["desague_pozociego"],     DES, "Viviendas con desagüe a pozo ciego."),
   ("pct_sin_desague",    "Sin desagüe",           "%", -1, ["desague_notiene", "desague_superficie"], DES, "Viviendas sin desagüe o que descargan a la superficie."),
   ("pct_electricidad",   "Energía eléctrica",     "%",  1, ["energiaelectrica_serviciopublico"], ENE, "Viviendas con electricidad de servicio público."),
   ("pct_gas_red",        "Gas por cañería",       "%",  1, ["combustible_gascañería"], COMB, "Viviendas que cocinan con gas domiciliario por cañería."),
   ("pct_gas_garrafa",    "Gas en garrafa",        "%",  0, ["combustible_gasgarrafa"], COMB, "Viviendas que cocinan con gas en garrafa."),
   ("pct_lena_guano",     "Leña o guano",          "%", -1, ["combustible_leña", "combustible_guano"], COMB, "Viviendas que cocinan con leña o guano."),
   ("pct_basura_carro",   "Recojo formal de basura","%", 1, ["basura_carrobasurero", "basura_basureropúblico"], BAS, "Viviendas cuya basura se recoge por carro basurero o contenedor público."),
   ("pct_basura_quema",   "Quema de basura",       "%", -1, ["basura_quema"], BAS, "Viviendas que queman su basura."),
   ("pct_basura_informal","Basura a calle o río",  "%", -1, ["basura_calle", "basura_río"], BAS, "Viviendas que arrojan su basura a la calle o a un río."),
   ("idx_carencia",       "Índice de carencia de servicios", "0-100", -1, None, None,
    "Promedio simple de cinco carencias: sin agua de red, sin alcantarillado, sin electricidad pública, cocina con leña o guano, y basura sin recojo formal. 0 = ninguna carencia, 100 = todas."),
 ]),
 ("conectividad", "Conectividad", [
   ("pct_internet",  "Internet",  "%", 1, ["tics_internet"],  None, "Viviendas con acceso a internet."),
   ("pct_celular",   "Celular",   "%", 1, ["tics_celular"],   None, "Viviendas con al menos un celular."),
   ("pct_televisor", "Televisor", "%", 0, ["tics_televisor"], None, "Viviendas con televisor."),
   ("pct_radio",     "Radio",     "%", 0, ["tics_radio"],     None, "Viviendas con radio."),
 ]),
]

# Las TICs se declaran por vivienda como tenencia sí/no: el denominador correcto
# es el total de viviendas particulares con dato, no la suma de la familia
# (una vivienda puede tener radio Y celular Y internet, así que sumarlas pasaría
# de 100%).
DEN_TICS = ["viviendatipo_particular"]


def suma(df, cols):
    presentes = [c for c in cols if c in df.columns]
    faltan = set(cols) - set(presentes)
    if faltan:
        print(f"  ⚠ columnas ausentes: {sorted(faltan)}", file=sys.stderr)
    if not presentes:
        return pd.Series(0.0, index=df.index)
    return df[presentes].sum(axis=1)


def pct(num, den):
    """Porcentaje con guarda: denominador 0 → null, NO 0. Un 0% inventado en una
    manzana sin dato se lee como carencia total y es la mentira más fácil de
    cometer en un coroplético."""
    r = (num / den.replace(0, pd.NA)) * 100
    return r.astype("Float64").round(1)


def main():
    print("Leyendo fuente…")
    mz = pd.read_parquet(FUENTE / "manzanos.parquet")
    po = pd.read_parquet(FUENTE / "poblacion.parquet")
    fi = pd.read_parquet(FUENTE / "fichas.parquet")

    mz["_k"] = mz["municipio"].map(_norm)
    faltan = [n for n in NOMBRE_A_META if _norm(n) not in set(mz["_k"])]
    if faltan:
        sys.exit(f"ERROR: no se encontraron en la fuente: {faltan}")
    mz = mz[mz["_k"].isin(NORM_A_NOMBRE)].copy()
    mz["municipio"] = mz["_k"].map(NORM_A_NOMBRE)      # nombre canónico
    mz = mz.drop(columns=["_k"])
    print(f"  manzanas en los 9 municipios: {len(mz):,}")

    for c in ("personas", "viviendas"):
        po[c] = pd.to_numeric(po[c], errors="coerce")
    for c in fi.columns:
        if c != "codigo":
            fi[c] = pd.to_numeric(fi[c], errors="coerce")

    df = mz.merge(po[["codigo", "personas", "viviendas"]], on="codigo", how="left")
    df = df.merge(fi, on="codigo", how="left")
    df["tiene_ficha"] = df["codigo"].isin(set(fi["codigo"]))
    print(f"  con ficha: {int(df['tiene_ficha'].sum()):,} "
          f"({100*df['tiene_ficha'].mean():.0f}%)")

    # ── geometría y superficie ───────────────────────────────────────────────
    geom = gpd.GeoSeries([wkb.loads(b) for b in df["geometry"]], crs="EPSG:4326")
    g = gpd.GeoDataFrame(df.drop(columns=["geometry"]), geometry=geom, crs="EPSG:4326")
    # UTM 20S: la región entera cae en esta zona, así que el área en m² es fiable.
    g["_area_ha"] = g.to_crs("EPSG:32720").area / 10_000

    # ── derivaciones directas del catálogo ───────────────────────────────────
    print("Derivando indicadores…")
    for _, _, inds in CATALOGO:
        for key, _, unit, _, num, den, _ in inds:
            if num is None:
                continue
            d = DEN_TICS if den is None else den
            g[key] = pct(suma(g, num), suma(g, d))

    # ── derivaciones especiales ──────────────────────────────────────────────
    g["personas"] = g["personas"].astype("Float64")
    g["viviendas"] = g["viviendas"].astype("Float64")
    g["pers_x_vivienda"] = (g["personas"] / g["viviendas"].replace(0, pd.NA)).astype("Float64").round(2)
    g["densidad"] = (g["personas"] / g["_area_ha"].replace(0, pd.NA)).astype("Float64").round(1)

    jov = suma(g, _sx("edad", ["0a19"]))
    may = suma(g, _sx("edad", ["60omas"]))
    act = suma(g, _sx("edad", ["20a39", "40a59"]))
    g["dependencia"] = pct(jov + may, act)

    h = suma(g, [c for c in EDAD_TODOS if c.endswith("_hombre")])
    m = suma(g, [c for c in EDAD_TODOS if c.endswith("_mujer")])
    g["masculinidad"] = pct(h, m)

    def brecha(base, opcion, familia):
        """Diferencia en puntos porcentuales entre hombres y mujeres, cada uno
        sobre SU PROPIO total. Restar dos porcentajes calculados sobre el total
        conjunto daría una brecha contaminada por la composición por sexo."""
        ph = pct(suma(g, [f"{base}_{opcion}_hombre"]),
                 suma(g, [c for c in familia if c.endswith("_hombre")]))
        pm = pct(suma(g, [f"{base}_{opcion}_mujer"]),
                 suma(g, [c for c in familia if c.endswith("_mujer")]))
        return (ph - pm).astype("Float64").round(1)

    g["brecha_educ_superior"] = brecha("educacion", "superior", EDU_TODOS)
    g["brecha_sin_educacion"] = brecha("educacion", "ninguno", EDU_TODOS)
    g["brecha_sin_seguro"] = brecha("saludafiliacion", "ninguno", SAL_TODOS)
    g["brecha_cuentapropia"] = brecha("ocupacion", "cuentapropia", OCU_TODOS)

    # Índice de carencia: promedio de 5 carencias, cada una 0-100.
    carencias = [100 - g["pct_agua_red"], 100 - g["pct_alcantarillado"],
                 100 - g["pct_electricidad"], g["pct_lena_guano"],
                 100 - g["pct_basura_carro"]]
    g["idx_carencia"] = (sum(carencias) / len(carencias)).astype("Float64").round(1)

    # ── salida ───────────────────────────────────────────────────────────────
    SALIDA.mkdir(parents=True, exist_ok=True)
    claves = [k for _, _, inds in CATALOGO for k, *_ in inds]
    props = ["codigo", "nombre", "municipio", "tiene_ficha"] + claves

    resumen = []
    for nombre, meta in NOMBRE_A_META.items():
        sub = g[g["municipio"] == nombre].copy()
        if sub.empty:
            print(f"  ⚠ sin manzanas: {nombre}")
            continue
        sub["sigep"] = meta["sigep"]
        out = sub[props + ["sigep", "geometry"]].copy()
        # el GeoJSON no admite pd.NA
        for c in props:
            if c not in ("codigo", "nombre", "municipio", "tiene_ficha"):
                out[c] = out[c].astype(object).where(out[c].notna(), None)
        slug = (nombre.lower().replace(" ", "_").replace("á", "a").replace("é", "e")
                .replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
        destino = SALIDA / f"manzanas_{slug}.geojson"
        out.to_file(destino, driver="GeoJSON")
        mb = destino.stat().st_size / 1024 / 1024
        con = int(sub["tiene_ficha"].sum())
        print(f"  {nombre:<26} {len(sub):>6} manzanas  {con:>6} c/ficha  {mb:>5.1f} MB")

        # ── Agregado URBANO, no municipal ────────────────────────────────────
        # ⚠ Esto NO es el valor del municipio y no debe presentarse como tal.
        # El universo de las manzanas son bloques URBANOS con ficha publicada;
        # la cifra municipal del INE cubre todo el territorio, incluido lo rural.
        # Medido contra el Atlas, el sesgo es sistemático y siempre al alza:
        # +12 pp en agua en la capital, +30 en Porongo, +47 en Pailón — porque su
        # población rural, que es la mayoría, no tiene manzana. Presentar esto
        # como "el municipio" exageraría la cobertura de servicios de toda la
        # región. El piso municipal del tablero se sirve del Atlas (clave
        # `municipal` abajo); esto viaja aparte y rotulado como urbano.
        fila = {"sigep": meta["sigep"], "cod_ine": meta["cod_ine"], "nombre": nombre,
                "ambito": meta["ambito"], "manzanas": len(sub), "con_ficha": con,
                "personas_urbano": float(sub["personas"].sum()),
                "viviendas_urbano": float(sub["viviendas"].sum())}
        w = sub["personas"].astype(float).fillna(0)
        urbano = {}
        for k in claves:
            if k in ("personas", "viviendas"):
                continue
            v = pd.to_numeric(sub[k], errors="coerce")
            ok = v.notna() & (w > 0)
            urbano[k] = round(float((v[ok] * w[ok]).sum() / w[ok].sum()), 1) if ok.any() else None
        fila["urbano"] = urbano
        resumen.append(fila)

    # ── Piso municipal: se toma del Atlas, que es el dato del INE para todo el
    # municipio. No se recalcula acá (ver la nota de sesgo arriba).
    if ATLAS_MUNICIPAL.exists():
        atlas = json.loads(ATLAS_MUNICIPAL.read_text(encoding="utf-8"))
        hallados = 0
        for fila in resumen:
            m = atlas.get(fila["sigep"])
            if m:
                fila["municipal"] = {k: v for k, v in m.items()
                                     if k not in ("nombre", "cod_ine", "dpto")}
                hallados += 1
        print(f"  piso municipal desde el Atlas: {hallados}/{len(resumen)}")
    else:
        print(f"  ⚠ no se halló el Atlas en {ATLAS_MUNICIPAL} — sin piso municipal")

    (SALIDA / "municipios.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")

    catalogo = {"grupos": [
        {"key": gk, "label": gl,
         "indicadores": [{"key": k, "label": lb, "unit": u, "dir": d, "desc": ds}
                         for k, lb, u, d, _, _, ds in inds]}
        for gk, gl, inds in CATALOGO]}
    (SALIDA / "catalogo.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")

    n_ind = sum(len(i) for _, _, i in CATALOGO)
    print(f"\nCatálogo: {len(CATALOGO)} grupos · {n_ind} indicadores")
    print(f"Salida en {SALIDA}")


if __name__ == "__main__":
    main()
