"""
Empaqueta las manzanas para la web SIN teselar.

El GeoJSON que sale del derivador pesa 78,9 MB porque repite, manzana por
manzana, el nombre de las 52 propiedades y guarda las coordenadas con 15
decimales. Las dos cosas son evitables:

  · GEOMETRÍA y DATOS se separan. La geometría es fija (el Censo 2024 no cambia)
    y se carga una vez; los 52 indicadores viajan en arreglos COLUMNARES
    alineados por posición, sin repetir un solo nombre de clave.
  · Las coordenadas se redondean a 5 decimales ≈ 1,1 m en el ecuador. Una manzana
    urbana mide decenas de metros: 1 m es invisible y son 10 dígitos menos por
    vértice.
  · Se simplifica con una tolerancia chica, medida en metros sobre UTM 20S.

No se toca ningún valor de los indicadores: sólo cambia cómo se serializan.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "datos"
SALIDA = RAIZ / "web" / "datos"
DECIMALES = 5          # ~1,1 m
TOLERANCIA_M = 1.5     # simplificación en metros (UTM 20S)


def slug_de(p):
    return p.stem.replace("manzanas_", "")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    cat = json.loads((ENTRADA / "catalogo.json").read_text(encoding="utf-8"))
    claves = [i["key"] for g in cat["grupos"] for i in g["indicadores"]]

    total_antes = total_geo = total_dat = 0
    for src in sorted(ENTRADA.glob("manzanas_*.geojson")):
        antes = src.stat().st_size
        g = gpd.read_file(src)
        n = len(g)

        # Simplificar en metros (UTM 20S) y volver a lon/lat.
        # `preserve_topology` evita que una manzana se coma a la vecina, pero NO
        # garantiza validez: en Santa Cruz quedaban 39 polígonos inválidos —
        # anillos que se auto-intersectan tras mover vértices— y un polígono
        # inválido se dibuja con artefactos o directamente no se dibuja.
        g["geometry"] = (g.to_crs("EPSG:32720").geometry
                         .simplify(TOLERANCIA_M, preserve_topology=True))
        # La reparación va DESPUÉS de reproyectar, no antes: el cambio de
        # coordenadas reintroduce auto-intersecciones diminutas y reparar en UTM
        # dejaba 5 polígonos inválidos igual. El orden importa.
        g = g.set_geometry(g["geometry"]).set_crs("EPSG:32720").to_crs("EPSG:4326")
        malas = ~g.geometry.is_valid
        if malas.any():
            g.loc[malas, "geometry"] = g.loc[malas, "geometry"].make_valid()
        vacias = g.geometry.is_empty | g.geometry.isna()
        if vacias.any():
            g = g[~vacias]
        restan = int((~g.geometry.is_valid).sum())
        if malas.any() or vacias.any() or restan:
            print(f"  · {slug_de(src):<24} reparadas {int(malas.sum())} · "
                  f"descartadas {int(vacias.sum())} · inválidas restantes {restan}")

        slug = slug_de(src)

        # ── geometría: sólo el índice posicional ────────────────────────────
        geo = g[["geometry"]].copy()
        geo["i"] = range(len(geo))
        p_geo = SALIDA / f"geo_{slug}.geojson"
        geo.to_file(p_geo, driver="GeoJSON", COORDINATE_PRECISION=DECIMALES)

        # ── datos: columnas alineadas por posición ──────────────────────────
        cols = {}
        for k in claves:
            if k not in g.columns:
                continue
            s = g[k]
            vals = []
            for v in s:
                if v is None or (isinstance(v, float) and v != v):
                    vals.append(None)
                else:
                    f = float(v)
                    vals.append(int(f) if f == int(f) else round(f, 1))
            cols[k] = vals
        dat = {
            "n": len(g),
            "codigo": g["codigo"].tolist(),
            "nombre": g["nombre"].tolist(),
            "ficha": [bool(x) for x in g["tiene_ficha"]],
            "cols": cols,
        }
        p_dat = SALIDA / f"dat_{slug}.json"
        p_dat.write_text(json.dumps(dat, ensure_ascii=False, separators=(",", ":")),
                         encoding="utf-8")

        sg, sd = p_geo.stat().st_size, p_dat.stat().st_size
        total_antes += antes
        total_geo += sg
        total_dat += sd
        print(f"  {slug:<26} {antes/1e6:>6.1f} MB → geo {sg/1e6:>5.1f} + dat {sd/1e6:>4.1f} "
              f"= {(sg+sd)/1e6:>5.1f} MB  ({100*(sg+sd)/antes:>3.0f}%)")

    print("-" * 78)
    print(f"  {'TOTAL':<26} {total_antes/1e6:>6.1f} MB → "
          f"{(total_geo+total_dat)/1e6:>5.1f} MB "
          f"({100*(total_geo+total_dat)/total_antes:.0f}% del original)")
    print(f"\n  geometría {total_geo/1e6:.1f} MB · datos {total_dat/1e6:.1f} MB")
    print(f"  → {SALIDA}")


if __name__ == "__main__":
    main()
