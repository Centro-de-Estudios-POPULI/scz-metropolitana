# -*- coding: utf-8 -*-
"""
CHEQUEO — la puerta de sanidad que le faltaba al pipeline.
==========================================================

`validar.py` y `validar_persona.py` comparan contra los tabulados del INE, que
es la prueba fuerte; pero sólo cubren los ~58 indicadores que tienen hoja de
validación. Los otros ~170 no los miraba nadie.

Así sobrevivió el peor bug encontrado hasta ahora: `pct_idioma_castellano`
publicaba **0,00% en los 343 municipios** y `pct_idioma_materno_originario`
publicaba **100,00%**, porque la regla decía `idioma_mat == 1` y el código 1 es
*Araona* — el castellano es el 6. Eran 122 personas en todo el país. Ningún
validador lo tocaba y el número, mirado de reojo, no gritaba.

Este script no sabe cuál es la cifra correcta: sabe reconocer las formas que
tiene un indicador ROTO. Es barato, corre en segundos y se puede pasar después
de cada motor.

    python chequeo.py            # sale con código 1 si hay algún ERROR

Las dos categorías son distintas a propósito:
  · **ERROR** — la columna no puede ser cierta (constante, >100%, negativa,
    degenerada, o vacía en los dos censos: nadie la calcula nunca).
  · **AVISO** — la columna está vacía en UN censo. Suele ser correcto (el censo
    de 2012 no preguntaba por celular ni internet), pero se lista igual para que
    sea una decisión visible y no un accidente silencioso.
"""
import pathlib, sys, json
import pandas as pd, numpy as np

AQUI = pathlib.Path(__file__).parent

# ── techos por unidad: lo que es FÍSICAMENTE imposible ───────────────────────
# ⚠️ La regla de ">100%" sólo miraba porcentajes, así que no vio una edad media
#    de emigración de 660,8 años (los códigos de "no aplica" son números
#    grandes y entran al promedio). El catálogo ya declara la unidad de cada
#    indicador: se usa esa, en vez de una lista aparte que se desactualiza.
TECHO = {"%": 100, "años": 110, "hijos": 25, "‰": 1000, "índice": 100}

# ── razones, NO proporciones: pasar de 100 es legítimo ───────────────────────
# ⚠️ Una razón de dependencia de 100,4 dice que hay más personas dependientes
#    que en edad activa; un índice de envejecimiento de 101,8, que hay más
#    adultos mayores que niños. No son la parte de un total y no tienen techo en
#    100, aunque el catálogo los declare como "%" o "índice".
RAZONES = {"razon_dependencia", "dep_juvenil", "dep_senil",
           "indice_envejecimiento", "indice_masculinidad", "indice_juventud"}
try:
    UNIDAD = {i["k"]: i["u"] for i in
              json.loads((AQUI / "catalogo.json").read_text(encoding="utf-8"))["indicadores"]}
except FileNotFoundError:
    UNIDAD = {}
# los motores todavía nombran algunas cosas a su manera; el techo es por unidad
# y estas no están declaradas en el catálogo con ese nombre
UNIDAD.setdefault("edad_prom_emigracion", "años")
UNIDAD.setdefault("edad_prom_fallecimiento", "años")
UNIDAD.setdefault("edad_media_jefe", "años")
UNIDAD.setdefault("edad_1er_hijo", "años")
UNIDAD.setdefault("edad_mediana", "años")
UNIDAD.setdefault("edad_promedio", "años")

# los pares que tienen serie intercensal, para poder distinguir "este censo no
# lo preguntó" de "esto no lo calcula nadie"
PARES = [("municipal_2024", "municipal_2012"),
         ("municipal_urbano_2024", "municipal_urbano_2012"),
         ("personas_2024", "personas_2012"),
         ("nbi_2024", "nbi_2012"),
         ("otros_2024", "otros_2012")]
# el nivel manzana existe sólo en 2024: no tiene gemelo con qué contrastar
SUELTOS = ["manzana_agregado_municipal"]

# ── casos donde una distribución concentrada es la REALIDAD, no un bug ───────
# Un pueblo indígena chico vive en un puñado de municipios: su mediana nacional
# es 0 y eso es correcto. Se exceptúan por nombre para que la regla general siga
# siendo estricta con todo lo demás.
ESPERADO_CONCENTRADO = {
    "pct_pueblo_guarani", "pct_pueblo_chiquitano", "pct_pueblo_mojeno",
    "pct_pueblo_trinitario", "pct_pueblo_movima", "pct_pueblo_guarayo",
    "pct_pueblo_yuracare", "pct_pueblo_afroboliviano", "pct_pueblo_aymara",
    "pct_bote", "pct_panel_solar", "pct_agua_lluvia", "pct_agua_rio",
    "pct_gas_red", "pct_urbano", "pct_muertes_covid",
}


def leer(nombre):
    p = AQUI / f"{nombre}.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, index_col=0)


# en el recorte urbano `pct_urbano` vale 100 por construcción: es una identidad,
# no un indicador roto
TRIVIAL = {("municipal_urbano_2024", "pct_urbano"),
           ("municipal_urbano_2012", "pct_urbano")}


def diagnosticar(s, col):
    """Devuelve (severidad, motivo) o None si la columna se ve sana."""
    v = pd.to_numeric(s, errors="coerce")
    vivos = v.dropna()
    if len(vivos) == 0:
        return ("VACIO", "sin un solo valor")
    if vivos.nunique() == 1:
        return ("ERROR", f"constante en {vivos.iloc[0]:g}")
    es_pct = col.startswith("pct_") or col.startswith("tasa_")
    # techo por unidad declarada; los `pct_`/`tasa_` sin declarar van a 100
    techo = None if col in RAZONES else TECHO.get(UNIDAD.get(col, "%" if es_pct else None))
    if techo is not None:
        exceden = int((vivos > techo * 1.00001).sum())
        if exceden:
            return ("ERROR", f"{exceden} municipios por encima de {techo} "
                             f"{UNIDAD.get(col, '%')} (máximo {vivos.max():.1f})")
    if es_pct:
        if (vivos < -0.001).any():
            return ("ERROR", f"negativo (mínimo {vivos.min():.2f})")
        # ★ LA FORMA DEL BUG DE IDIOMA: casi sin dispersión y pegado a un
        #   extremo. Un porcentaje real varía entre municipios; uno que vale
        #   0,00 o 100,00 en todos lados es una regla mal escrita, no un dato.
        if col not in ESPERADO_CONCENTRADO:
            rango = vivos.quantile(.95) - vivos.quantile(.05)
            if rango < 0.05:
                return ("ERROR", f"degenerado: el 90% central cabe en {rango:.3f} pp "
                                 f"(mediana {vivos.median():.2f})")
    if vivos.isna().sum() == 0 and len(vivos) < len(v) * 0.5:
        return ("ERROR", f"sólo {len(vivos)} de {len(v)} municipios con dato")
    return None


def main():
    errores, avisos = [], []

    def revisar(nombre, df, gemelo=None):
        for col in df.columns:
            if col.startswith("_den_") or (nombre, col) in TRIVIAL:
                continue
            d = diagnosticar(df[col], col)
            if d is None:
                continue
            sev, motivo = d
            if sev == "VACIO":
                # vacía acá: ¿el otro censo la tiene? Si sí, es el patrón
                # legítimo "la pregunta no existe en este censo".
                if gemelo is not None and col in gemelo.columns \
                   and pd.to_numeric(gemelo[col], errors="coerce").notna().any():
                    avisos.append((nombre, col, "vacía en este censo, con dato en el otro"))
                else:
                    errores.append((nombre, col, "vacía en los DOS censos: no la calcula nadie"))
            else:
                errores.append((nombre, col, motivo))

    for a, b in PARES:
        da, db = leer(a), leer(b)
        if da is not None:
            revisar(a, da, db)
        if db is not None:
            revisar(b, db, da)
    for s in SUELTOS:
        d = leer(s)
        if d is not None:
            revisar(s, d)

    ancho = max([len(c) for _, c, _ in errores + avisos] + [20])
    if errores:
        print(f"\n  ERRORES ({len(errores)})")
        print("  " + "=" * (ancho + 60))
        for arch, col, motivo in errores:
            print(f"  {arch:<24}{col:<{ancho}}  {motivo}")
    if avisos:
        print(f"\n  AVISOS ({len(avisos)}) — un solo censo tiene la pregunta")
        print("  " + "=" * (ancho + 60))
        for arch, col, motivo in avisos:
            print(f"  {arch:<24}{col:<{ancho}}  {motivo}")
    if not errores:
        print(f"\n  sin errores · {len(avisos)} avisos")
    print()
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
