"""
Extrae la hoja de estilo del Atlas Socioeconómico a `web/estilo-atlas.css`.

Se extrae en vez de transcribirse a mano: la identidad son ~200 reglas y copiar
a ojo es exactamente como se produce una deriva —un token que queda viejo, un
gris que no es el gris— que después nadie encuentra. Si el Atlas cambia, se
vuelve a correr esto y el tablero se entera.

Lo que NO se trae: las reglas del renderizador de canvas (`#map-wrap canvas`,
`#pick`, `#fade`), porque acá el mapa es MapLibre y esos selectores no existen.
Quedan comentadas para que se vea que la omisión fue deliberada.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ATLAS = (RAIZ.parent / "Observatorio de Presupuesto Fiscal Departamental"
         / "_github_atlas_fiscal" / "Mapa_Censo_2024_Bolivia.html")
SALIDA = RAIZ / "web" / "estilo-atlas.css"

# Selectores del motor viejo: se retiran y se deja constancia.
CANVAS = ["#map-wrap canvas", "#pick", "#fade", "#map-wrap"]

CABECERA = """/* ─────────────────────────────────────────────────────────────────────────
   IDENTIDAD DEL OBSERVATORIO — extraída de Mapa_Censo_2024_Bolivia.html
   (repo Atlas-Fiscal-Municipal). NO editar a mano: se regenera con
   `python scripts/extraer_estilo.py`. Si hay que cambiar la identidad, se
   cambia en el Atlas y se vuelve a extraer, para que los tres mapas del
   ecosistema no se separen.

   Se omitieron las reglas del renderizador de canvas del Atlas
   (%s), porque acá el mapa es MapLibre.
   ───────────────────────────────────────────────────────────────────────── */
"""


def main():
    html = ATLAS.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        raise SystemExit("ERROR: no se encontró el bloque <style> del Atlas")
    css = m.group(1)

    quitadas = []
    for sel in CANVAS:
        patron = re.compile(r"^" + re.escape(sel) + r"\s*\{[^}]*\}\s*$", re.M)
        css, n = patron.subn("", css)
        if n:
            quitadas.append(sel)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text((CABECERA % ", ".join(quitadas or ["ninguna"])) + css.strip() + "\n",
                      encoding="utf-8")

    tokens = len(re.findall(r"--[a-z0-9-]+\s*:", css))
    reglas = css.count("{")
    print(f"  {reglas} reglas · {tokens} tokens CSS")
    print(f"  reglas de canvas retiradas: {', '.join(quitadas) or '(ninguna)'}")
    print(f"  {SALIDA.stat().st_size/1024:.0f} KB → {SALIDA}")


if __name__ == "__main__":
    main()
