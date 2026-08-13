# -*- coding: utf-8 -*-
"""
MOTOR DE MANZANA — el tercer nivel del Tablero 2.
==================================================

A diferencia de los otros dos motores, éste NO sale del microdato y no puede:
el microdato llega hasta municipio y no trae identificador de manzano (es una
restricción de anonimización del INE). Las fichas por manzana vienen ya
agregadas del geoportal, vía `mauforonda/atlasurbano`.

Lo que hace este archivo es traducir esas fichas a los MISMOS nombres canónicos
que `motor.py`, para que el indicador sea el mismo objeto en los tres niveles:

    municipio  ·  municipio urbano  ·  manzana

La ficha trae CONTEOS por categoría, así que cada indicador es
`categoría / suma de las categorías de esa pregunta` — cada pregunta lleva su
propio denominador, que es como se forman los porcentajes en el origen.

★ CONTROL DE CALIDAD: al final se agregan las manzanas por municipio y se
  contrastan contra `municipal_urbano_2024.csv`, que sale del microdato. Son dos
  fuentes independientes del INE; si coinciden, la traducción es correcta. No se
  espera identidad exacta —"área urbana censada" y `urbrur=urbana` no son
  exactamente el mismo polígono— sino diferencias del orden de 1 pp.
"""
import pathlib, unicodedata, csv, re
import pandas as pd, numpy as np

AQUI = pathlib.Path(__file__).parent
FUENTE = AQUI.parent / "fuente"
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace("-", " ").split())

# indicador canónico -> (prefijo de la pregunta en la ficha, sufijos que suman)
# El denominador de cada uno es la suma de TODAS las columnas de su prefijo.
IND = {
 "pct_agua_caneria":       ("agua_",   ["cañería"]),
 "pct_agua_pileta":        ("agua_",   ["piletapública"]),
 "pct_agua_pozo":          ("agua_",   ["pozoconbomba", "pozosinbomba"]),
 "pct_agua_pozo_bomba":    ("agua_",   ["pozoconbomba"]),
 "pct_agua_carro":         ("agua_",   ["carrorepartidor"]),
 "pct_alcantarillado":     ("desague_", ["alcantarillado"]),
 "pct_camara_septica":     ("desague_", ["camaraséptica"]),
 "pct_pozo_ciego":         ("desague_", ["pozociego"]),
 "pct_desague_superficie": ("desague_", ["superficie"]),
 "pct_sin_desague":        ("desague_", ["notiene"]),
 "pct_electricidad":       ("energiaelectrica_", ["serviciopublico", "motorpropio",
                                                  "panelsolar", "otra"]),
 "pct_elec_red":           ("energiaelectrica_", ["serviciopublico"]),
 "pct_panel_solar":        ("energiaelectrica_", ["panelsolar"]),
 "pct_sin_energia":        ("energiaelectrica_", ["notiene"]),
 "pct_gas_garrafa":        ("combustible_", ["gasgarrafa"]),
 "pct_gas_red":            ("combustible_", ["gascañería"]),
 "pct_lena_guano":         ("combustible_", ["leña", "guano"]),
 "pct_basura_formal":      ("basura_",  ["basureropúblico", "carrobasurero"]),
 "pct_basura_carro":       ("basura_",  ["carrobasurero"]),
 "pct_basura_quema":       ("basura_",  ["quema"]),
 "pct_basura_entierra":    ("basura_",  ["entierra"]),
 "pct_basura_informal":    ("basura_",  ["calle", "río"]),
 "pct_viv_propia":         ("viviendatenencia_", ["propia"]),
 "pct_viv_alquilada":      ("viviendatenencia_", ["alquilada"]),
 "pct_viv_anticretico":    ("viviendatenencia_", ["anticretico"]),
 "pct_viv_prestada":       ("viviendatenencia_", ["prestada"]),
 "pct_pared_ladrillo":     ("material_paredes_", ["ladrillo"]),
 "pct_pared_adobe":        ("material_paredes_", ["adobe"]),
 "pct_pared_madera":       ("material_paredes_", ["madera"]),
 "pct_revoque":            ("material_revoque_", ["con"]),
 "pct_techo_calamina":     ("material_techo_", ["calamina"]),
 "pct_techo_teja":         ("material_techo_", ["teja"]),
 "pct_techo_losa":         ("material_techo_", ["losa"]),
 "pct_techo_paja":         ("material_techo_", ["paja"]),
 "pct_piso_tierra":        ("material_piso_", ["tierra"]),
 "pct_piso_cemento":       ("material_piso_", ["cemento"]),
 "pct_piso_ceramica":      ("material_piso_", ["ceramica", "mosaico"]),
 "pct_hogar_unipersonal":  ("hogar_",   ["unipersonal"]),
 "pct_hogar_extendido":    ("hogar_",   ["extendido"]),
 "pct_hogar_monoparental": ("hogar_",   ["monoparental"]),
 "pct_radio":              ("tics_",    ["radio"]),
 "pct_televisor":          ("tics_",    ["televisor"]),
 "pct_internet":           ("tics_",    ["internet"]),
 "pct_celular":            ("tics_",    ["celular"]),
 # personas: la ficha trae todo partido por sexo, así que el denominador es la
 # suma de las dos mitades
 "pct_menor20":            ("edad_",    ["0a19_hombre", "0a19_mujer"]),
 "pct_60_mas":             ("edad_",    ["60omas_hombre", "60omas_mujer"]),
 "pct_edu_superior":       ("educacion_", ["superior_hombre", "superior_mujer"]),
 "pct_edu_ninguno":        ("educacion_", ["ninguno_hombre", "ninguno_mujer"]),
 "pct_salud_publica":      ("salud_",   ["centropublico_hombre", "centropublico_mujer"]),
 "pct_salud_privada":      ("salud_",   ["centroprivado_hombre", "centroprivado_mujer"]),
 "pct_salud_tradic":       ("salud_",   ["medicinatradicional_hombre", "medicinatradicional_mujer"]),
 "pct_sin_seguro":         ("saludafiliacion_", ["ninguno_hombre", "ninguno_mujer"]),
 "pct_sus":                ("saludafiliacion_", ["sus_hombre", "sus_mujer"]),
 "pct_nacido_otro_municipio": ("nacimiento_", ["otromunicipio_hombre", "otromunicipio_mujer"]),
 "pct_nacido_extranjero":  ("nacimiento_", ["otropais_hombre", "otropais_mujer"]),
 "pct_catocu_asalariado":  ("ocupacion_", ["empleado_hombre", "empleado_mujer"]),
 "pct_catocu_cuenta_propia": ("ocupacion_", ["cuentapropia_hombre", "cuentapropia_mujer"]),
 "pct_rama_agricultura":   ("actividad_", ["agricultura_hombre", "agricultura_mujer"]),
 "pct_rama_comercio":      ("actividad_", ["comercio_hombre", "comercio_mujer"]),
 "pct_rama_manufactura":   ("actividad_", ["manufactura_hombre", "manufactura_mujer"]),
 "pct_rama_construccion":  ("actividad_", ["construccion_hombre", "construccion_mujer"]),
 "pct_rama_transporte":    ("actividad_", ["transporte_hombre", "transporte_mujer"]),
 "pct_rama_alojamiento":   ("actividad_", ["alojamientoycomida_hombre", "alojamientoycomida_mujer"]),
}
# las preguntas cuyo "sin especificar" NO debe entrar al denominador
SIN_ESP = ("sinespecificar",)

# ★ DENOMINADOR ESPECIAL. La regla general —sumar todas las categorías del
#   prefijo— sirve para las preguntas de opción única (agua, techo, tenencia…),
#   pero NO para las de sí/no independientes: `tics_radio`, `tics_televisor`,
#   `tics_celular` e `tics_internet` son CUATRO preguntas distintas, no cuatro
#   categorías de una. Sumarlas daba denominadores absurdos y errores de 40 a 50
#   pp contra el microdato. Su denominador es el total de viviendas del manzano.
DEN_PROPIO = {"tics_": ["viviendatipo_personaspresentes"]}


def calcular_manzana():
    f = pd.read_parquet(FUENTE / "fichas.parquet")
    cols = list(f.columns)
    out = pd.DataFrame({"codigo": f.codigo})
    faltan = []
    for k, (pref, sufijos) in IND.items():
        grupo = [c for c in cols if c.startswith(pref) and not any(s in c for s in SIN_ESP)]
        num_cols = [c for c in grupo if any(c == pref + s for s in sufijos)]
        if not num_cols:
            faltan.append((k, pref, [c[len(pref):] for c in grupo][:8])); continue
        den = f[DEN_PROPIO[pref]].sum(axis=1) if pref in DEN_PROPIO else f[grupo].sum(axis=1)
        out[k] = 100 * f[num_cols].sum(axis=1) / den.replace(0, np.nan)
    if faltan:
        print("⚠️ sin columna en la ficha:")
        for k, pref, hay in faltan:
            print(f"   {k:<28} prefijo {pref!r} — hay: {hay}")
    return out, [k for k in IND if k in out.columns]


if __name__ == "__main__":
    mz, listos = calcular_manzana()
    print(f"\n{len(mz):,} manzanas · {len(listos)} indicadores canónicos")

    # ── control: agregar por municipio y contrastar con el microdato urbano ──
    geo = pd.read_parquet(FUENTE / "manzanos.parquet", columns=["codigo", "departamento", "municipio"])
    sp = list(csv.DictReader(open(SPINE, encoding="utf-8")))
    clave = {}
    for r in sp:
        for nm in {norm(r["nombre_censo"]), norm(r["nombre"])}:
            clave[(norm(r["dpto"]), nm)] = r["cod_ine"]
    geo["cod_ine"] = [clave.get((norm(d), norm(m))) for d, m in
                      zip(geo.departamento, geo.municipio)]
    print(f"manzanos con municipio identificado: {geo.cod_ine.notna().mean():.1%}")

    f = pd.read_parquet(FUENTE / "fichas.parquet")
    d = f.merge(geo[["codigo", "cod_ine"]], on="codigo", how="left")
    agr = {}
    cols = list(f.columns)
    for k, (pref, sufijos) in IND.items():
        grupo = [c for c in cols if c.startswith(pref) and not any(s in c for s in SIN_ESP)]
        num_cols = [c for c in grupo if any(c == pref + s for s in sufijos)]
        if not num_cols: continue
        g = d.groupby("cod_ine")
        dcols = DEN_PROPIO[pref] if pref in DEN_PROPIO else grupo
        agr[k] = 100 * g[num_cols].sum().sum(axis=1) / g[dcols].sum().sum(axis=1)
    agr = pd.DataFrame(agr)
    agr.to_csv(AQUI / "manzana_agregado_municipal.csv", encoding="utf-8")
    mz.to_csv(AQUI / "manzana_2024.csv", index=False, encoding="utf-8")

    urb = pd.read_csv(AQUI / "municipal_urbano_2024.csv", index_col=0, dtype={0: str})
    urb.index = urb.index.astype(str).str.zfill(6)
    comunes = [c for c in agr.columns if c in urb.columns]
    print(f"\nCONTRASTE contra el microdato urbano — {len(comunes)} indicadores comparables")
    print(f"{'indicador':<30}{'|dif| media':>13}{'mediana':>10}{'máx':>10}")
    filas = []
    for c in comunes:
        dif = (agr[c] - urb[c]).abs().dropna()
        if len(dif) < 50: continue
        filas.append((c, dif.mean(), dif.median(), dif.max()))
    filas.sort(key=lambda x: x[1])
    for c, m, md, mx in filas:
        print(f"{c:<30}{m:>12.2f}{md:>10.2f}{mx:>10.2f}")
    tot = np.mean([x[1] for x in filas])
    print(f"\nerror absoluto medio global: {tot:.2f} pp  ·  {len(filas)} indicadores")
    print("→ manzana_2024.csv · manzana_agregado_municipal.csv")
