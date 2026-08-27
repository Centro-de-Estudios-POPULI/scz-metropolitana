# -*- coding: utf-8 -*-
"""QUÉ INDICADORES VALE LA PENA CRUZAR CONTRA CUÁL.

El comparador del Atlas ofrecía los 215 indicadores contra cualquier otro: 23.005
pares, y la enorme mayoría no dice nada o dice una obviedad. Este script los mide
todos y deja, para cada indicador, una lista corta de cruces que sí se sostienen.

★ LO PRIMERO: LA SIGNIFICANCIA ESTADÍSTICA NO SIRVE DE FILTRO. Con n = 343
  municipios, |ρ| > 0,106 ya es p < 0,05 — o sea el 72 % de los pares. Decir
  «mostramos los significativos» sería no filtrar nada y encima sonar riguroso.
  Lo que hay que separar es lo INTERESANTE de lo TRIVIAL, y eso no es una prueba
  de hipótesis: es saber de dónde sale cada indicador.

★ LAS CUATRO FAMILIAS DE RELACIÓN FALSA — cada una DETECTADA sobre el dato, no
  enumerada a mano, que es lo que hace que la regla siga valiendo cuando entren
  indicadores nuevos:

  1. COMPLEMENTOS. `a + b = 100` en los 343 municipios ⇒ ρ = −1 por aritmética.
     Son 6 pares: «Con electricidad ↔ Sin energía eléctrica» y compañía.

  2. ANIDAMIENTOS. `a ≤ b` en todos los municipios y comparten universo ⇒ uno
     está DENTRO del otro. «Adultos mayores (65+) ↔ 60 años y más» (ρ +0,995),
     «Población 0–14 ↔ Menores de 20» (+0,976). Que suban juntos no es un
     hallazgo: es que los mismos individuos están contados dos veces.

  3. PORCIONES DE LA MISMA TORTA con signo negativo. Mismo universo y su suma
     nunca pasa de 100 ⇒ compiten por el mismo 100 %, así que la oposición es
     forzosa. ⚠️ Sólo se descarta la NEGATIVA: dos porciones que crecen JUNTAS
     pese a competir sí dicen algo.

  4. LA MISMA VARIABLE DICHA DOS VECES. Es lo que caza el techo de |ρ| < 0,95,
     y se eligió midiendo: TODOS los pares por encima de 0,963 resultaron ser
     definicionales — los componentes NBI contra el indicador del que se
     construyen («Piso de tierra ↔ NBI: Materiales» +0,983), las versiones
     femeninas («Analfabetismo ↔ Analfabetismo femenino» +0,985) y los conteos
     entre sí, que correlacionan porque los dos miden el TAMAÑO del municipio
     («Población total ↔ Viviendas» +0,977).

★ NO SE ESCONDE NADA. La lista corta es el atajo, no una reja: el desplegable
  conserva la opción de ver los 215. Filtrar no puede quitar capacidad.

    python catalogo/relaciones_atlas.py            # ensayo, con el informe
    python catalogo/relaciones_atlas.py --escribir
"""
import itertools
import json
import math
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
REPO = (AQUI.parent.parent / "Observatorio de Presupuesto Fiscal Departamental"
        / "_github_atlas_fiscal")

TECHO = 0.95      # por encima, es la misma variable dos veces
PISO = 0.30       # por debajo, la nube no muestra ninguna forma
CUANTOS = 12      # cuántos cruces se ofrecen por indicador
MIN_PARES = 100   # municipios en común para que el ρ signifique algo


def rangos(vals):
    """Rangos con empates promediados, que es lo que pide Spearman."""
    idx = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        med = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[idx[k]] = med
        i = j + 1
    return r


def spearman(xs, ys):
    n = len(xs)
    rx, ry = rangos(xs), rangos(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else None


def main(escribir):
    cat = json.loads((REPO / "catalogo.json").read_text(encoding="utf-8"))
    data = json.loads((REPO / "data.json").read_text(encoding="utf-8"))
    META = {i["key"]: (g["key"], g["label"], i)
            for g in cat["grupos"] for i in g["indicadores"]}
    sig = list(data)
    VAL = {k: {s: data[s][k] for s in sig if data[s].get(k) is not None} for k in META}
    keys = [k for k in META if len(VAL[k]) >= MIN_PARES]
    print(f"  {len(keys)} indicadores · {len(sig)} municipios · "
          f"{len(keys) * (len(keys) - 1) // 2} pares por medir")

    # ── el ρ de cada par, sobre su universo COMÚN ────────────────────────────
    # Rangos por par y no una vez por indicador: dos indicadores con distinta
    # cobertura darían un ρ sesgado si se rankearan sobre poblaciones distintas.
    rho = {}
    for a, b in itertools.combinations(keys, 2):
        com = list(VAL[a].keys() & VAL[b].keys())
        if len(com) < MIN_PARES:
            continue
        r = spearman([VAL[a][s] for s in com], [VAL[b][s] for s in com])
        if r is not None:
            rho[(a, b)] = (r, len(com))
    print(f"  {len(rho)} pares con universo común suficiente")

    # ── las cuatro familias de relación falsa ───────────────────────────────
    def pct(k):
        return META[k][2].get("unit") == "%"

    def mismo_universo(a, b):
        da, db = META[a][2].get("den"), META[b][2].get("den")
        return da is not None and da == db

    def clasifica(a, b):
        va, vb = VAL[a], VAL[b]
        com = va.keys() & vb.keys()
        if len(com) < MIN_PARES:
            return None
        if pct(a) and pct(b):
            if all(abs(va[s] + vb[s] - 100) <= 0.6 for s in com):
                return "complemento"
            if mismo_universo(a, b):
                # ⚠️ el anidamiento se mide con holgura: los redondeos del
                # microdato hacen que un subconjunto supere a su conjunto por
                # centésimas en algún municipio suelto
                if all(va[s] <= vb[s] + 0.4 for s in com) or all(vb[s] <= va[s] + 0.4 for s in com):
                    return "anidado"
                if all(va[s] + vb[s] <= 100.8 for s in com):
                    return "porcion"
        return None

    fam = {p: clasifica(*p) for p in rho}
    from collections import Counter
    print("  familias detectadas:", dict(Counter(v for v in fam.values() if v)))

    def descartar(p):
        r = rho[p][0]
        if abs(r) >= TECHO:
            return "la misma variable dos veces"
        if fam[p] == "complemento":
            return "complemento aritmético"
        if fam[p] == "anidado":
            return "uno está dentro del otro"
        if fam[p] == "porcion" and r < 0:
            return "compiten por el mismo 100 %"
        return None

    fuera = {p: descartar(p) for p in rho}
    quedan = {p: rho[p] for p in rho if not fuera[p]}
    print(f"\n  descartados: {len(rho) - len(quedan)} · quedan {len(quedan)}")
    print("  ", dict(Counter(v for v in fuera.values() if v)))

    # ── la lista corta de cada indicador ────────────────────────────────────
    porInd = {}
    for (a, b), (r, n) in quedan.items():
        if abs(r) < PISO:
            continue
        porInd.setdefault(a, []).append((abs(r), r, b))
        porInd.setdefault(b, []).append((abs(r), r, a))
    rel = {}
    for k in META:
        lst = sorted(porInd.get(k, []), reverse=True)[:CUANTOS]
        rel[k] = [[o, round(r, 3)] for _, r, o in lst]

    n0 = sum(1 for k in rel if not rel[k])
    print(f"\n  cruces ofrecidos por indicador: "
          f"mediana {sorted(len(v) for v in rel.values())[len(rel) // 2]} · "
          f"sin ninguno {n0}")

    print("\n--- MUESTRA: qué se le va a ofrecer a cada uno ---")
    for k in ("pct_alcantarillado", "pct_nbi_pobre", "pob_total", "tasa_desocupacion"):
        if k not in rel:
            continue
        print(f"\n  {META[k][2]['label']}  [{META[k][1]}]")
        for o, r in rel[k][:6]:
            print(f"     {r:+.3f}  {META[o][2]['label'][:38]:<38} [{META[o][1][:16]}]")

    print("\n--- LOS QUE SE QUEDAN SIN CRUCES (y por qué está bien) ---")
    vacios = [k for k in rel if not rel[k]]
    for k in vacios[:12]:
        mejor = max((abs(rho[p][0]) for p in rho if k in p), default=0)
        print(f"   {META[k][2]['label'][:40]:<40} su cruce más fuerte útil no llega a {PISO}"
              f" (el mayor |ρ| bruto era {mejor:.2f})")

    if escribir:
        for g in cat["grupos"]:
            for i in g["indicadores"]:
                if rel.get(i["key"]):
                    i["rel"] = rel[i["key"]]
                else:
                    i.pop("rel", None)
        (REPO / "catalogo.json").write_text(
            json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ escrito {REPO / 'catalogo.json'}")
    else:
        print("\n(ensayo: no se escribió. Volvé a correr con --escribir)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--escribir" in sys.argv))
