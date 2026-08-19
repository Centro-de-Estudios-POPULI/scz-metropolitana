# -*- coding: utf-8 -*-
"""
RE-EMPAQUETA EL NIVEL MANZANA DESDE EL MOTOR VALIDADO.
=======================================================

`empaquetar_web.py` toma los datos de `datos/manzanas_*.geojson`, que salen del
pipeline VIEJO (`derivar_indicadores.py`): 52 indicadores con vocabulario propio,
sin contraste contra el microdato. El motor nuevo (`catalogo/motor_manzana.py`)
produce **63 indicadores con los MISMOS nombres canónicos que el motor
municipal**, que es lo que permite que el toggle municipio↔manzana conserve el
indicador en vez de cambiar de objeto.

★ NO SE VUELVE A TOCAR LA GEOMETRÍA. Ya está simplificada (1,5 m sobre UTM 20S),
  redondeada a 5 decimales y con los polígonos inválidos reparados —466k→186k
  vértices, área −0,23%, 0 geometrías inválidas—. Este script sólo reescribe los
  ARREGLOS DE DATOS de `dat_<muni>.json`, alineados a la lista de `codigo` que ya
  vive en ese archivo. Así el re-empaquetado es barato y no arriesga la
  geometría, que fue lo caro de producir.

⚠️ El orden importa: los datos viajan en columnas alineadas POR POSICIÓN con la
   geometría. Si se reordenaran, cada manzana quedaría pintada con el valor de
   otra sin que nada falle.

    python scripts/reempaquetar_manzana.py
"""
import json, pathlib, sys
import pandas as pd

RAIZ = pathlib.Path(__file__).resolve().parent.parent
# Columnas que NO salen de la ficha del geoportal sino de `poblacion.parquet` y
# de la geometría: existen para todos los manzanos, tengan ficha o no.
SIN_FICHA = {"pob_total", "viviendas", "tam_hogar", "densidad"}
SALIDA = RAIZ / "web" / "datos"
MOTOR = RAIZ / "catalogo" / "manzana_2024.csv"
sys.path.insert(0, str(RAIZ / "catalogo"))


def main():
    from alias import ALIAS
    mz = pd.read_csv(MOTOR, dtype={"codigo": str}).set_index("codigo")
    # ⚠️ El motor de manzana emite SU vocabulario (`pct_salud_tradic`) y el
    #    catálogo declara otro (`pct_salud_tradicional`). Sin traducir, la
    #    intersección con la lista de comparables pierde indicadores en silencio:
    #    daba 50 en vez de los que son.
    mz.columns = [ALIAS.get(c, c) for c in mz.columns]
    inds = [c for c in mz.columns if c != "codigo"]
    print(f"motor de manzana: {len(mz):,} manzanas · {len(inds)} indicadores canónicos")

    comp = json.loads((RAIZ / "catalogo" / "comparables.json").read_text(encoding="utf-8"))
    # `verificados` = los que además REPRODUCEN la cifra urbana del microdato.
    # Quedan fuera los que sólo comparten el nombre: el bloque de salud, donde el
    # municipal divide por toda la población y admite respuesta múltiple.
    # ★ ENTRAN LOS VERIFICADOS **Y** LOS SÓLO-MANZANA. Estos últimos no tienen
    #   contraparte municipal contra la cual verificarse —la ficha separa cosas
    #   que el microdato no— pero son la mitad del valor de este nivel, y el
    #   catálogo los rotula para que se lea que al subir de nivel no están.
    admitidos = set(comp["verificados"]) | set(comp.get("solo_manzana", []))
    quedan = [k for k in inds if k in admitidos]
    print(f"de ésos, admitidos en el tablero: {len(quedan)} "
          f"({len(set(comp['verificados']) & set(inds))} verificados + "
          f"{len(set(comp.get('solo_manzana', [])) & set(inds))} sólo manzana)")

    tot_antes = tot_desp = 0
    for p in sorted(SALIDA.glob("dat_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        # sólo los archivos POR MUNICIPIO: el patrón también agarraría cualquier
        # otro `dat_*.json` que viva en la carpeta, y ésos tienen otra forma
        if "codigo" not in d:
            continue
        antes = p.stat().st_size
        codigos = [str(c) for c in d["codigo"]]
        sub = mz.reindex(codigos)          # ALINEADO a la geometría, no reordenado
        cols = {}
        for k in quedan:
            s = sub[k]
            cols[k] = [None if pd.isna(v) else (int(v) if float(v) == int(v) else round(float(v), 1))
                       for v in s]
        # ⚠️ `ficha` NO puede medirse sobre TODAS las columnas desde que entraron
        #    población y densidad: ésas vienen de `poblacion.parquet` y existen
        #    para los 247.429 manzanos, incluidos los 13.194 de la región que el
        #    INE suprime por privacidad. Medido sobre todo, las 38.892 darían
        #    "con ficha" y se perdería la distinción que el mapa usa para pintar
        #    en gris — y con ella el 34% de las manzanas dejaría de estar
        #    explicado. Se mide sobre las columnas que SALEN de la ficha.
        de_ficha = [k for k in quedan if k not in SIN_FICHA]
        con = int(sub[de_ficha].notna().any(axis=1).sum())
        d["cols"] = cols
        d["ficha"] = [bool(x) for x in sub[de_ficha].notna().any(axis=1)]
        p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
        desp = p.stat().st_size
        tot_antes += antes; tot_desp += desp
        print(f"  {p.stem[4:]:<26}{d['n']:>7,} manzanas · {con:>7,} con ficha "
              f"· {antes/1e6:>5.1f} → {desp/1e6:>5.1f} MB")
    print(f"\ntotal: {tot_antes/1e6:.1f} → {tot_desp/1e6:.1f} MB · {len(quedan)} indicadores")


if __name__ == "__main__":
    main()
