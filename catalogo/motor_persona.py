# -*- coding: utf-8 -*-
"""
MOTOR DE PERSONAS — una regla por indicador, los dos censos.
============================================================

Mismas reglas que `motor.py` (vivienda): capa de armonización y una sola
definición por indicador, verificada contra el tabulado del INE.

★ TRAMPAS REALES DE ESTE BLOQUE, todas leídas de los diccionarios o resueltas
  contando — ninguna supuesta:

  · SEXO: en los DOS censos 1=Mujer, 2=Hombre. Al revés de lo habitual; asumir
    1=hombre invierte todas las brechas de género sin que nada falle.

  · CATEGORÍA OCUPACIONAL invertida: 2012 1=obrero/empleado 2=cuenta propia ·
    2024 al revés.  Grupo ocupacional (0-9) y rama (1-21) sí coinciden.

  · NIVEL EDUCATIVO 2012: 20 categorías crudas de TRES sistemas educativos. El
    INE no agrupa por nivel declarado sino por AÑOS ACUMULADOS, cortando en 6.
    Agrupar por nivel da 2.085.118 donde el INE publica 1.636.143.

  · SALUD: los códigos de "dónde acude" están PERMUTADOS entre censos
    (2012 P28C = público, 2024 p30a = público, pero P28A = caja y p30b = caja…).
    Se mapean por significado, no por posición.

  · TRES UNIVERSOS que hay que acertar:
      1. RESIDENTES — el INE excluye a quienes viven en el exterior.
      2. El denominador educativo son quienes DECLARARON nivel, no toda la
         población de 19+.
      3. Empleo = ocupados 14+ residentes INCLUYENDO "sin especificar".
"""
import pathlib, sys, json, unicodedata, numpy as np, pandas as pd

CPV24 = pathlib.Path(r"C:\Users\HP\cpv2024")
CPV12 = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones"
                     r"\upre-nbi\datos\crudo\CPV2012 343M\baser")
PARQ = CPV24 / "persona_full.parquet"
PARQ12 = CPV24 / "persona_2012_full.parquet"
sys.path.insert(0, r"C:\Users\HP\OneDrive\Desktop\Proyectos\investigaciones\upre-nbi\scripts")

# ── nivel educativo 2012: años acumulados = base[nivel] + curso ─────────────
# ⚠️ FALTABAN LOS NIVELES SUPERIORES (2026-08-13). La tabla sólo llegaba al 10,
#    así que técnico, licenciatura, maestría, doctorado, normal y militar
#    (11-17) daban NaN y esas personas DESAPARECÍAN del promedio de años de
#    estudio: `prom_anios_estudio` validaba 15/343 contra `educacion/4`.
#    Los dos sistemas cierran la secundaria en 12 años, así que lo superior
#    arranca ahí.
#      4 Básico(1-5)=0 · 5 Intermedio(1-3)=5 · 6 Medio(1-4)=8   (sistema antiguo)
#      7 Primaria(1-8)=0 · 8 Secundario(1-4)=8                  (sistema anterior)
#      9 Primaria(1-6)=0 · 10 Secundaria(1-6)=6                 (sistema actual)
#    ★ TODO EL TRAMO SUPERIOR PARTE DE 12, maestría y doctorado INCLUIDOS.
#      Probado contra `educacion/4` con bases 10, 11 y 12: dan 15, 164 y 238 de
#      343. Un intento previo puso 17 y 19 para maestría/doctorado "porque
#      vienen después de la licenciatura" — invención mía que EMPEORABA el
#      resultado (141/343). El INE no los trata aparte.
ANIOS12 = {4: 0, 5: 5, 6: 8, 7: 0, 8: 8, 9: 0, 10: 6,
           11: 12, 12: 12, 13: 12, 14: 12, 15: 12, 16: 12, 17: 12}

# ── ídem 2024, y ⚠️ LOS CÓDIGOS NO SON LOS MISMOS ───────────────────────────
# La "secundaria del sistema actual" es el código 10 en 2012 y el 8 en 2024.
# Reutilizar ANIOS12 le habría sumado 8 años en vez de 6 a todo el secundario.
# Comprobado contra el propio dato: con nivel Primaria(7) el curso mediano va
# 2,3,4,5,6 a los 8,9,10,11,12 años (⇒ años = curso, esperado = edad − 6), y con
# Secundaria(8) da 3 a los 15 y 5 a los 17 (⇒ 6+3=9=15−6 y 6+5=11=17−6).
#   1 Ninguno · 2 Alfabetización · 3 Inicial → 0 años
#   4 Básico → curso · 5 Intermedio → 5+curso · 6 Medio → 8+curso   (sistema viejo)
#   7 Primaria → curso · 8 Secundaria → 6+curso                     (sistema actual)
ANIOS24 = {1: 0, 2: 0, 3: 0, 4: 0, 5: 5, 6: 8, 7: 0, 8: 6}
NINGUNO12, SUPERIOR12, OTROS12 = {1, 2, 3}, {11, 12, 13, 14, 15, 16, 17}, {18}
NIVEL24 = {"ninguno": {1}, "primaria": {2}, "secundaria": {3}, "superior": {4}}
CATOCU12 = {"asalariado": {1}, "cuenta_propia": {2}, "empleador": {3},
            "familiar": {4}, "hogar": {5}, "cooperativista": {6}}
CATOCU24 = {"asalariado": {2}, "cuenta_propia": {1}, "empleador": {3},
            "familiar": {4}, "hogar": {5}, "cooperativista": {6}}   # ⚠ 1 y 2 invertidos

# ⚠️ ESTADO CIVIL: los códigos están PERMUTADOS entre censos y el motor les
#    aplicaba el mismo mapeo a los dos, así que los cinco indicadores de 2012
#    estaban corridos —"casado" contaba solteros y "soltero" contaba viudos—.
#    Se detectó porque `pct_ecivil_separado_divorciado` caía de 27,6% a 4,6%.
#      2012: 1 Soltera(o) · 2 Casada(o) · 3 Conviviente · 4 Separada(o) ·
#            5 Divorciada(o) · 6 Viuda(o)
#      2024: 1 Casada(o) · 2 Conviviente · 3 Separada(o) · 4 Divorciada(o) ·
#            5 Viuda(o) · 6 Soltera(o)
ECIVIL12 = {"casado": {2}, "conviviente": {3}, "separado_divorciado": {4, 5},
            "viudo": {6}, "soltero": {1}}
ECIVIL24 = {"casado": {1}, "conviviente": {2}, "separado_divorciado": {3, 4},
            "viudo": {5}, "soltero": {6}}

# ★ Grupo ocupacional y rama van en la versión 13ª CIET, NO la 19ª. El tabulado
#   del INE usa la 13 en todo el bloque de empleo (es la que permite comparar con
#   2012), y la 19 saca de la ocupación a los productores agrícolas de
#   autoconsumo: con `act_eco_2d_19` faltaban 444.396 agricultores.
COLS24 = ["p25_sexo", "p26_edad", "nivel_edu", "asiste", "p40_lee", "p50_catocu_13",
          "ocu_1d_13", "act_eco_2d_13", "p30a_public", "p30b_caja", "p30c_privad",
          "p30e_tradic", "p30f_autome", "p30g_casera", "p28_cn", "p29_ci",
          "p32_pueblo_per", "idioma_mat", "p42_discap", "p54_hvtot", "p55_hstot",
          "p35_lugnac", "p37_lugres5", "mun_nac_cod", "mun_res5_cod", "p39_tipoest",
          # ── ampliación 2026-08-12: jefatura, pueblos al detalle, discapacidad,
          #    afiliación de salud, estado civil, años de estudio y conmutación
          "p24_parentes", "p32_pueblo_cod", "p42a_ver", "p42b_oir", "p42c_camina",
          "p42d_comuni", "p31_afiliado", "p53_ecivil", "aestudio",
          "p59_partocalif", "mun_lab_cod", "dep_lab_cod",
          # ── ampliación 2026-08-12 (b): las tres cosas que faltaban del plan,
          #    juntas en UNA sola reconstrucción de caché en vez de tres:
          #    · `i00`         → hogares con menores / con adulto mayor / AM solo
          #    · `p41a/p41b`   → rezago escolar (curso aprobado vs. edad)
          #    · `p59_mef`     → parto calificado con el universo CORRECTO
          "i00", "p41a_nivel", "p41b_curso_act", "p59_mef",
          "condact_19", "p56_edadmad", "p331_idiohab1_cod", "p332_idiohab2_cod",
          # ★ hace falta el filtro de RESIDENCIA explícito: las variables derivadas
          #   del INE (`asiste`, `nivel_edu`, `p50_catocu_13`) ya lo traen incorporado,
          #   pero las preguntas crudas como `p40_lee` no. Sin esto el denominador de
          #   analfabetismo tiene 59.822 personas de más — las que viven en el exterior.
          "p36_lugres"]

# ── pueblos: se emparejan por NOMBRE, nunca por código ──────────────────────
# ⚠️ Los códigos NO coinciden entre censos y las diferencias son traicioneras:
#     quechua  2012=2  · 2024=28
#     aymara   2012=1  · 2024=3
#     guaraní  2012=17 · 2024=13
#     afrobol. 2012=3  · 2024=1      ← el 3 es "Afroboliviano" en 2012 y
#                                       "Aymara" en 2024
# Un mapeo por número habría producido cifras verosímiles y falsas. Por eso el
# motor traduce el código a la ETIQUETA del propio diccionario de cada censo y
# los indicadores se escriben contra el nombre.
import re as _re
def _limpiar_pueblo(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    s = _re.sub(r"^[a-zA-Z]\s*-\s*", "", s.strip())   # 2012 prefija "A - ", "B - "
    return " ".join(s.lower().split())

PUEBLOS = ["quechua", "aymara", "guarani", "chiquitano", "afroboliviano",
           "guarayo", "mojeno", "trinitario", "yuracare", "movima"]

# ⚠️ Emparejar por NOMBRE esquiva la trampa de los códigos, pero la GRAFÍA
#    tampoco es estable entre censos: el mismo pueblo se escribe "Guarayu" en
#    2012 y "Gwarayu" en 2024, "Yuracaré" y "Yurakaré". Con comparación literal
#    los dos daban 0,00% en 2024 — y no es que no haya gente, es que la etiqueta
#    no se encontraba. Verificado contra los dos diccionarios: de los diez
#    pueblos del catálogo, éstos son los ÚNICOS con grafía distinta.
#    Se aplica en la capa de reglas, no al derivar: la caché guarda el rótulo
#    del propio censo y la armonización vive junto a la comparación, igual que
#    el `MAPEO` de motor.py.
SINONIMOS = {"gwarayu": "guarayo", "guarayu": "guarayo",
             "yurakare": "yuracare"}


def _map(serie, mapa):
    out = pd.Series(np.full(len(serie), "", dtype=object), index=serie.index)
    for nombre, cods in mapa.items():
        out[serie.isin(list(cods))] = nombre
    return out


# ── IDIOMA MATERNO ──────────────────────────────────────────────────────────
# ★ CASTELLANO ES EL CÓDIGO 6, NO EL 1 — el 1 es Araona. Verificado en los
#   diccionarios de LOS DOS censos: la lista va alfabética (1 Araona, 2 Aymara,
#   3 Baure, 4 Bésiro, 5 Canichana, 6 Castellano…) y los códigos 1..37 son los
#   "idiomas oficiales" del tabulado (36 originarios + el castellano en el 6).
#   Los códigos COINCIDEN entre 2012 y 2024, cosa que no pasa con casi ninguna
#   otra variable de este bloque.
#   Con `== 1` el motor contaba 122 personas en TODO EL PAÍS como
#   hispanohablantes y dejaba el 100,0% del país con idioma materno originario.
CASTELLANO = 6
OFICIALES = set(range(1, 38))              # 1..37
# 2024 suma al bloque de oficiales tres declaraciones que 2012 no desagrega:
# Afroboliviano (94), Joaquiniano (95) y "Otras declaraciones" (991). En 2012 su
# equivalente es "Otro idioma nacional" (39).
OFI_EXTRA = {2024: {94, 95, 991}, 2012: {39}}


def _cod6(s):
    """Código INE de 6 dígitos desde una columna NUMÉRICA.

    ⚠️ `astype(str)` sobre una columna numérica escribe "70101.0", y entonces el
    `zfill(6)` no hace nada porque ya son 7 caracteres. Ese era el bug que dejaba
    la conmutación laboral vacía en los 343 municipios: el filtro
    `mun_trabaja.str.len() == 6` no encontraba una sola fila.
    Los códigos 999xxx son "no aplica" / "sin especificar" y se descartan.
    """
    v = pd.to_numeric(s, errors="coerce")
    v = v.where(v.between(10101, 998999))
    out = v.astype("Int64").astype(str).str.zfill(6)
    return out.where(v.notna(), "")


def _derivar_24(p):
    """Convierte un bloque crudo en las columnas derivadas, que ocupan una
    fracción: booleanos y enteros chicos en vez de 26 columnas de texto."""
    for c in COLS24:
        if c in p.columns:
            p[c] = pd.to_numeric(p[c], errors="coerce")
    d = pd.DataFrame({"cod_ine": p.cod_ine})
    d["mujer"] = p.p25_sexo == 1
    d["edad"] = p.p26_edad
    # ★ residente = declaró vivir en el país. Excluye "en otro país" (3) Y
    #   "sin especificar" (9): con `!= 3` el denominador de analfabetismo quedaba
    #   41.304 personas por encima del publicado. Las derivadas del INE
    #   (`asiste`, `nivel_edu`, `p50_catocu_13`) ya traen este filtro incorporado;
    #   las preguntas crudas como `p40_lee` no.
    d["residente"] = p.p36_lugres.isin([1, 2])
    d["nivel"] = _map(p.nivel_edu, NIVEL24)
    d["asiste"] = p.asiste == 1
    d["asiste_resp"] = p.asiste.isin([1, 2])     # el INE divide por quienes respondieron
    d["publica"] = p.p39_tipoest == 1
    d["lee"] = p.p40_lee == 2                    # ⚠ el indicador es ANALFABETISMO
    d["lee_resp"] = p.p40_lee.isin([1, 2])
    d["catocu"] = _map(p.p50_catocu_13, CATOCU24)
    d["ocupado"] = p.p50_catocu_13.isin([1, 2, 3, 4, 5, 6, 9])
    d["ocu1d"] = p.ocu_1d_13
    d["rama"] = p.act_eco_2d_13
    for k, c in [("s_publica", "p30a_public"), ("s_caja", "p30b_caja"),
                 ("s_privada", "p30c_privad"), ("s_tradic", "p30e_tradic"),
                 ("s_autome", "p30f_autome"), ("s_casera", "p30g_casera")]:
        d[k] = p[c] == 1
    d["registro"] = p.p28_cn == 1
    d["cedula"] = p.p29_ci == 1
    d["indigena"] = p.p32_pueblo_per == 1
    # se guarda el CÓDIGO, no un booleano: castellano y originario salen del
    # mismo campo y el booleano perdía la información (ver CASTELLANO arriba)
    d["idioma"] = p.idioma_mat.astype("float32")
    d["discap"] = p.p42_discap == 1
    # ⚠️ Los códigos de "no aplica" / "sin especificar" son números grandes y
    #    entran al promedio: sin recortarlos la paridez media daba 28,3 hijos por
    #    mujer y los hijos fallecidos salían NEGATIVOS. Se acota a un rango
    #    biológicamente posible.
    d["hijos_nac"] = p.p54_hvtot.where(p.p54_hvtot <= 25)
    d["hijos_viv"] = p.p55_hstot.where(p.p55_hstot <= 25)
    d["nac_aqui"] = p.p35_lugnac == 1
    d["nac_exterior"] = p.p35_lugnac == 3
    d["res5_otro"] = p.p37_lugres5 == 2
    # los tres códigos de origen/destino comparten el mismo tratamiento: son
    # numéricos y necesitan `_cod6` para quedar como el `cod_ine` de 6 dígitos.
    # `mun_res5` es el insumo de la matriz migratoria y antes ni se asignaba.
    d["mun_nac"] = _cod6(p.mun_nac_cod)
    d["mun_res5"] = _cod6(p.mun_res5_cod)
    d["mun_trabaja"] = _cod6(p.mun_lab_cod)
    d["jefe"] = p.p24_parentes == 1
    et = json.loads((CPV24 / "diccionario.json").read_text(encoding="utf-8")
                    )["PERSONA"]["p32_pueblo_cod"]["categorias"]
    et = {int(k): _limpiar_pueblo(v) for k, v in et.items()}
    d["pueblo"] = p.p32_pueblo_cod.map(et).fillna("")
    d["ecivil"] = p.p53_ecivil
    d["anios_estudio"] = p.aestudio.where(p.aestudio <= 30)
    d["afiliado"] = p.p31_afiliado
    d["parto_calif"] = p.p59_partocalif == 1
    # ★ `p59_mef` YA viene restringida a mujeres en edad fértil residentes con
    #   parto en los últimos cinco años, y dice QUIÉN atendió (1 médica/o ·
    #   2 enfermera/o · 3 auxiliar · … · 9 sin especificar). Es el universo que
    #   faltaba: `p59_partocalif` dividido por todas las madres de 15-49 daba
    #   40,8%, porque a la mayoría la pregunta ni le corresponde.
    d["parto_quien"] = p.p59_mef.astype("float32")
    # ★ HOGAR: `i00` sólo es único DENTRO del municipio, así que la clave real
    #   es cod_ine + i00. Se guarda como entero de 14 dígitos (entra en int64):
    #   como texto son 11,4 M de cadenas y la memoria no alcanza.
    d["hogar"] = (pd.to_numeric(p.cod_ine, errors="coerce").astype("int64") * 100_000_000
                  + pd.to_numeric(p.i00, errors="coerce").fillna(0).astype("int64"))
    d["curso_nivel"] = p.p41a_nivel.astype("float32")
    d["curso_anio"] = p.p41b_curso_act.astype("float32")
    d["desocupado"] = p.condact_19.isin([2, 3])      # cesante o aspirante
    d["edad_madre_1"] = p.p56_edadmad.where(p.p56_edadmad.between(8, 60))
    d["bilingue"] = p.p332_idiohab2_cod.notna() & (p.p332_idiohab2_cod > 0)
    d["res_otro_mun"] = p.p36_lugres == 2
    for k, c in [("disc_ver", "p42a_ver"), ("disc_oir", "p42b_oir"),
                 ("disc_caminar", "p42c_camina"), ("disc_comunicar", "p42d_comuni")]:
        d[k] = p[c].isin([3, 4])     # dificultad severa o total
    d["cod_ine"] = d.cod_ine.astype("category")
    d["edad"] = d.edad.astype("float32")
    for c in ("hijos_nac", "hijos_viv", "ocu1d", "rama"):
        d[c] = d[c].astype("float32")
    return d


def cargar_2024():
    """Lee el CSV por bloques y DERIVA en cada uno. Acumular los 26 campos de
    texto de 11,4 M de filas antes de derivar agota la memoria: pandas aborta
    con 'Error tokenizing data. C error: out of memory'."""
    # ⚠️ El parquet es una CACHÉ de las columnas YA DERIVADAS. Si `_derivar_24`
    #    cambia, la caché queda vieja y el arreglo se vuelve invisible: el motor
    #    sigue leyendo la versión anterior y los números no se mueven. Eso fue lo
    #    que mantuvo vivo el bug de `mun_trabaja`. La guarda compara el esquema.
    ESPERADAS = {"idioma", "mun_nac", "mun_res5", "mun_trabaja",
                 "hogar", "curso_nivel", "curso_anio", "parto_quien"}
    if PARQ.exists():
        cache = pd.read_parquet(PARQ)
        if ESPERADAS <= set(cache.columns):
            return cache
        faltan = ", ".join(sorted(ESPERADAS - set(cache.columns)))
        # sin caracteres fuera de cp1252: la consola de Windows aborta con
        # UnicodeEncodeError cuando la salida se redirige a un archivo
        print(f"   cache vieja (faltan: {faltan}); se rehace desde el CSV", flush=True)
    base = ["idep", "iprov", "imun"] + COLS24
    partes = []
    for ch in pd.read_csv(CPV24 / "Persona_CPV-2024.csv", sep=";", usecols=base,
                          dtype=str, encoding="latin-1", chunksize=1_500_000,
                          low_memory=False):
        ch["cod_ine"] = ch.idep.str.zfill(2) + ch.iprov.str.zfill(2) + ch.imun.str.zfill(2)
        partes.append(_derivar_24(ch))
        print(f"   … {sum(len(x) for x in partes):,} personas", flush=True)
    d = pd.concat(partes, ignore_index=True)
    d["cod_ine"] = d.cod_ine.astype(str)
    d.to_parquet(PARQ, compression="zstd")
    return d


def cargar_2012():
    # ⚠️ Leer las ~50 variables de PERSONA del Redatam son unos 20 minutos: el
    #    formato es bit-packed y se decodifica en Python. Sin caché, cambiar una
    #    sola regla cuesta una corrida entera, y eso empuja a "probar de memoria"
    #    en vez de correr. Misma guarda de esquema que 2024.
    ESPERADAS = {"idioma", "mun_nac", "mun_res5", "desocupado", "hogar",
                 "nivel_cod", "curso_cod"}
    if PARQ12.exists():
        cache = pd.read_parquet(PARQ12)
        if ESPERADAS <= set(cache.columns):
            return cache
        faltan = ", ".join(sorted(ESPERADAS - set(cache.columns)))
        print(f"   cache 2012 vieja (faltan: {faltan}); se rehace", flush=True)
    d = _leer_2012()
    d.to_parquet(PARQ12, compression="zstd")
    return d


def _leer_2012():
    from redatam import RedatamDB
    db = RedatamDB(str(CPV12))
    cods = db.codigos_municipio()
    mun = db.municipio_de("PERSONA")
    g = lambda v: pd.Series(db.leer("PERSONA:" + v))
    d = pd.DataFrame({"cod_ine": pd.Categorical.from_codes(mun, cods).astype(str)})
    d["mujer"] = g("P24") == 1
    d["edad"] = g("P25")
    d["residente"] = g("P33A") != 3        # 3 = "En el exterior"
    niv, cur = g("P37A"), g("P37B")
    anios = niv.map(ANIOS12).astype("float") + cur
    d["nivel"] = np.where(niv.isin(list(NINGUNO12)), "ninguno",
                 np.where(niv.isin(list(SUPERIOR12)), "superior",
                 np.where(niv.isin(list(OTROS12)), "otros",
                 np.where(anios <= 6, "primaria",
                 np.where(anios >= 7, "secundaria", "")))))
    asi = g("P36")
    d["asiste"] = asi.isin([1, 2, 3])      # pública, privada o de convenio
    d["asiste_resp"] = asi.isin([1, 2, 3, 4])   # excluye "sin especificar"
    d["publica"] = asi == 1
    lee = g("P35")
    d["lee"] = lee == 2                    # ⚠ el indicador es ANALFABETISMO
    d["lee_resp"] = lee.isin([1, 2])
    cat = g("P43")
    d["catocu"] = _map(cat, CATOCU12)
    d["ocupado"] = cat.isin([1, 2, 3, 4, 5, 6, 9])
    d["ocu1d"] = g("P42")
    d["rama"] = g("P44")
    # ⚠ los códigos de salud están PERMUTADOS: se mapean por significado
    for k, c in [("s_publica", "P28C"), ("s_caja", "P28A"), ("s_privada", "P28D"),
                 ("s_tradic", "P28E"), ("s_autome", "P28G"), ("s_casera", "P28F")]:
        d[k] = g(c) == 1
    d["registro"] = g("P26") == 1
    d["cedula"] = g("P27") == 1
    d["indigena"] = g("P29A") == 1
    d["idioma"] = g("P30B").astype("float32")       # mismos códigos que 2024
    # ⚠️ 2012 NO capta discapacidad por persona (va en una entidad aparte). Debe
    #    quedar VACÍO, no en False: con False el motor publicaba 0,00% en los 343
    #    municipios, que se lee como "no hay ninguna persona con discapacidad"
    #    en vez de "este censo no lo preguntó".
    d["discap"] = np.nan
    # ⚠️ el mismo recorte que 2024, que acá faltaba: sin él los códigos de "no
    #    aplica" (números grandes) entraban a las sumas y `pct_hijos_fallecidos`
    #    daba valores NEGATIVOS en los 343 municipios (mediana −29,9%).
    d["hijos_nac"] = g("P46").where(lambda x: x <= 25)
    d["hijos_viv"] = g("P47").where(lambda x: x <= 25)
    nacl = g("P32A")
    d["nac_aqui"] = nacl == 1
    d["nac_exterior"] = nacl == 3
    d["res5_otro"] = g("P34A") == 2
    # ★ ENLACE PERSONA ↔ VIVIENDA: Redatam guarda a PERSONA como entidad HIJA de
    #   VIVIENDA, y `_padre_idx` devuelve el índice de la vivienda de cada
    #   persona. Es el identificador de hogar de 2012 —el análogo de `i00` en
    #   2024— y con él los indicadores de hogar SÍ tienen serie intercensal.
    #   Control: 10.059.856 personas en 2.851.135 viviendas = 3,53 por hogar,
    #   que es el tamaño medio de Bolivia en 2012.
    d["hogar"] = db._padre_idx("PERSONA").astype("int64")
    # ⚠️ `P32H` NO es el municipio de nacimiento: tiene diez valores (es un
    #    código de otro nivel) y el diccionario Redatam no trae sus etiquetas.
    #    Se deja para que el esquema no cambie, pero las matrices O-D son sólo
    #    de 2024 — ver el encabezado de motor_flujos.py.
    d["mun_nac"] = _cod6(g("P32H"))
    d["jefe"] = g("P23") == 1
    et = {k: _limpiar_pueblo(v) for k, v in db.etiquetas("PERSONA:P29C").items()}
    d["pueblo"] = g("P29C").map(et).fillna("")
    d["ecivil"] = g("P45")
    # 2012 no trae los años de estudio calculados: se derivan del nivel + curso
    # con la misma tabla que resuelve la agrupación educativa
    # ★ se guardan los códigos CRUDOS además del derivado: si hay que
    #   corregir ANIOS12 otra vez, se recalcula sin rehacer la caché
    d["nivel_cod"] = niv.astype("float32")
    d["curso_cod"] = cur.astype("float32")
    d["anios_estudio"] = (niv.map(ANIOS12).astype("float") + cur).where(lambda x: x <= 30)
    d["parto_calif"] = g("P49B").isin([1, 2])   # establecimiento de salud
    # ⚠️ `PEA` de 2012 NO es un booleano: sus categorías son 1=Ocupado,
    #    2=Cesante, 3=Aspirante. La regla anterior (`PEA == 1 & ~ocupado`) es
    #    una contradicción —los ocupados no son "no ocupados"— y por eso la tasa
    #    de desocupación salía 0,00% en los 343 municipios. Es el mismo criterio
    #    que `condact_19.isin([2, 3])` en 2024.
    d["desocupado"] = g("PEA").isin([2, 3])
    d["edad_madre_1"] = np.nan                  # 2012 no pregunta la edad al primer hijo
    d["bilingue"] = g("P31B2") > 0              # declara un segundo idioma
    d["res_otro_mun"] = g("P33A") == 2
    d["mun_res5"] = _cod6(g("P34G"))            # matriz migratoria: sí hay serie
    # ⚠️ 2012 NO tiene: municipio de trabajo, afiliación a seguro, ni discapacidad
    #    por persona (la capta a nivel hogar en P22A + una entidad aparte).
    #    Van VACÍAS, no en False/0 — ver el comentario de `discap` arriba.
    d["mun_trabaja"] = ""
    d["afiliado"] = np.nan
    for k in ("disc_ver", "disc_oir", "disc_caminar", "disc_comunicar"):
        d[k] = np.nan
    return d


def calcular(d, anio):
    g = d.groupby("cod_ine")
    tot = g.size()
    out = {"poblacion": tot,
           "n_mujeres": d[d.mujer].groupby("cod_ine").size().reindex(tot.index, fill_value=0)}

    def pct(mask, universo, nombre):
        # ⚠️ Una variable que ESTE censo no preguntó llega como columna vacía.
        #    Tiene que salir en NaN, no en 0: un 0,00% se lee como "no hay
        #    ninguno" y en la serie intercensal inventa un cambio que nunca
        #    ocurrió (ver `discap` y los equipamientos en cargar_2012).
        if mask.dtype != bool and mask.isna().all():
            out[nombre] = pd.Series(np.nan, index=tot.index)
            out["_den_" + nombre] = pd.Series(np.nan, index=tot.index)
            return
        u = d[universo]
        den = u.groupby("cod_ine").size().reindex(tot.index, fill_value=0)
        num = u[mask[universo]].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
        out[nombre] = 100 * num / den.replace(0, np.nan)
        out["_den_" + nombre] = den

    todos = pd.Series(True, index=d.index)
    res = d.residente
    # ── demografía ──
    pct(d.edad.between(0, 14), todos, "pct_0_14")
    pct(d.edad.between(15, 64), todos, "pct_15_64")
    pct(d.edad >= 65, todos, "pct_65_mas")
    pct(d.edad < 20, todos, "pct_menor20")
    pct(d.edad >= 60, todos, "pct_60_mas")
    out["edad_mediana"] = d.groupby("cod_ine").edad.median()
    out["edad_promedio"] = d.groupby("cod_ine").edad.mean()
    out["indice_masculinidad"] = 100 * (tot - out["n_mujeres"]) / out["n_mujeres"]
    out["pob_hombres"] = tot - out["n_mujeres"]
    pct(d.edad.between(0, 4), todos, "pct_0_4")
    pct(d.edad.between(15, 29), todos, "pct_15_29")
    pct(d.edad >= 80, todos, "pct_80_mas")
    # razones de dependencia: sobre la población en edad activa, no sobre el total
    n0_14 = d[d.edad.between(0, 14)].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n15_64 = d[d.edad.between(15, 64)].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n65 = d[d.edad >= 65].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n15_29 = d[d.edad.between(15, 29)].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    out["razon_dependencia"] = 100 * (n0_14 + n65) / n15_64.replace(0, np.nan)
    out["dep_juvenil"] = 100 * n0_14 / n15_64.replace(0, np.nan)
    out["dep_senil"] = 100 * n65 / n15_64.replace(0, np.nan)
    out["indice_envejecimiento"] = 100 * n65 / n0_14.replace(0, np.nan)
    # ⚠️ CORREGIDO 2026-08-13 al validar contra `poblacion/9`: el motor calculaba
    #    15-29 sobre la población total (30,2 en Sucre) y el INE publica 336,45.
    #    Su "índice de juventud" es 0-14 sobre 65+, o sea el INVERSO EXACTO del
    #    índice de envejecimiento — no "qué proporción de la gente es joven".
    #    La proporción de jóvenes ya existe aparte, en `pct_15_29`.
    out["indice_juventud"] = 100 * n0_14 / n65.replace(0, np.nan)
    # ── educación ──
    # el denominador del INE son quienes RESPONDIERON, no toda la franja de edad
    pct(d.lee, res & (d.edad >= 15) & d.lee_resp, "pct_analfabetismo")
    # el Atlas lo publica aparte para poder leer la brecha de género de frente
    pct(d.lee, res & (d.edad >= 15) & d.lee_resp & d.mujer, "pct_analfabetismo_mujeres")
    pct(d.asiste, res & d.edad.between(4, 17) & d.asiste_resp, "pct_asistencia_4_17")
    pct(d.publica, res & d.edad.between(4, 17) & d.asiste, "pct_educacion_publica")
    pct(d.asiste, res & d.edad.between(4, 5) & d.asiste_resp, "tasa_asistencia_4_5")
    pct(d.asiste, res & d.edad.between(18, 24) & d.asiste_resp, "tasa_asistencia_18_24")
    edu = res & (d.edad >= 19) & (d.nivel != "")
    for n in ("ninguno", "primaria", "secundaria", "superior"):
        pct(d.nivel == n, edu, "pct_edu_" + n)
    pct(d.nivel.isin(["secundaria", "superior"]), edu, "pct_secundaria_mas")
    pct(d.anios_estudio >= 6, edu, "pct_primaria_completa")
    # ── brechas de género: mujeres menos hombres, en puntos porcentuales ──
    def brecha(mask, universo, nombre):
        # ⚠️ Si en un municipio NINGUNA mujer (o ningún hombre) cumple la
        #    condición, el groupby no devuelve fila para ese municipio y la
        #    división daba NaN en vez de 0. Coipasa, Uru Chipaya y La Rivera
        #    quedaban sin brecha de alfabetismo por eso —descubierto al validar
        #    contra `educacion/1`, que sí publica el valor—. No es que falte el
        #    dato: es que el numerador es cero. Hay que reindexar ANTES de dividir.
        u = d[universo]
        m, h = u[u.mujer], u[~u.mujer]
        dm, dh = m.groupby("cod_ine").size(), h.groupby("cod_ine").size()
        nm = m[mask[m.index]].groupby("cod_ine").size().reindex(dm.index, fill_value=0)
        nh = h[mask[h.index]].groupby("cod_ine").size().reindex(dh.index, fill_value=0)
        out[nombre] = (100 * nm / dm - 100 * nh / dh).reindex(tot.index)
        # ★ UNA BRECHA NO SE PROMEDIA, ni siquiera ponderando: es la RESTA de dos
        #   porcentajes, y el agregado hay que rearmarlo desde los componentes
        #   (calcular el % de mujeres y el de hombres del departamento y recién
        #   ahí restar). Por eso viajan los cuatro números que hacen falta.
        out[nombre + "_muj"] = (100 * nm / dm).reindex(tot.index)
        out[nombre + "_hom"] = (100 * nh / dh).reindex(tot.index)
        out["_den_" + nombre + "_muj"] = dm.reindex(tot.index)
        out["_den_" + nombre + "_hom"] = dh.reindex(tot.index)
    brecha(d.lee, res & (d.edad >= 15) & d.lee_resp, "brecha_alfabetismo")
    brecha(d.nivel == "superior", edu, "brecha_edu_superior")
    e19b = res & (d.edad >= 19) & d.anios_estudio.notna()
    _am = d[e19b & d.mujer].groupby("cod_ine").anios_estudio.mean()
    _ah = d[e19b & ~d.mujer].groupby("cod_ine").anios_estudio.mean()
    out["brecha_anios_estudio"] = (_am - _ah).reindex(tot.index)
    out["brecha_anios_estudio_muj"] = _am.reindex(tot.index)
    out["brecha_anios_estudio_hom"] = _ah.reindex(tot.index)
    out["_den_brecha_anios_estudio_muj"] = d[e19b & d.mujer].groupby("cod_ine").size().reindex(tot.index)
    out["_den_brecha_anios_estudio_hom"] = d[e19b & ~d.mujer].groupby("cod_ine").size().reindex(tot.index)
    # ── empleo ──
    ocu = d.ocupado & (d.edad >= 14) & res
    for n in ("asalariado", "cuenta_propia", "empleador", "familiar",
              "hogar", "cooperativista"):
        pct(d.catocu == n, ocu, "pct_catocu_" + n)
    # la columna del INE "Empleada(o) u obrera(o) (2)" INCLUYE trabajadoras del hogar
    pct(d.catocu.isin(["asalariado", "hogar"]), ocu, "pct_catocu_asalariado_amplio")
    # ── tasas de empleo con CORTE PROPIO A 15+ ──
    # ★ NO se usan `pea_13`/`PEA`: en 2012 su base es 10 años y en 2024 son 7.
    #   Publicar esas tasas como serie sería comparar dos poblaciones distintas.
    pet = res & (d.edad >= 15)
    activo = (d.ocupado | d.desocupado)
    n_pet = d[pet].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n_pea = d[pet & activo].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n_ocu = d[pet & d.ocupado].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    # ★ el universo de las tasas de empleo es la PET 15+, no la población:
    #   sin este denominador el Atlas las agregaba ponderando por población y
    #   los municipios jóvenes pesaban de más
    out["tasa_participacion"] = 100 * n_pea / n_pet.replace(0, np.nan)
    out["tasa_ocupacion"] = 100 * n_ocu / n_pet.replace(0, np.nan)
    out["_den_tasa_participacion"] = n_pet
    out["_den_tasa_ocupacion"] = n_pet
    out["_den_tasa_desocupacion"] = n_pea
    out["tasa_desocupacion"] = 100 * (n_pea - n_ocu) / n_pea.replace(0, np.nan)
    # ── cortes femeninos: los pide el Atlas Socioeconómico y son el mismo
    #    cálculo restringido a mujeres, con la MISMA base 15+ (no la del INE,
    #    que cambia entre censos y rompería la serie)
    pet_f = pet & d.mujer
    n_pet_f = d[pet_f].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n_pea_f = d[pet_f & activo].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    n_ocu_f = d[pet_f & d.ocupado].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    out["tasa_participacion_fem"] = 100 * n_pea_f / n_pet_f.replace(0, np.nan)
    out["tasa_ocupacion_fem"] = 100 * n_ocu_f / n_pet_f.replace(0, np.nan)
    out["_den_tasa_participacion_fem"] = n_pet_f
    out["_den_tasa_ocupacion_fem"] = n_pet_f
    for s, cods in [("primario", [1, 2]), ("secundario", [3, 4, 5, 6]),
                    ("servicios", list(range(7, 22)))]:
        pct(d.rama.isin(cods), ocu, "pct_sector_" + s)
    nh = d[pet & ~d.mujer].groupby("cod_ine").size()
    nm = d[pet & d.mujer].groupby("cod_ine").size()
    _bh = 100 * d[pet & activo & ~d.mujer].groupby("cod_ine").size() / nh
    _bm = 100 * d[pet & activo & d.mujer].groupby("cod_ine").size() / nm
    out["brecha_participacion"] = (_bh - _bm).reindex(tot.index)
    out["brecha_participacion_hom"] = _bh.reindex(tot.index)
    out["brecha_participacion_muj"] = _bm.reindex(tot.index)
    out["_den_brecha_participacion_hom"] = nh.reindex(tot.index)
    out["_den_brecha_participacion_muj"] = nm.reindex(tot.index)
    pct(d.ocu1d.isin([1, 2, 3]), ocu, "pct_ocu_profesionales")
    pct(d.ocu1d == 9, ocu, "pct_ocu_no_calificado")
    for n, cods in [("agricultura", [1]), ("manufactura", [3]), ("construccion", [6]),
                    ("comercio", [7]), ("transporte", [8]), ("alojamiento", [9]),
                    ("mineria", [2]), ("adm_publica", [15]), ("ensenanza", [16]),
                    ("salud", [17])]:
        pct(d.rama.isin(cods), ocu, "pct_rama_" + n)
    # ── salud ──
    # el cuadro de salud se publica sobre la POBLACIÓN TOTAL, no sobre residentes:
    # el total de Bolivia 2012 del tabulado es 10.059.856, la población entera
    for k in ("publica", "caja", "privada", "tradic", "autome", "casera"):
        pct(d["s_" + k], todos, "pct_salud_" + k)
    # ── ciudadanía, pueblos e idiomas ──
    pct(d.registro, res, "pct_registro_civil")
    pct(d.cedula, res, "pct_cedula")
    pct(d.indigena, res & (d.edad >= 15), "pct_autoident_indigena")
    # ── migración ──
    pct(~d.nac_aqui & ~d.nac_exterior, res, "pct_nacido_otro_municipio")
    pct(d.nac_exterior, res, "pct_nacido_extranjero")
    pct(d.res5_otro, res & (d.edad >= 5), "pct_migrante_reciente")
    # ── fecundidad ──
    # ★ PARIDEZ MEDIA = LA DEFINICIÓN DEL INE (adoptada 2026-08-14).
    #   Verificado aritméticamente contra `salud/6`: su paridez es
    #   `hijos nacidos vivos / (total de mujeres − sin información)` y su
    #   universo son las MUJERES EN EDAD FÉRTIL (15-49) — 87.540 en Sucre,
    #   contra 116.900 si fueran todas las de 15+. Eso es exactamente lo que
    #   este motor venía llamando `fecundidad`.
    #   El nombre ya tiene dueño público: publicar otra cosa bajo él es el error,
    #   por correcto que sea nuestro cálculo.
    mef = res & d.mujer & d.edad.between(15, 49) & d.hijos_nac.notna()
    out["paridez_media"] = d[mef].groupby("cod_ine").hijos_nac.mean()
    out["_den_paridez_media"] = d[mef].groupby("cod_ine").size()
    # la versión sobre mujeres de 12+ se conserva con nombre propio: es un
    # indicador legítimo, pero NO es el que el INE publica como paridez media
    m12 = res & d.mujer & (d.edad >= 12) & d.hijos_nac.notna()
    out["paridez_media_12mas"] = d[m12].groupby("cod_ine").hijos_nac.mean()
    # ⚠️ El cociente exige que estén LAS DOS variables en la misma mujer.
    #    565.290 mujeres en 2012 (1.021.545 en 2024) declaran hijos nacidos y
    #    tienen el campo de sobrevivientes en "no aplica" —código grande que el
    #    recorte deja en NaN—. Sumando cada columna por su lado, sus 88.285
    #    hijos entraban al numerador sin par en el denominador e inflaban el
    #    porcentaje de fallecidos.
    amb = m12 & d.hijos_viv.notna()
    hn = d[amb].groupby("cod_ine").hijos_nac.sum()
    hv = d[amb].groupby("cod_ine").hijos_viv.sum()
    out["pct_hijos_fallecidos"] = 100 * (1 - hv / hn)
    out["_den_pct_hijos_fallecidos"] = hn          # el universo son los HIJOS
    # ── parto calificado ──
    # ★ El universo NO son todas las madres de 15-49: es quien tuvo un parto en
    #   los últimos cinco años, que es a quien se le hace la pregunta. Con el
    #   denominador viejo daba 40,8% en la región metropolitana.
    # ⚠️ 2012 QUEDA VACÍO A PROPÓSITO. Su variable `P49B` existe pero el
    #    diccionario Redatam NO trae etiquetas para sus categorías (1, 2, 3, 9),
    #    y la regla anterior —`isin([1,2])`— daba 96,9%, incompatible con
    #    cualquier cifra publicada para 2012. Antes que inventar una caída de
    #    −56 pp que es un artefacto de definición, se deja sin dato hasta
    #    conseguir el cuestionario de 2012.
    if "parto_quien" in d.columns and d.parto_quien.notna().any():
        pct(d.parto_quien.isin([1, 2, 3]), res & d.parto_quien.between(1, 8),
            "pct_parto_calificado")
    else:
        pct(pd.Series(np.nan, index=d.index), res, "pct_parto_calificado")
    # ── jefatura y estructura del hogar ──
    jefes = res & d.jefe
    pct(d.mujer, jefes, "pct_jefatura_femenina")
    out["edad_media_jefe"] = d[jefes].groupby("cod_ine").edad.mean()
    # ── años de estudio (19+) ──
    # ★★ SIN EDUCACIÓN = CERO AÑOS, NO "sin dato" (corregido 2026-08-13).
    #    `ANIOS12` no mapeaba los niveles 1 Ninguno, 2 Alfabetización y 3 Inicial,
    #    así que esas personas salían NaN y **se caían del promedio**. El sesgo se
    #    ve en el dato: contra `educacion/4` nos pasábamos 0,99 años en Sucre
    #    (9% sobre 10,45) pero 1,64 en Poroma (45% sobre 3,62) — el error es
    #    proporcionalmente mayor donde hay MENOS educación, que es la firma de
    #    estar excluyendo a los que no tienen ninguna.
    #    Se recalcula acá, en la capa de reglas, aprovechando que la caché guarda
    #    `nivel_cod` y `curso_cod` crudos: así no hace falta rehacerla.
    if "nivel_cod" in d.columns and d.nivel_cod.notna().any():
        base = d.nivel_cod.map(ANIOS12)
        anios12 = np.where(d.nivel_cod.isin([1, 2, 3]), 0.0,
                           base + d.curso_cod.fillna(0))
        d = d.assign(anios_estudio=pd.Series(anios12, index=d.index).where(
            lambda x: (x >= 0) & (x <= 30)))
    e19 = res & (d.edad >= 19) & d.anios_estudio.notna()
    out["prom_anios_estudio"] = d[e19].groupby("cod_ine").anios_estudio.mean()
    out["_den_prom_anios_estudio"] = d[e19].groupby("cod_ine").size()
    # ── estado civil ──
    # la caché guarda el código CRUDO de cada censo; la armonización vive acá,
    # junto a la comparación, igual que los pueblos y el `MAPEO` de motor.py
    ecivil = _map(d.ecivil, ECIVIL24 if anio == 2024 else ECIVIL12)
    conyugal = res & (d.edad >= 15) & ecivil.ne("")
    for n in ("casado", "conviviente", "separado_divorciado", "viudo", "soltero"):
        pct(ecivil == n, conyugal, "pct_ecivil_" + n)
    # ── pueblos al detalle: la comparación es por NOMBRE (ver PUEBLOS arriba) ──
    ind15 = res & (d.edad >= 15)
    pueblo = d.pueblo.replace(SINONIMOS)
    for n in PUEBLOS:
        pct(pueblo == n, ind15, "pct_pueblo_" + n)
    # ── discapacidad (sólo 2024: 2012 la capta a nivel hogar) ──
    dcols = ["disc_ver", "disc_oir", "disc_caminar", "disc_comunicar"]
    for k in ("ver", "oir", "caminar", "comunicar"):
        pct(d["disc_" + k], res, "pct_disc_" + k)
    # ⚠️ `.any(axis=1)` sobre columnas vacías devuelve False, no NaN: la guarda de
    #    `pct` no se dispararía y el agregado volvería a publicar 0,00% en 2012.
    #    Hay que preguntar por el censo, no por el resultado del `any`.
    hay_disc = any(d[c].dtype == bool for c in dcols)
    pct(d[dcols].any(axis=1) if hay_disc else pd.Series(np.nan, index=d.index),
        res, "pct_discapacidad")
    # ── afiliación de salud (sólo 2024) ──
    afi = res & d.afiliado.between(1, 4)
    for n, c in [("sus", 1), ("caja", 2), ("privado", 3), ("ninguno", 4)]:
        pct(d.afiliado == c, afi, "pct_afiliado_" + n)
    pct(d.afiliado.between(1, 3), afi, "pct_seguro_salud")
    # ── maternidad ──
    pct(d.hijos_nac.gt(0), res & d.mujer & d.edad.between(15, 19), "pct_madres_adolescentes")
    out["edad_1er_hijo"] = d[res & d.mujer & d.edad_madre_1.notna()]                              .groupby("cod_ine").edad_madre_1.mean()
    # ── IDIOMA MATERNO ──
    # ★ UNIVERSO = RESIDENTES DE 4 O MÁS AÑOS (idiomas_1, cuadro 1). Las dos
    #   condiciones hacen falta y se verificaron contra el registro:
    #     4+ y todos       10.703.866   (98.649 de más)
    #     4+ y residentes  10.605.217   = exactamente el total del INE
    #   Incluye "No habla" y "Sin especificar": el denominador NO se recorta a
    #   quienes contestaron.
    idi = res & (d.edad >= 4)
    pct(d.idioma == CASTELLANO, idi, "pct_idioma_castellano")
    # originario = los idiomas OFICIALES menos el castellano. Los códigos 1..37
    # son los oficiales en los dos censos; 2024 suma Afroboliviano, Joaquiniano
    # y "Otras declaraciones" al mismo bloque (ver OFI_EXTRA).
    orig = (OFICIALES | OFI_EXTRA.get(anio, set())) - {CASTELLANO}
    pct(d.idioma.isin(list(orig)), idi, "pct_idioma_materno_originario")
    pct(d.bilingue, res & (d.edad >= 5), "pct_bilingue")
    pct(d.registro, res & (d.edad < 5), "pct_registro_menores5")
    # ── migración de residencia ──
    pct(d.res_otro_mun, res, "pct_residia_otro_mun")
    # ── REZAGO ESCOLAR ──
    # ⚠️ NO sirve `anios_estudio`: en 2024 la variable del INE (`aestudio`) está
    #    definida sólo para 19 o más años, así que en toda la franja escolar
    #    viene vacía. Hay que armarlo desde el curso aprobado.
    # Un chico que entra a los 6 y nunca repite lleva (edad − 6) años aprobados.
    # Se marca rezago con DOS o más años de atraso: uno solo puede ser el mes de
    # nacimiento o el corte de matrícula, no repetición.
    if "curso_nivel" in d.columns and d.curso_nivel.notna().any():
        base = d.curso_nivel.map(ANIOS24)
        anios = base + d.curso_anio.fillna(0)
    else:
        anios = d.anios_estudio            # 2012 ya lo trae armado con ANIOS12
    esc = res & d.edad.between(8, 17) & anios.notna()
    pct(anios <= (d.edad - 8), esc, "pct_rezago_escolar")
    # ── ESTRUCTURA DEL HOGAR ──
    # ★ El universo son HOGARES, no personas: se cuenta una vez por hogar. La
    #   clave viene de `i00` en 2024 y del índice de vivienda del Redatam en
    #   2012, y en los dos casos es única a nivel nacional.
    if "hogar" in d.columns and d.hogar.notna().any():
        h = pd.DataFrame({"hogar": d.hogar[res], "cod_ine": d.cod_ine[res],
                          "menor": (d.edad < 15)[res], "am": (d.edad >= 65)[res],
                          "jefe": d.jefe[res]})
        ag = h.groupby("hogar", observed=True).agg(
            cod_ine=("cod_ine", "first"), n=("hogar", "size"),
            con_menor=("menor", "max"), con_am=("am", "max"),
            con_jefe=("jefe", "max"))
        nh = ag.groupby("cod_ine", observed=True).size().reindex(tot.index, fill_value=0)
        def phog(mask, nombre):
            num = ag[mask].groupby("cod_ine", observed=True).size().reindex(tot.index, fill_value=0)
            out[nombre] = 100 * num / nh.replace(0, np.nan)
            out["_den_" + nombre] = nh
        phog(ag.con_menor, "pct_hogar_con_menores")
        phog(ag.con_am, "pct_hogar_con_am")
        # ★ HOGAR UNIPERSONAL — definición del GLOSARIO DEL INE: "compuesto por
        #   una persona, QUE POR DEFINICIÓN ES LA JEFA O JEFE DE HOGAR". Antes se
        #   calculaba en motor.py como `tot_pers == 1` a secas, sin exigir la
        #   jefatura, y validaba sólo 141/343: quien vive solo pero no se declara
        #   jefe cae en "hogares sin jefe de hogar" en la tipología del INE.
        #   Se calcula ACÁ porque el motor de vivienda no conoce el parentesco.
        solo = (ag.n == 1) & ag.con_jefe
        phog(solo, "pct_hogar_unipersonal")
        # adulto mayor viviendo SOLO: el mismo hogar unipersonal, de 65 o más
        phog(solo & ag.con_am, "pct_am_solo")
        out["hogares"] = nh
        out["tam_hogar_pers"] = ag.groupby("cod_ine", observed=True).n.mean().reindex(tot.index)
    # ── CONMUTACIÓN LABORAL (sólo 2024: la pregunta no existe en 2012) ──
    # `_cod6` deja "" en los códigos inválidos, así que el filtro de largo 6 ya
    # separa a quien declaró municipio de trabajo. Antes esto no encontraba una
    # sola fila porque el código venía escrito como "70101.0".
    aqui = d.cod_ine.astype(str)
    trabaja = ocu & d.mun_trabaja.str.len().eq(6)
    n_tr = d[trabaja].groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    propio = d[trabaja & (d.mun_trabaja == aqui)]                .groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    out["autocontencion_laboral"] = 100 * propio / n_tr.replace(0, np.nan)
    out["pct_trabaja_fuera"] = 100 - out["autocontencion_laboral"]
    # ⚠️ "la capital" era Santa Cruz de la Sierra CABLEADA. El motor calcula los
    #    343 municipios del país, así que para los otros ocho departamentos el
    #    indicador medía la dependencia de una ciudad ajena. Ahora es la capital
    #    del PROPIO departamento (código de departamento + "0101").
    cap_dep = aqui.str[:2] + "0101"
    cap = d[trabaja & (d.mun_trabaja == cap_dep) & (d.mun_trabaja != aqui)]             .groupby("cod_ine").size().reindex(tot.index, fill_value=0)
    out["dependencia_capital"] = 100 * cap / n_tr.replace(0, np.nan)
    # los tres flujos se calculan sobre quienes DECLARARON dónde trabajan
    for _f in ("autocontencion_laboral", "pct_trabaja_fuera", "dependencia_capital"):
        out["_den_" + _f] = n_tr
    return pd.DataFrame(out)


def urbrur_2024(d):
    """Marca urbana/rural en la persona, traída de SU VIVIENDA.

    ★ POR QUÉ HACE FALTA. El tablero municipio↔manzana sirve TRES cifras por
      indicador —municipio · municipio URBANO · manzana— y la del medio es la
      única estrictamente comparable con la manzana, que es un bloque urbano.
      `motor.py` ya la emitía para vivienda (`municipal_urbano_*`), pero el
      bloque de PERSONA no la tenía, así que 20 de los 62 comparables no se
      podían verificar: la diferencia contra el municipio entero mezcla el sesgo
      urbano con una posible definición distinta y no se pueden separar.

    ⚠️ NO se toca la caché ni `ESPERADAS`: la marca se pega DESPUÉS, por la clave
       `hogar` (cod_ine + i00) que el motor ya construye y que es la misma llave
       de la vivienda. Rehacer el parquet cuesta ~20 minutos y acá no hace falta.
    """
    v = pd.read_csv(CPV24 / "Vivienda_CPV-2024.csv", sep=";", encoding="latin-1",
                    usecols=["idep", "iprov", "imun", "i00", "urbrur"], dtype=str)
    ci = v.idep.str.zfill(2) + v.iprov.str.zfill(2) + v.imun.str.zfill(2)
    llave = (pd.to_numeric(ci, errors="coerce").astype("int64") * 100_000_000
             + pd.to_numeric(v.i00, errors="coerce").fillna(0).astype("int64"))
    # ⚠️ `.to_numpy()` NO es cosmético: `pd.Series(otra_serie, index=...)`
    #    REINDEXA por el índice viejo en vez de reetiquetar, así que el mapa salía
    #    todo NaN y quedaban CERO personas urbanas — sin que nada fallara.
    es_urb = (pd.to_numeric(v.urbrur, errors="coerce") == 1).to_numpy()
    urb = pd.Series(es_urb, index=llave.to_numpy())
    urb = urb[~urb.index.duplicated()]
    m = d.hogar.map(urb).fillna(False).to_numpy()
    if not m.any():
        raise SystemExit("urbrur_2024: ninguna persona cruzó con su vivienda — "
                         "revisar la clave `hogar` antes de seguir")
    return m


if __name__ == "__main__":
    import sys
    aqui = pathlib.Path(__file__).parent
    # `--urbano` recalcula SÓLO la mitad urbana de 2024: con las cachés calientes
    # son minutos, contra la corrida entera de los dos censos.
    if "--urbano" in sys.argv:
        d24 = cargar_2024()
        ru = calcular(d24[urbrur_2024(d24)], 2024)
        ru.to_csv(aqui / "personas_urbano_2024.csv", encoding="utf-8")
        print(f"urbano 2024: {int(ru.poblacion.sum()):,} personas · {len(ru)} municipios")
        print("→ personas_urbano_2024.csv")
        raise SystemExit(0)
    print("2024 …", flush=True); d24 = cargar_2024(); r24 = calcular(d24, 2024)
    print("  urbano 2024 …", flush=True)
    ru = calcular(d24[urbrur_2024(d24)], 2024)
    print("2012 …", flush=True); r12 = calcular(cargar_2012(), 2012)
    print(f"\n2024: {int(r24.poblacion.sum()):,} personas · {len(r24)} municipios "
          f"· {len([c for c in r24.columns if not c.startswith('_')])} columnas")
    print(f"      urbano: {int(ru.poblacion.sum()):,} personas · {len(ru)} municipios")
    print(f"2012: {int(r12.poblacion.sum()):,} personas · {len(r12)} municipios")
    aqui = pathlib.Path(__file__).parent
    r24.to_csv(aqui / "personas_2024.csv", encoding="utf-8")
    ru.to_csv(aqui / "personas_urbano_2024.csv", encoding="utf-8")
    r12.to_csv(aqui / "personas_2012.csv", encoding="utf-8")
    print("→ personas_2024.csv · personas_urbano_2024.csv · personas_2012.csv")
