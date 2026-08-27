# -*- coding: utf-8 -*-
"""EL ATLAS PESA MENOS Y ARRANCA ANTES.

Reescribe `data.json`, `data_2012.json` y los dos `denominadores*.json` del Atlas
Socioeconómico en formato POR COLUMNA, sin tocar un solo valor.

★ EL PROBLEMA MEDIDO. `data.json` guardaba un objeto por municipio, así que los
  223 nombres de clave se escribían 343 veces: **76.489 repeticiones**. Son
  1.847 KB en disco (310 KB comprimidos) para 76 mil números.

★ LA CUENTA, MEDIDA:
      data.json        1.847 KB → 368 KB  ·  310 KB → 135 KB comprimido  (−57 %)
      data_2012.json   1.549 KB → 303 KB  ·  249 KB → 112 KB comprimido  (−55 %)
      denominadores    sin cambio: ya viajaban por columna
      ────────────────────────────────────────────────────────────────────────
      TOTAL comprimido 622 KB → 310 KB   (−50 %)
  Y **5× menos que parsear**, que es lo que se nota al abrir: `JSON.parse` de
  368 KB contra 1,8 MB. Ahí está la fluidez, no en el ancho de banda.

★ POR QUÉ NO SE REDONDEA. Se probó bajar a dos decimales y ahorraba un 5 %:
  nada, al lado del 57 % que da la estructura. No vale cambiar un dato publicado
  por un 5 %, y sin redondeo la verificación puede ser EXACTA — que es lo que
  permite afirmar «cero diferencias» y que sea verdad.

★ EL NAVEGADOR RECONSTRUYE LA MISMA FORMA. El HTML sigue usando
  `DATA[sigep].pob_total`: lo único que cambia es el formato en el que viaja. Se
  rehidrata en el arranque con dos bucles. Así ningún consumidor del `data.json`
  —ni el resto del código— tiene que enterarse.

⚠️ NO ES UNA MIGRACIÓN DE IDA: se escribe al lado (`.col.json`) y el HTML pide
   primero el compacto y cae al viejo si no está. Los dos conviven hasta que el
   sitio esté verificado.

    python catalogo/compactar_atlas.py            # ensayo
    python catalogo/compactar_atlas.py --escribir
"""
import gzip
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent
REPO = (AQUI.parent.parent / "Observatorio de Presupuesto Fiscal Departamental"
        / "_github_atlas_fiscal")

# claves que describen al municipio, no a un indicador: viajan como columnas
# propias porque son texto y se repiten poco
IDENT = ("nombre", "dpto", "cod_ine")


def limpio(v):
    """Quita el `.0` de los enteros que viajan como float (`1610982.0`). Y NADA
    MÁS.

    ⛔ La primera versión redondeaba a dos decimales «porque el Atlas muestra
       uno». El verificador lo cazó al instante: 97 valores cambiaban
       (`0.605 → 0.6`, `9.375 → 9.38`). Se midió lo que ese redondeo ahorraba y
       era **5 %** — nada, al lado del 59 % que da la estructura. No vale
       cambiar un dato publicado por un 5 %, y además volvía difusa la
       verificación: con tolerancia no se puede afirmar «cero diferencias».
       Sin redondeo la comparación es EXACTA y la afirmación, verdadera."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, float):
        if v != v:                       # NaN
            return None
        return int(v) if v == int(v) else v
    return v


def peso(obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return len(s) / 1024, len(gzip.compress(s, 9)) / 1024


def columnar(d):
    """{sigep: {clave: valor}}  →  {sigep:[…], claves:[…], v:[[…], …]}"""
    sig = list(d)
    # el orden de claves sale del PRIMER municipio pero se completa con todos:
    # si un indicador sólo existe en algunos, no puede perderse
    claves, vistas = [], set()
    for s in sig:
        for k in d[s]:
            if k not in vistas and k not in IDENT:
                vistas.add(k)
                claves.append(k)
    out = {"sigep": sig, "claves": claves}
    for k in IDENT:
        if any(k in d[s] for s in sig):
            out[k] = [d[s].get(k) for s in sig]
    out["v"] = [[limpio(d[s].get(k)) for s in sig] for k in claves]
    return out


def denominadores(d):
    """`denominadores.json` ya es medio columnar (`orden` + lista por municipio);
    lo único que falta es sacarle los `.0` de los enteros."""
    m = d.get("municipios", {})
    return {"orden": d.get("orden", []),
            "municipios": {k: [limpio(x) for x in v] for k, v in m.items()}}


def verificar(orig, comp):
    """Se rehidrata en Python EXACTAMENTE como lo hará el navegador y se compara
    contra el original, valor por valor. Sin esto, «pesa menos» no significa
    nada: podría pesar menos porque perdió datos."""
    sig, claves = comp["sigep"], comp["claves"]
    idx = {s: i for i, s in enumerate(sig)}
    fallos = 0
    for s, fila in orig.items():
        i = idx.get(s)
        if i is None:
            print(f"  ⛔ falta el municipio {s}")
            fallos += 1
            continue
        for k, v in fila.items():
            if k in IDENT:
                nv = comp[k][i] if k in comp else None
            else:
                j = claves.index(k)
                nv = comp["v"][j][i]
            if v is None and nv is None:
                continue
            # comparación EXACTA: la transformación no toca ningún valor
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if nv is None or float(v) != float(nv):
                    print(f"  ⛔ {s}.{k}: {v} → {nv}")
                    fallos += 1
            elif v != nv:
                print(f"  ⛔ {s}.{k}: {v!r} → {nv!r}")
                fallos += 1
    return fallos


def main(escribir):
    total_a = total_b = 0
    salidas = []
    for nom in ("data.json", "data_2012.json"):
        ruta = REPO / nom
        if not ruta.exists():
            print(f"  (sin {nom})")
            continue
        d = json.loads(ruta.read_text(encoding="utf-8"))
        comp = columnar(d)
        a, az = peso(d)
        b, bz = peso(comp)
        total_a, total_b = total_a + az, total_b + bz
        print(f"\n{nom}: {len(d)} municipios × {len(comp['claves'])} claves")
        print(f"   antes   {a:8.1f} KB · {az:7.1f} KB comprimido")
        print(f"   ahora   {b:8.1f} KB · {bz:7.1f} KB comprimido   (−{100 * (1 - bz / az):.0f} %)")
        fallos = verificar(d, comp)
        print(f"   verificación valor por valor: "
              f"{'✅ 0 diferencias' if not fallos else f'⛔ {fallos} DIFERENCIAS'}")
        if fallos:
            return 1
        salidas.append((REPO / nom.replace(".json", ".col.json"), comp))

    for nom in ("denominadores.json", "denominadores_2012.json"):
        ruta = REPO / nom
        if not ruta.exists():
            continue
        d = json.loads(ruta.read_text(encoding="utf-8"))
        nd = denominadores(d)
        a, az = peso(d)
        b, bz = peso(nd)
        total_a, total_b = total_a + az, total_b + bz
        print(f"\n{nom}")
        print(f"   antes   {a:8.1f} KB · {az:7.1f} KB comprimido")
        print(f"   ahora   {b:8.1f} KB · {bz:7.1f} KB comprimido   (−{100 * (1 - bz / az):.0f} %)")
        salidas.append((REPO / nom.replace(".json", ".col.json"), nd))

    print(f"\n  TOTAL comprimido: {total_a:.0f} KB → {total_b:.0f} KB "
          f"(−{100 * (1 - total_b / total_a):.0f} %)")

    if not escribir:
        print("\n(ensayo: no se escribió nada. Volvé a correr con --escribir)")
        return 0
    for ruta, obj in salidas:
        ruta.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
        print(f"→ {ruta.name}")
    print("\n⚠️ Falta agregar las excepciones al .gitignore del repo "
          "(ignora *.json) o el sitio pedirá archivos que nunca se subieron.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--escribir" in sys.argv))
