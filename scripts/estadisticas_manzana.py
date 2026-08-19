# -*- coding: utf-8 -*-
"""
ESTADÍSTICAS DEL NIVEL MANZANA — el precio de pasar a teselas.
===============================================================

Con los `dat_*.json` en memoria, el navegador tenía TODOS los valores y podía
calcular la escala del mapa y el percentil de una manzana sobre la marcha. Con
PMTiles sólo ve las teselas del viewport, así que lo que antes se computaba hay
que **precalcularlo**: es exactamente lo mismo que hacía `escala()`, movido de
tiempo de ejecución a tiempo de armado.

Produce `web/datos/mz_stats.json` con dos bloques por indicador:

  `esc`  — lo que necesitaba `escala()` en el ámbito "manzana":
           q02/q98 (el dominio dibujado), pivote ponderado por personas,
           mín, máx, n, y una **rejilla de cuantiles** para que el tooltip
           siga pudiendo decir en qué percentil cae una manzana sin tener
           las 25.698 ordenadas al lado.

  `dist` — la distribución DENTRO de cada municipio (p10 · p25 · p50 · p75 ·
           p90 · n), que es lo que dibuja la tira nueva del panel derecho.

★ POR QUÉ LA TIRA: medido sobre estos mismos datos, en 36 de los 59 indicadores
  la desigualdad DENTRO de un municipio es mayor que todo el rango ENTRE los
  nueve. El comparativo de barras —que se queda— retrata la variación entre
  municipios; sin esto, la mayor de las dos no se ve en ninguna parte.
  El caso que lo resume: Santa Cruz de la Sierra tiene 63,9% de alcantarillado
  con el decil de abajo en 0% y el de arriba en 100%.

⚠️ El universo son las manzanas CON FICHA. Las 13.194 sin ficha no son ceros:
   el INE las suprime por privacidad. Meterlas como 0 inventaría un piso de
   carencia que no está en el dato.

    python scripts/estadisticas_manzana.py
"""
import json, pathlib

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATOS = RAIZ / "web" / "datos"
SALIDA = DATOS / "mz_stats.json"

# Rejilla de cuantiles para el percentil del tooltip: 51 cortes (cada 2%).
# Con 101 la precisión no mejora de forma perceptible y el archivo crece al doble.
CORTES = [i / 50 for i in range(51)]


def cuantil(ord_, q):
    """Idéntica a `cuantil()` del tablero: interpolación lineal entre vecinos."""
    if not ord_:
        return None
    h = (len(ord_) - 1) * q
    b = int(h)
    r = h - b
    return ord_[b] + r * (ord_[b + 1] - ord_[b]) if b + 1 < len(ord_) else ord_[b]


def r1(v):
    return None if v is None else round(v, 1)


def main():
    slugs = sorted(p.stem[4:] for p in DATOS.glob("geo_*.geojson"))
    D = {s: json.loads((DATOS / f"dat_{s}.json").read_text(encoding="utf-8"))
         for s in slugs}
    cat = json.loads((DATOS / "catalogo_manzana.json").read_text(encoding="utf-8"))
    orden = [i["key"] for g in cat["grupos"] for i in g["indicadores"]]
    # el sigep es lo que usa el panel para casar municipio con polígono
    mun = json.loads((DATOS / "municipios_manzana.json").read_text(encoding="utf-8"))
    sigep = {}
    for m in mun:
        s = (m["nombre"].lower().replace(" ", "_")
             .replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u"))
        sigep[s] = m["sigep"]
    faltan = [s for s in slugs if s not in sigep]
    if faltan:
        raise SystemExit(f"sin sigep para: {faltan}")

    out = {}
    for k in orden:
        todos, pesos = [], []
        dist = {}
        for s in slugs:
            col = D[s]["cols"].get(k)
            if not col:
                continue
            pers = D[s]["cols"].get("personas")
            v = []
            for i, x in enumerate(col):
                if x is None:
                    continue
                v.append(x)
                todos.append(x)
                pesos.append(pers[i] if pers and pers[i] is not None else 0)
            if len(v) >= 30:      # con menos, los deciles no dicen nada
                v.sort()
                dist[sigep[s]] = {
                    "n": len(v),
                    "p10": r1(cuantil(v, .10)), "p25": r1(cuantil(v, .25)),
                    "p50": r1(cuantil(v, .50)), "p75": r1(cuantil(v, .75)),
                    "p90": r1(cuantil(v, .90)),
                }
        if not todos:
            continue
        ordenados = sorted(todos)
        sw = sum(pesos)
        piv = (sum(x * w for x, w in zip(todos, pesos)) / sw if sw > 0
               else cuantil(ordenados, .5))
        out[k] = {
            "esc": {
                "lo": r1(cuantil(ordenados, .02)), "hi": r1(cuantil(ordenados, .98)),
                "piv": r1(piv), "tipo": "región" if sw > 0 else "mediana",
                "min": r1(ordenados[0]), "max": r1(ordenados[-1]),
                "n": len(ordenados),
                "q": [r1(cuantil(ordenados, c)) for c in CORTES],
            },
            "dist": dist,
        }

    SALIDA.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")),
                      encoding="utf-8")
    import gzip
    b = SALIDA.read_bytes()
    print(f"{SALIDA.name}: {len(out)} indicadores · "
          f"{len(b)/1024:.0f} KB ({len(gzip.compress(b,9))/1024:.0f} KB gzip)")
    n_dist = sum(len(v["dist"]) for v in out.values())
    print(f"  distribución en {n_dist} pares indicador×municipio")
    # el hallazgo que justifica la tira, recalculado acá para que no sea una
    # afirmación suelta en un informe: si deja de ser cierto, se ve al correr
    gana = 0
    for k, v in out.items():
        entre = [m["municipal"].get(k) for m in mun
                 if m.get("municipal", {}).get(k) is not None]
        if len(entre) < 8 or not v["dist"]:
            continue
        rango = max(entre) - min(entre)
        dentro = sorted(d["p90"] - d["p10"] for d in v["dist"].values())
        if cuantil(dentro, .5) > rango:
            gana += 1
    print(f"  en {gana} de {len(out)} indicadores la desigualdad DENTRO de un "
          f"municipio supera el rango ENTRE los nueve")


if __name__ == "__main__":
    main()
