"""
Crosswalk manzana ↔ municipio.

Empareja los 52 indicadores derivados por manzana (Censo 2024, fichas del INE)
con los 136 del Atlas Socioeconómico Municipal, para que el tablero pueda
CONSERVAR el indicador cuando el usuario hace zoom y sólo cambie la resolución.

Se hace A MANO a propósito. Un emparejador por similitud de texto produjo
`Gas por cañería = Agua por cañería` con 0,82 de puntaje: en un crosswalk, un
falso positivo no es ruido, es un dato equivocado que después nadie revisa.

TRES ESTADOS, y el del medio es el que importa:

  "si"       misma definición y mismo universo → el toggle mantiene el indicador
             y el número es continuo entre niveles.
  "no"       existe el gemelo temático pero mide OTRA COSA (otro corte de edad,
             otro denominador, incluye categorías distintas). El toggle puede
             seguir en el mismo tema, pero la ficha DEBE avisar que la definición
             cambia. Si no, el usuario hace zoom, ve saltar el número y lee un
             cambio territorial que no ocurrió.
  null       no hay gemelo: el indicador sólo vive en la manzana.

De dónde sale el problema de fondo: las fichas por manzana traen los cortes de
edad 0-19 / 20-39 / 40-59 / 60+, y el Atlas usa los estándares (0-14, 15+, 25+,
65+). No es un descuido nuestro: es lo único que el INE publica a nivel de
manzano, y no se puede reconstruir "25 y más" desde ahí.
"""
import json
from pathlib import Path

SALIDA = Path(__file__).resolve().parent.parent / "datos" / "crosswalk.json"

# (clave_manzana, clave_municipal, comparable, nota)
PARES = [
    # ── Población y hogar ────────────────────────────────────────────────────
    ("personas",            "pob_total",            "si",  None),
    ("viviendas",           None,                   None,  "El Atlas no publica el total de viviendas."),
    ("pers_x_vivienda",     "tam_hogar",            "no",  "Vivienda ≠ hogar: una vivienda puede alojar más de un hogar, así que el municipal es sistemáticamente menor."),
    ("densidad",            None,                   None,  "No existe a nivel municipal; la superficie municipal incluye lo rural y la densidad no sería comparable."),
    ("pct_menor20",         "pct_0_14",             "no",  "Cortes distintos: 0-19 en la manzana, 0-14 en el municipio."),
    ("pct_60mas",           "pct_65_mas",           "no",  "Cortes distintos: 60+ en la manzana, 65+ en el municipio."),
    ("dependencia",         "razon_dependencia",    "no",  "La manzana usa (0-19 + 60+) / (20-59); el estándar municipal usa (0-14 + 65+) / (15-64)."),
    ("masculinidad",        "indice_masculinidad",  "si",  None),

    # ── Migración ────────────────────────────────────────────────────────────
    ("pct_nacido_otro_mun", "pct_nacido_otro_municipio", "si", None),
    ("pct_nacido_exterior", "pct_nacido_extranjero",     "si", None),
    ("pct_residia_otro_mun","pct_migrante_reciente", "revisar", "Probable equivalencia (residencia previa vs. migración desde 2019), pero hay que confirmar contra la boleta censal antes de darlo por comparable."),

    # ── Educación ────────────────────────────────────────────────────────────
    ("pct_educ_superior",   "pct_edu_superior",     "no",  "El municipal es sobre 25 años y más; el de manzana es sobre todas las personas con dato educativo, así que sale más bajo."),
    ("pct_sin_educacion",   "pct_sin_educacion",    "no",  "⚠ MISMA CLAVE, universo distinto: el municipal es 15+, el de manzana es toda la población con dato. La coincidencia de nombre es una trampa."),
    ("brecha_educ_superior", None,                  None,  "Aporte propio: el Atlas no desagrega educación por sexo."),
    ("brecha_sin_educacion", None,                  None,  "Aporte propio."),

    # ── Salud ────────────────────────────────────────────────────────────────
    ("pct_sin_seguro",      "pct_seguro_salud",     "no",  "Es el COMPLEMENTO, no el mismo indicador: para compararlos hay que invertir uno de los dos."),
    ("pct_sus",             None,                   None,  "El Atlas mide dónde se ATIENDE la gente, no a qué seguro está afiliada."),
    ("pct_seguro_privado",  None,                   None,  "Ídem: `pct_salud_privada` del Atlas es atención, no afiliación."),
    ("pct_automedicacion",  "pct_automedicacion",   "si",  None),
    ("pct_med_tradicional", "pct_salud_tradicional","si",  None),
    ("brecha_sin_seguro",   None,                   None,  "Aporte propio."),

    # ── Trabajo ──────────────────────────────────────────────────────────────
    ("pct_empleado",        "pct_asalariados",      "si",  None),
    ("pct_cuentapropia",    "pct_cuenta_propia",    "si",  None),
    ("brecha_cuentapropia", None,                   None,  "Aporte propio."),
    ("pct_comercio",        "pct_comercio",         "si",  None),
    ("pct_manufactura",     "pct_sector_secundario","no",  "El sector secundario del Atlas incluye construcción; el de manufactura de la manzana no."),
    ("pct_construccion",    None,                   None,  "El Atlas la agrupa dentro del sector secundario."),
    ("pct_agricultura",     "pct_sector_primario",  "no",  "El sector primario del Atlas suma minería."),
    ("pct_transporte",      None,                   None,  "El Atlas sólo publica el agregado de servicios."),
    ("pct_alojamiento",     None,                   None,  "Ídem."),

    # ── Vivienda ─────────────────────────────────────────────────────────────
    ("pct_viv_propia",      "pct_vivienda_propia",  "si",  None),
    ("pct_viv_alquilada",   "pct_alquiler",         "si",  None),
    ("pct_viv_anticretico", None,                   None,  "El Atlas no separa el anticrético."),
    ("pct_viv_desocupada",  "pct_vivienda_desocupada", "si", None),

    # ── Servicios básicos ────────────────────────────────────────────────────
    ("pct_agua_red",        "pct_agua_caneria",     "si",  None),
    ("pct_agua_pozo",       "pct_agua_pozo",        "si",  None),
    ("pct_alcantarillado",  "pct_alcantarillado",   "si",  None),
    ("pct_camara_septica",  "pct_camara_septica",   "si",  None),
    ("pct_pozo_ciego",      "pct_pozo_ciego",       "no",  "El municipal es «pozo ciego O superficie»; el de manzana es sólo pozo ciego (la superficie va en `pct_sin_desague`)."),
    ("pct_sin_desague",     None,                   None,  "El Atlas reparte estas categorías dentro de `pct_pozo_ciego`."),
    ("pct_electricidad",    "pct_electricidad",     "si",  None),
    ("pct_gas_red",         "pct_gas_natural",      "si",  None),
    ("pct_gas_garrafa",     "pct_gas_garrafa",      "si",  None),
    ("pct_lena_guano",      "pct_combustible_solido", "si", None),
    ("pct_basura_carro",    "pct_basura_formal",    "si",  None),
    ("pct_basura_quema",    None,                   None,  "El Atlas sólo publica el recojo formal, no el destino de la basura no recogida."),
    ("pct_basura_informal", None,                   None,  "Ídem."),
    ("idx_carencia",        None,                   None,  "Índice propio. El pariente municipal conceptual es `pct_nbi_pobre`, pero la NBI usa otra construcción y NO debe presentarse como su versión amanzanada."),

    # ── Conectividad ─────────────────────────────────────────────────────────
    ("pct_internet",        "pct_internet",         "si",  None),
    ("pct_celular",         "pct_celular",          "si",  None),
    ("pct_televisor",       "pct_tv",               "si",  None),
    ("pct_radio",           "pct_radio",            "si",  None),
]


def main():
    raiz = Path(__file__).resolve().parent.parent
    mz = json.loads((raiz / "datos" / "catalogo.json").read_text(encoding="utf-8"))
    at = json.loads((raiz.parent / "Observatorio de Presupuesto Fiscal Departamental"
                     / "_github_atlas_fiscal" / "catalogo.json").read_text(encoding="utf-8"))

    claves_mz = {i["key"]: i["label"] for g in mz["grupos"] for i in g["indicadores"]}
    claves_at = {i["key"]: i["label"] for g in at["grupos"] for i in g["indicadores"]}

    # Verificación: que no se me haya escapado ni inventado ninguna clave.
    declaradas = {p[0] for p in PARES}
    if declaradas != set(claves_mz):
        sys_faltan = set(claves_mz) - declaradas
        sys_sobran = declaradas - set(claves_mz)
        raise SystemExit(f"ERROR de cobertura — faltan: {sorted(sys_faltan)} · sobran: {sorted(sys_sobran)}")
    malas = [p for p in PARES if p[1] and p[1] not in claves_at]
    if malas:
        raise SystemExit(f"ERROR: claves municipales inexistentes: {[m[1] for m in malas]}")

    filas = []
    for k_mz, k_at, comp, nota in PARES:
        filas.append({
            "manzana": k_mz,
            "label_manzana": claves_mz[k_mz],
            "municipal": k_at,
            "label_municipal": claves_at.get(k_at),
            "comparable": comp,
            "nota": nota,
        })

    SALIDA.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")

    t = {"si": 0, "no": 0, "revisar": 0, "solo_manzana": 0}
    for f in filas:
        t["solo_manzana" if f["municipal"] is None else f["comparable"]] += 1
    print(f"Crosswalk: {len(filas)} indicadores de manzana")
    print(f"  comparables directo      {t['si']:>3}   el toggle mantiene el indicador y el número es continuo")
    print(f"  gemelo NO comparable     {t['no']:>3}   mismo tema, otra definición → la ficha debe avisar")
    print(f"  a confirmar              {t['revisar']:>3}")
    print(f"  sólo en la manzana       {t['solo_manzana']:>3}")
    print(f"\n→ {SALIDA}")


if __name__ == "__main__":
    main()
