# -*- coding: utf-8 -*-
"""
ARMADO FINAL — la base del Tablero 1 (municipal, con serie intercensal).

Une los cuatro archivos que producen los motores (vivienda y personas × 2012 y
2024), recorta a los nueve municipios metropolitanos y calcula el cambio entre
censos. Emite un JSON listo para la web y un CSV para revisar a mano.

Regla del cambio, que no es cosmética:
  · un PORCENTAJE cambia en puntos porcentuales (pp), no en %.
    Pasar de 40% a 60% no es "+50%", es "+20 pp".
  · un CONTEO (habitantes, viviendas) cambia en % y además se da la tasa anual
    equivalente, que es lo comparable entre períodos de distinta duración.
"""
import pathlib, json, csv, numpy as np, pandas as pd
from alias import renombrar

AQUI = pathlib.Path(__file__).parent
SCZ = AQUI.parent
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")
ANIOS = 12.0          # 2012 → 2024

# ── cómo cambia cada indicador, según la UNIDAD que declara el catálogo ──────
# ⚠️ Antes esto era una lista a mano con el vocabulario del MOTOR
#    (`poblacion`, `n_viviendas`); al traducir al vocabulario del catálogo dejó
#    de coincidir y la población pasó a informarse como "+42.066,7 pp".
#    Ahora manda el catálogo, que es donde vive la unidad.
UNI_CONTEO = {"hab", "pers", "viv"}      # cambian en % y con tasa anual
UNI_PCT = {"%"}                          # cambian en puntos porcentuales
_cat = {i["k"]: i["u"] for i in
        json.loads((pathlib.Path(__file__).parent / "catalogo.json")
                   .read_text(encoding="utf-8"))["indicadores"]}
# lo que el catálogo aún no declara pero el motor sí produce
_cat.update({"pob_hombres": "hab", "poblacion_nbi": "hab", "emigrantes": "hab",
             "fallecidos": "hab", "edad_prom_emigracion": "años",
             "edad_prom_fallecimiento": "años", "edad_media_jefe": "años",
             "edad_1er_hijo": "años", "edad_promedio": "años"})
# los flujos son conteos de personas (pueden ser NEGATIVOS: son saldos)
_cat.update({k: "hab" for k in (
    "inmigrantes_5a", "emigrantes_internos_5a", "saldo_migratorio",
    "inmigrantes_vida", "emigrantes_internos_vida", "saldo_migratorio_vida",
    "entran_a_trabajar", "salen_a_trabajar", "poblacion_flotante",
    "trabajan_en_su_municipio")})
# ⚠️ Los que el default "%" clasificaba MAL (2026-08-15). El resto de lo que el
#    catálogo no declara sí son porcentajes, así que el default les sirve; éstos
#    no: `hogares` es un conteo y salía informado como "+17.514,1 pp".
_cat.update({"hogares": "viv", "tam_hogar_pers": "pers/hogar",
             "paridez_media_12mas": "hijos",
             "brecha_anios_estudio_hom": "años", "brecha_anios_estudio_muj": "años"})

_sin_unidad = set()


def unidad_de(k):
    """(unidad_del_cambio, es_conteo) para un indicador."""
    # ⚠️ EL DEFAULT NO PUEDE SER SILENCIOSO: suponer "%" para lo que el catálogo
    #    no declara es lo que hizo que un conteo se informara en pp dos veces
    #    (población primero, hogares después). Sigue siendo "%" porque es lo que
    #    acierta en la gran mayoría, pero ahora se avisa al cerrar el armado.
    if k not in _cat:
        _sin_unidad.add(k)
    u = _cat.get(k, "%")
    if u in UNI_CONTEO:
        return "%", True
    if u in UNI_PCT:
        return "pp", False
    return u, False           # años, hijos, índice, ‰… cambian en su unidad

# `flujos_municipal` sólo existe en 2024 (ver el encabezado de motor_flujos.py):
# `cargar` avisa y sigue cuando falta el archivo de un año.
FUENTES = ["municipal", "personas", "nbi", "otros", "flujos_municipal"]

def cargar(anio):
    """Une las cuatro salidas del año: vivienda, personas, NBI (del tabulado) y
    emigración/mortalidad. Cada una llega ya a nivel municipio."""
    partes = []
    for f in FUENTES:
        ruta = AQUI / f"{f}_{anio}.csv"
        if not ruta.exists():
            print(f"  (falta {ruta.name})"); continue
        d = pd.read_csv(ruta, index_col=0, dtype={0: str})
        d.index = d.index.astype(str).str.zfill(6)
        d = d.drop(columns=[c for c in d.columns if c.startswith("_den_")])
        # ⚠️ Los motores emiten su propio vocabulario (`poblacion`,
        #    `pct_catocu_asalariado`) y este armado —como el catálogo— habla el
        #    del catálogo (`pob_total`, `pct_asalariados`). Sin esta traducción
        #    el armado se cae con KeyError sobre `pob_total`, y los indicadores
        #    con alias entraban al tablero con dos nombres distintos.
        partes.append(renombrar(d))
    # `viviendas` y `n_viviendas` son lo mismo; se conserva uno
    d = partes[0].rename(columns={"n_viviendas": "viviendas"})
    for otra in partes[1:]:
        nuevas = [c for c in otra.columns if c not in d.columns]
        d = d.join(otra[nuevas], how="outer")
    return d

def derivar(d):
    """Indicadores que no salen de un motor sino de combinar otros. Se calculan
    acá, con la misma fórmula en los dos censos, para que la serie sea legítima."""
    def tomar(*claves):
        """primer nombre disponible (el vocabulario puede venir con alias)"""
        for k in claves:
            if k in d.columns:
                return d[k]
        return pd.Series(np.nan, index=d.index)
    # Índice de carencia de servicios, 0-100: promedio simple de cinco
    # privaciones. Simple a propósito — un índice ponderado exige justificar los
    # pesos y acá no hay base para hacerlo.
    d["idx_carencia"] = pd.concat([
        100 - tomar("pct_agua_caneria"),
        100 - tomar("pct_alcantarillado", "pct_saneamiento_mejorado"),
        100 - tomar("pct_electricidad"),
        100 - tomar("pct_basura_formal"),
        tomar("pct_lena_guano"),
    ], axis=1).mean(axis=1)
    # Índice de calidad de la vivienda, 0-100: materiales + espacio
    d["idx_calidad_vivienda"] = pd.concat([
        tomar("pct_pared_ladrillo"),
        tomar("pct_revoque"),
        100 - tomar("pct_piso_tierra"),
        100 - tomar("pct_hacinamiento"),
        100 - tomar("pct_techo_paja"),
    ], axis=1).mean(axis=1)
    return d


d24, d12 = derivar(cargar(2024)), derivar(cargar(2012))
comunes = [c for c in d24.columns if c in d12.columns]
print(f"indicadores calculados en los dos censos: {len(comunes)}")
print(f"sólo 2024: {sorted(set(d24.columns) - set(d12.columns))}")

muns = json.loads((SCZ / "datos" / "municipios.json").read_text(encoding="utf-8"))
metro = {m["cod_ine"]: m for m in muns}
sp = {r["cod_ine"]: r for r in csv.DictReader(open(SPINE, encoding="utf-8"))}

filas = []
for ci, m in metro.items():
    for k in comunes:
        a, b = d12.at[ci, k] if ci in d12.index else np.nan, d24.at[ci, k] if ci in d24.index else np.nan
        if not (np.isfinite(a) or np.isfinite(b)):
            continue
        unidad, es_conteo = unidad_de(k)
        if es_conteo:
            cambio = 100 * (b / a - 1) if (a and np.isfinite(a) and np.isfinite(b)) else np.nan
            anual = 100 * ((b / a) ** (1 / ANIOS) - 1) if (a and np.isfinite(a) and np.isfinite(b)) else np.nan
        else:
            cambio = b - a if (np.isfinite(a) and np.isfinite(b)) else np.nan
            anual = np.nan
        filas.append(dict(cod_ine=ci, municipio=m["nombre"], ambito=m["ambito"],
                          indicador=k, v2012=a, v2024=b,
                          cambio=cambio, unidad_cambio=unidad, cambio_anual=anual))
    # `crec_intercensal` es la tasa ANUAL de la población: se guarda como
    # indicador propio para que el tablero no tenga que derivarla.
    a, b = (d12.at[ci, "pob_total"] if ci in d12.index else np.nan,
            d24.at[ci, "pob_total"] if ci in d24.index else np.nan)
    if a and np.isfinite(a) and np.isfinite(b):
        tasa = 100 * ((b / a) ** (1 / ANIOS) - 1)
        filas.append(dict(cod_ine=ci, municipio=m["nombre"], ambito=m["ambito"],
                          indicador="crec_intercensal", v2012=np.nan, v2024=tasa,
                          cambio=np.nan, unidad_cambio="%", cambio_anual=tasa))

df = pd.DataFrame(filas)
df.to_csv(AQUI / "metro_2012_2024.csv", index=False, encoding="utf-8")

# JSON compacto para la web: {cod_ine: {indicador: [v2012, v2024, cambio]}}
compacto = {}
for ci, g in df.groupby("cod_ine"):
    compacto[ci] = {r.indicador: [None if pd.isna(r.v2012) else round(r.v2012, 3),
                                  None if pd.isna(r.v2024) else round(r.v2024, 3),
                                  None if pd.isna(r.cambio) else round(r.cambio, 3)]
                    for r in g.itertuples()}
(AQUI / "metro_2012_2024.json").write_text(
    json.dumps({"anios": [2012, 2024], "municipios": compacto}, ensure_ascii=False),
    encoding="utf-8")

print(f"\n{len(df):,} filas municipio×indicador · {df.indicador.nunique()} indicadores × {df.cod_ine.nunique()} municipios")
print(f"→ metro_2012_2024.csv · metro_2012_2024.json")

print("\nLOS CAMBIOS MÁS GRANDES DE LA REGIÓN (2012 → 2024)")
print("=" * 84)
pct = df[df.unidad_cambio == "pp"].copy()
med = (pct.groupby("indicador")
          .agg(cambio_medio=("cambio", "mean"), v12=("v2012", "mean"), v24=("v2024", "mean"))
          .dropna().sort_values("cambio_medio"))
print(f"{'indicador':<32}{'2012':>10}{'2024':>10}{'cambio':>12}")
for k, r in pd.concat([med.head(8), med.tail(8)]).iterrows():
    print(f"{k:<32}{r.v12:>9.1f}{r.v24:>10.1f}{r.cambio_medio:>+11.1f} pp")

if _sin_unidad:
    print(f"\n⚠ {len(_sin_unidad)} indicadores sin unidad declarada en el catálogo "
          f"(se les supuso '%'): {', '.join(sorted(_sin_unidad))}")
