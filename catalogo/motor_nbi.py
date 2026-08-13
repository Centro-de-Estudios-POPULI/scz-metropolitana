# -*- coding: utf-8 -*-
"""
NBI — el único bloque que NO sale del microdato.
=================================================

Los 13 indicadores de Necesidades Básicas Insatisfechas se leen del tabulado
`pobreza.xlsx` del INE. Se podrían derivar del microdato, pero replicar la
metodología oficial del NBI (umbrales por componente, agregación, población de
referencia) es un proyecto en sí mismo y no aporta nada al tablero: el INE ya
los publica para 2012 y 2024 a nivel municipio.

Queda marcado como `fuente="tabulado"` en el catálogo para que nunca se confunda
con lo que sí calculamos.

Estructura de la hoja: fila 5 = año, fila 6 = grupo (POBLACIÓN DE REFERENCIA /
NO POBRE / POBRE), fila 7 = categoría. La columna de referencia tiene la fila 7
vacía, así que su nombre hay que tomarlo de la fila 6.
"""
import pathlib, unicodedata, csv, re
import pandas as pd, numpy as np, openpyxl

AQUI = pathlib.Path(__file__).parent
TAB = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\Retrato_Censal_2024\Censo2024_Tabulados")
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro\spine\municipios.csv")

def norm(s):
    s = str(s or "")
    s = re.sub(r"[‐-―−-]", " ", s)
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()
    s = " ".join(s.lower().split())
    return re.sub(r"^tioc[a ]*", "tioc ", s)

def rellenar(fila, hasta):
    out, u = [], ""
    for i in range(hasta):
        v = fila[i] if i < len(fila) else None
        if v not in (None, ""):
            u = norm(v)
        out.append(u)
    return out

# categoría del INE -> clave del catálogo
MAPA = {
 "total poblacion no pobre":       "pct_nbi_no_pobre",
 "necesidades basicas satisfechas":"pct_nbi_satisfechas",
 "umbral":                         "pct_nbi_umbral",
 "total poblacion pobre":          "pct_nbi_pobre",
 "moderada":                       "pct_nbi_moderada",
 "indigente":                      "pct_nbi_indigente",
 "marginal":                       "pct_nbi_marginal",
}

def leer(hoja, mapa):
    wb = openpyxl.load_workbook(TAB / "pobreza.xlsx", read_only=True, data_only=True)
    ws = wb[hoja]
    cab = list(ws.iter_rows(min_row=1, max_row=8, values_only=True))
    ancho = max(len(f) for f in cab)
    años = rellenar(cab[4], ancho)
    grupo = rellenar(cab[5], ancho)
    cat = [norm(c) for c in cab[6][:ancho]] + [""] * max(0, ancho - len(cab[6]))
    cols, refs = {}, {}
    for i in range(ancho):
        a = re.search(r"\b(2012|2024)\b", años[i] or "")
        if not a: continue
        y = int(a.group(1))
        if "referencia" in grupo[i] and not cat[i]:
            refs[y] = i
        elif cat[i] in mapa:
            cols[(y, mapa[cat[i]])] = i
    filas, ctx = {}, None
    for f in ws.iter_rows(min_row=8, values_only=True):
        if f[2] and str(f[2]).startswith(("Municipio", "MUNICIPIO")):
            ctx = (norm(f[3]), norm(f[5]))
        if ctx and f[6] and norm(f[6]) == ctx[1]:
            filas[ctx] = f
    wb.close()
    return cols, refs, filas


# Componentes (hoja 3). Ojo: dos de los seis tienen la fila 7 vacía y su nombre
# vive en la fila 6, así que la categoría se toma de una u otra.
COMPONENTES = {
 "inadecuados materiales":        "pct_nbi_materiales",
 "insuficientes espacios":        "pct_nbi_espacios",
 "inadecuados servicios de agua": "pct_nbi_agua_sanea",
 "inadecuados insumos energeticos": "pct_nbi_energia",
 "insuficiencia en educacion":    "pct_nbi_educacion",
 "inadecuada atencion en salud":  "pct_nbi_salud",
}

def leer_componentes():
    wb = openpyxl.load_workbook(TAB / "pobreza.xlsx", read_only=True, data_only=True)
    ws = wb["3"]
    cab = list(ws.iter_rows(min_row=1, max_row=8, values_only=True))
    ancho = max(len(f) for f in cab)
    años = rellenar(cab[4], ancho)
    grupo = [norm(c) for c in cab[5][:ancho]] + [""] * max(0, ancho - len(cab[5]))
    cat = [norm(c) for c in cab[6][:ancho]] + [""] * max(0, ancho - len(cab[6]))
    cols = {}
    for i in range(ancho):
        a = re.search(r"\b(2012|2024)\b", años[i] or "")
        if not a: continue
        etiqueta = cat[i] or grupo[i]
        for pref, clave in COMPONENTES.items():
            if etiqueta.startswith(pref):
                cols[(int(a.group(1)), clave)] = i
    filas, ctx = {}, None
    for f in ws.iter_rows(min_row=8, values_only=True):
        if f[2] and str(f[2]).startswith(("Municipio", "MUNICIPIO")):
            ctx = (norm(f[3]), norm(f[5]))
        if ctx and f[6] and norm(f[6]) == ctx[1]:
            filas[ctx] = f
    wb.close()
    return cols, filas


if __name__ == "__main__":
    cols, refs, filas = leer("1", MAPA)
    print(f"columnas detectadas: {len(cols)} · referencia: {refs} · municipios: {len(filas)}")
    sp = list(csv.DictReader(open(SPINE, encoding="utf-8")))
    clave = {}
    for r in sp:
        for nm in {norm(r["nombre_censo"]), norm(r["nombre"])}:
            clave[(norm(r["dpto"]), nm)] = r["cod_ine"]
    sin = [k for k in filas if k not in clave]
    if sin:
        print(f"⚠️ sin emparejar ({len(sin)}): {sin[:5]}")

    cols_c, filas_c = leer_componentes()
    print(f"componentes detectados: {sorted({c for _, c in cols_c})}")

    for anio in (2024, 2012):
        datos = {}
        for k, f in filas.items():
            ci = clave.get(k)
            if not ci: continue
            ref = f[refs[anio]]
            if not ref: continue
            fila = {"poblacion_nbi": float(ref)}
            for (y, ind), i in cols.items():
                if y == anio:
                    fila[ind] = 100 * float(f[i] or 0) / float(ref)
            # los componentes van sobre la misma población de referencia
            fc = filas_c.get(k)
            if fc is not None:
                for (y, ind), i in cols_c.items():
                    if y == anio:
                        fila[ind] = 100 * float(fc[i] or 0) / float(ref)
            datos[ci] = fila
        d = pd.DataFrame(datos).T
        d.index.name = "cod_ine"
        d.to_csv(AQUI / f"nbi_{anio}.csv", encoding="utf-8")
        print(f"{anio}: {len(d)} municipios · población de referencia "
              f"{d.poblacion_nbi.sum():,.0f} · pobreza media {d.pct_nbi_pobre.mean():.1f}%")
    print("-> nbi_2024.csv · nbi_2012.csv")
