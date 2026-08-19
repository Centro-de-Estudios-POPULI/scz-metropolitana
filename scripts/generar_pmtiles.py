# -*- coding: utf-8 -*-
"""
TESELA EL NIVEL MANZANA A UN ARCHIVO PMTiles.
==============================================

Reemplaza el par `geo_<muni>.geojson` + `dat_<muni>.json` (24,1 MB que el
navegador baja y parsea enteros) por UN archivo de teselas vectoriales del que
el mapa pide sólo el pedazo que está mirando.

★ EL PUNTO NO ES EL PESO DE RED, ES EL REPINTADO. Con los datos dentro de la
  tesela como atributos, cambiar de indicador es cambiar la expresión de color
  —`["get", clave]`— y nada más. Hoy `pintar()` reescribe `properties.v` en los
  38.892 polígonos y llama `setData()`: 12,1 MB reserializados y todo el nivel
  reteselado por cambiar un color. Medido en `web/_prueba_peso.html`.
  Por eso PMTiles vuelve a la mesa después de haberse descartado: la medición
  que lo descartó comparaba peso de red, que era la pregunta equivocada.

★ SIN tippecanoe. No hay binario de Windows, y en esta máquina tampoco hay WSL
  ni Docker (verificado: `wsl.exe` está en el PATH pero el subsistema NO está
  instalado). Se tesela con shapely + mapbox_vector_tile y se empaqueta con la
  librería `pmtiles` de Protomaps.

⚠️ Los `geo_*.geojson` traen 21 GeometryCollection y 11 MultiPolygon, residuo de
   la reparación de geometrías inválidas. Se normaliza todo a (Multi)Polygon: un
   GeometryCollection sin filtrar hace fallar el codificador de MVT.

    python scripts/generar_pmtiles.py
"""
import gzip, json, math, pathlib, sys, time

import shapely
from shapely import STRtree
from shapely.geometry import box, shape
from shapely.ops import transform as sh_transform
import mapbox_vector_tile
from mapbox_vector_tile.encoder import on_invalid_geometry_make_valid
from pmtiles.writer import Writer
from pmtiles.tile import Compression, TileType, zxy_to_tileid

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DATOS = RAIZ / "web" / "datos"
SALIDA = DATOS / "manzanas.pmtiles"

# ── Banda de zoom ────────────────────────────────────────────────────────────
# El cruce municipio→manzana ocurre entre Z_A y Z_B (ver `web/index.html`).
# Las teselas arrancan en ZMIN, un poco antes del cruce, para que las manzanas
# ya estén disponibles cuando el fundido empieza a mostrarlas. Por encima de
# ZMAX, MapLibre sobre-escala la última tesela: no hace falta teselar más.
#
# ★ ZMIN BAJÓ 12 -> 11 -> 10, en tres pedidos de Carlos, cada uno para que la
#   transformación ocurra estando MÁS LEJOS. z10 es el fondo razonable: a ese
#   nivel una manzana de 100 m mide 0,7 px —sub-píxel— así que deja de leerse
#   como polígono y pasa a leerse como MANCHA. Medido antes de aplicarlo:
#   17 teselas · +4,0 MB al archivo · vista de 6 teselas 1,4 MB · la tesela más
#   pesada 2.886 KB con 27.902 manzanas. Es viable; el costo es de lectura, no
#   de peso.
#   (nota original de cuando bajó a 11:)
#   La objeción original era que a z11 una tesela se lleva 8.707 manzanas de un
#   píxel —la mancha que el proyecto decidió no mostrar— y que es el nivel más
#   pesado (los atributos son el 79-81% de cada tesela).
#   Lo segundo se midió y resultó menos grave de lo que parecía: una VISTA a
#   z11 baja 1.393 KB contra los 1.161 KB de una a z12, o sea 230 KB más, y el
#   archivo pasa de 11,52 a 14,55 MB. Sigue muy por debajo de los 24,09 MB de
#   los `geo_*`+`dat_*` que reemplaza.
#   Lo primero se resuelve con el FUNDIDO, no con el teselado: a z11,4 las
#   manzanas recién asoman y sólo llegan a opacidad plena en z12,1, donde ya
#   miden 2,9 px. El nivel existe para que el cruce pueda empezar antes, no
#   para mirar fijo la región entera cubierta de manzanas.
ZMIN, ZMAX = 10, 14
EXTENT = 4096
BUFFER = 64          # en unidades de tesela: cose los bordes entre teselas vecinas
CAPA = "manzanas"

R = 6378137.0

def merc(lon, lat):
    x = R * math.radians(lon)
    y = R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, y

MUNDO = math.pi * R   # media circunferencia: el borde del mundo en Web Mercator


def tile_bounds(z, x, y):
    """bbox de la tesela en Web Mercator."""
    n = 2 ** z
    lado = 2 * MUNDO / n
    return (-MUNDO + x * lado, MUNDO - (y + 1) * lado,
            -MUNDO + (x + 1) * lado, MUNDO - y * lado)


def tile_xy(z, mx, my):
    """tesela que contiene un punto de Web Mercator."""
    n = 2 ** z
    lado = 2 * MUNDO / n
    return int((mx + MUNDO) / lado), int((MUNDO - my) / lado)


def normalizar(g):
    """Todo a (Multi)Polygon. Un GeometryCollection revienta el codificador."""
    if g.is_empty:
        return None
    t = g.geom_type
    if t in ("Polygon", "MultiPolygon"):
        return g
    if t == "GeometryCollection":
        partes = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        if not partes:
            return None
        return shapely.union_all(partes)
    return None


def cargar():
    """Une geometría y datos en una sola lista de (geom_mercator, propiedades)."""
    slugs = sorted(p.stem[4:] for p in DATOS.glob("geo_*.geojson"))
    geoms, props = [], []
    claves = None
    for s in slugs:
        geo = json.loads((DATOS / f"geo_{s}.geojson").read_text(encoding="utf-8"))
        dat = json.loads((DATOS / f"dat_{s}.json").read_text(encoding="utf-8"))
        cols = dat["cols"]
        if claves is None:
            claves = sorted(cols)
        elif sorted(cols) != claves:
            sys.exit(f"{s}: los indicadores no coinciden con los de los otros municipios")
        for f in geo["features"]:
            g = f.get("geometry")
            if not g:
                continue
            g = normalizar(shape(g))
            if g is None:
                continue
            i = f["properties"]["i"]
            # ⚠️ Los datos viajan ALINEADOS POR POSICIÓN con la geometría (es lo
            #    que documenta `reempaquetar_manzana.py`). El índice `i` es esa
            #    posición: si se leyera por otra clave, cada manzana quedaría
            #    pintada con el valor de otra sin que nada fallara.
            p = {"s": s, "nom": dat["nombre"][i]}
            if dat["ficha"][i]:
                p["f"] = 1
            for k in claves:
                v = cols[k][i]
                # Un atributo AUSENTE y un atributo en cero son cosas distintas:
                # el mapa distingue "sin ficha" de "cero" con `["has", clave]`,
                # igual que hace el tablero de desarrollo infantil.
                if v is not None:
                    p[k] = v
            geoms.append(sh_transform(merc, g))
            props.append(p)
    return geoms, props, claves


def main():
    t0 = time.time()
    print("leyendo geometría y datos…")
    geoms, props, claves = cargar()
    print(f"  {len(geoms):,} manzanas · {len(claves)} indicadores como atributos")

    arbol = STRtree(geoms)
    minx, miny, maxx, maxy = shapely.total_bounds(geoms)
    print(f"  bbox mercator  x {minx:,.0f}..{maxx:,.0f}   y {miny:,.0f}..{maxy:,.0f}")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    escritas = 0
    with open(SALIDA, "wb") as fh:
        w = Writer(fh)
        for z in range(ZMIN, ZMAX + 1):
            x0, y1 = tile_xy(z, minx, miny)
            x1, y0 = tile_xy(z, maxx, maxy)
            lado = 2 * MUNDO / (2 ** z)
            # `buffer` en unidades de mundo, para pedir un poco más de lo que
            # entra en la tesela y que los polígonos no se corten en la costura
            bmundo = lado * BUFFER / EXTENT
            n_z = 0
            for tx in range(x0, x1 + 1):
                for ty in range(y0, y1 + 1):
                    bx0, by0, bx1, by1 = tile_bounds(z, tx, ty)
                    caja = box(bx0 - bmundo, by0 - bmundo, bx1 + bmundo, by1 + bmundo)
                    idx = arbol.query(caja)
                    if len(idx) == 0:
                        continue
                    # Tolerancia de simplificación: medio píxel de esta tesela.
                    # A z11 una manzana mide 1-2 px, así que sin esto se
                    # codifican vértices que no se pueden ver.
                    tol = lado / EXTENT * 0.5
                    feats = []
                    for k in idx:
                        g = geoms[k]
                        if not g.intersects(caja):
                            continue
                        g = g.intersection(caja)
                        g = normalizar(g)
                        if g is None or g.is_empty:
                            continue
                        g = g.simplify(tol, preserve_topology=True)
                        g = normalizar(g)
                        if g is None or g.is_empty:
                            continue
                        feats.append({"geometry": g, "properties": props[k]})
                    if not feats:
                        continue
                    tile = mapbox_vector_tile.encode(
                        {"name": CAPA, "features": feats},
                        default_options={
                            "quantize_bounds": (bx0, by0, bx1, by1),
                            "extents": EXTENT,
                            # recorte + simplificación pueden dejar un anillo
                            # degenerado; repararlo pierde menos que descartarlo
                            "on_invalid_geometry": on_invalid_geometry_make_valid,
                        },
                    )
                    if not tile:
                        continue
                    # ⚠️ `Writer.write_tile` escribe los bytes TAL CUAL: no
                    #    comprime. El encabezado declara `tile_compression:
                    #    GZIP`, así que comprimir acá no es una optimización
                    #    opcional — sin esto el archivo queda mal formado y el
                    #    cliente intenta descomprimir lo que no lo está.
                    #    De paso es la mitad del peso: medido, −45%.
                    w.write_tile(zxy_to_tileid(z, tx, ty), gzip.compress(tile, 9))
                    escritas += 1
                    n_z += 1
            print(f"  z{z}: {n_z:,} teselas   ({time.time()-t0:,.0f}s)")

        # bbox en grados para el encabezado
        def inv(mx, my):
            lon = math.degrees(mx / R)
            lat = math.degrees(2 * math.atan(math.exp(my / R)) - math.pi / 2)
            return lon, lat
        lo = inv(minx, miny); hi = inv(maxx, maxy)
        w.finalize(
            {
                "tile_type": TileType.MVT,
                "tile_compression": Compression.GZIP,
                "min_zoom": ZMIN,
                "max_zoom": ZMAX,
                "min_lon_e7": int(lo[0] * 1e7), "min_lat_e7": int(lo[1] * 1e7),
                "max_lon_e7": int(hi[0] * 1e7), "max_lat_e7": int(hi[1] * 1e7),
                "center_zoom": ZMIN,
                "center_lon_e7": int((lo[0] + hi[0]) / 2 * 1e7),
                "center_lat_e7": int((lo[1] + hi[1]) / 2 * 1e7),
            },
            {
                "attribution": "INE · Censo 2024, fichas por manzano",
                "vector_layers": [{
                    "id": CAPA, "minzoom": ZMIN, "maxzoom": ZMAX,
                    "fields": {**{k: "Number" for k in claves},
                               "s": "String", "nom": "String", "f": "Number"},
                }],
            },
        )
    mb = SALIDA.stat().st_size / 1e6
    print(f"\n{SALIDA.name}: {escritas:,} teselas · {mb:.2f} MB "
          f"· {time.time()-t0:,.0f}s")
    print(f"  contra 24,09 MB de geo_*.geojson + dat_*.json")


if __name__ == "__main__":
    main()
