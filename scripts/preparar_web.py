"""
Prepara los insumos del nivel MUNICIPIO y copia los catálogos a web/datos.

  · municipios.geojson  los 9 polígonos, desde el mapa MAESTRO de bo-geo-maestro
    (343 municipios, clave `sigep`). No se recorta de ninguna otra fuente: la
    madre ya tiene los nombres curados y el crosswalk INE↔SIGEP congelado.
  · region.geojson      el contorno de la región (unión de los 9), para el
    encuadre inicial y para tapar el resto del mapa.
  · municipios.json y catalogo_tablero.json copiados tal cual.
"""
import json
import shutil
from pathlib import Path

import geopandas as gpd

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ.parent / "bo-geo-maestro" / "geo" / "atlas_muni_343.topojson"
SALIDA = RAIZ / "web" / "datos"


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    muns = json.loads((RAIZ / "datos" / "municipios.json").read_text(encoding="utf-8"))
    quiero = {m["sigep"]: m for m in muns}

    g = gpd.read_file(GEO)
    # El topojson maestro no declara CRS y GeoJSON sin proyección es una bomba de
    # tiempo para quien lo consuma después. Es lon/lat.
    if g.crs is None:
        g = g.set_crs("EPSG:4326")
    col = "sigep" if "sigep" in g.columns else g.columns[0]
    g[col] = g[col].astype(str)
    sub = g[g[col].isin(quiero)].copy()
    if len(sub) != len(quiero):
        faltan = set(quiero) - set(sub[col])
        raise SystemExit(f"ERROR: faltan municipios en el mapa maestro: {sorted(faltan)}")

    sub["sigep"] = sub[col]
    sub["nombre"] = sub["sigep"].map(lambda s: quiero[s]["nombre"])
    sub["ambito"] = sub["sigep"].map(lambda s: quiero[s]["ambito"])
    sub = sub[["sigep", "nombre", "ambito", "geometry"]]
    sub.to_file(SALIDA / "municipios.geojson", driver="GeoJSON",
                COORDINATE_PRECISION=5)

    borde = gpd.GeoDataFrame(geometry=[sub.union_all()], crs=sub.crs)
    borde.to_file(SALIDA / "region.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    for f in ("municipios.json", "catalogo_tablero.json"):
        shutil.copy(RAIZ / "datos" / f, SALIDA / f)

    # ── serie fiscal de los 9 ────────────────────────────────────────────────
    # El fiscal_data.json del Atlas pesa 736 KB con los 343 municipios; acá se
    # recortan los 9 y queda una fracción. Cada entidad trae `pob` por gestión y
    # `s[indicador][i_año]`, que es el ponderador correcto para el pivote.
    fdir = RAIZ.parent / "Observatorio de Presupuesto Fiscal Departamental" / "_github_atlas_fiscal"
    fdata = json.loads((fdir / "fiscal_data.json").read_text(encoding="utf-8"))
    fcat = json.loads((fdir / "fiscal_catalogo.json").read_text(encoding="utf-8"))
    recorte = {s: fdata[s] for s in quiero if s in fdata}
    faltan_fi = set(quiero) - set(recorte)
    (SALIDA / "fiscal.json").write_text(
        json.dumps({"anios": fcat["anios"], "entidades": recorte},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = (SALIDA / "fiscal.json").stat().st_size / 1024
    print(f"  fiscal: {len(recorte)}/{len(quiero)} entidades · {len(fcat['anios'])} gestiones · {kb:.0f} KB"
          + (f"  ⚠ sin dato fiscal: {sorted(faltan_fi)}" if faltan_fi else ""))

    # ── minimapas de las tarjetas ────────────────────────────────────────────
    # Cada indicador del panel lleva una miniatura de la región pintada con SU
    # valor, igual que en los atlas nacionales. Se precalculan los contornos ya
    # simplificados y proyectados a un lienzo 100×100, para que el navegador sólo
    # tenga que pintarlos: son 9 polígonos por tarjeta y ~16 tarjetas visibles.
    mini = sub.to_crs("EPSG:32720")
    mini["geometry"] = mini.geometry.simplify(320, preserve_topology=True)
    mini = mini.to_crs("EPSG:4326")
    mxmin, mymin, mxmax, mymax = mini.total_bounds
    ancho, alto = mxmax - mxmin, mymax - mymin
    esc = 100 / max(ancho, alto)
    dx = (100 - ancho * esc) / 2
    dy = (100 - alto * esc) / 2

    def a_path(geom):
        partes = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        d = []
        for p in partes:
            for anillo in [p.exterior] + list(p.interiors):
                pts = [(round((x - mxmin) * esc + dx, 1),
                        round(100 - ((y - mymin) * esc + dy), 1))
                       for x, y in anillo.coords]
                if len(pts) < 3:
                    continue
                d.append("M" + " ".join(f"{x},{y}" for x, y in pts) + "Z")
        return "".join(d)

    paths = {r["sigep"]: a_path(r["geometry"]) for _, r in mini.iterrows()}
    (SALIDA / "mini.json").write_text(
        json.dumps({"viewBox": "0 0 100 100", "paths": paths},
                   ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  minimapas: {len(paths)} siluetas · "
          f"{(SALIDA / 'mini.json').stat().st_size/1024:.0f} KB")

    xmin, ymin, xmax, ymax = sub.total_bounds
    print(f"  {len(sub)} municipios · bbox [{xmin:.3f}, {ymin:.3f}, {xmax:.3f}, {ymax:.3f}]")
    for _, r in sub.sort_values("nombre").iterrows():
        print(f"    {r['sigep']}  {r['nombre']:<26} {r['ambito']}")
    print(f"  → {SALIDA}")


if __name__ == "__main__":
    main()
