# -*- coding: utf-8 -*-
"""
GENERA LOS DOS SITIOS DESDE EL `index.html` QUE YA FUNCIONA.
=============================================================

Decisión de producto: son DOS tableros. Pero el motor de interfaz —mapa canvas
sobre CARTO, tarjetas con minimapa, ficha, comparativo entre los 9, tooltips,
tema claro/oscuro, fundido por zoom— es el MISMO y ya está resuelto. Reescribirlo
dos veces sería tirar trabajo y duplicar los bugs.

⇒ Este script deriva los dos `index.html` del original, cambiando sólo:

  · qué par de archivos carga (cada tablero tiene su catálogo y sus municipios),
  · si existe el conmutador Municipio/Manzana,
  · el título y las rutas relativas (los datos quedan COMPARTIDOS en `web/datos/`,
    así la geometría de las manzanas —12,4 MB— no se duplica).

⚠️ Es un DERIVADO: no editar `web/municipal/index.html` ni `web/manzana/index.html`
   a mano. Se toca `web/index.html` y se vuelve a correr esto.

    python scripts/generar_sitios.py
"""
import pathlib, re, sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "web" / "index.html"

SITIOS = {
 "municipal": {
   "titulo": "Santa Cruz · Atlas Metropolitano — Municipal",
   "cabecera": "<b>Santa Cruz:</b> Atlas Metropolitano",
   "catalogo": "catalogo_municipal.json",
   "municipios": "municipios_municipal.json",
   "toggle": False,
 },
 "manzana": {
   "titulo": "Santa Cruz · Atlas Metropolitano — Municipio y manzana",
   "cabecera": "<b>Santa Cruz:</b> Atlas Metropolitano <span class=\"t-sub\">· manzana</span>",
   "catalogo": "catalogo_manzana.json",
   "municipios": "municipios_manzana.json",
   "toggle": True,
 },
}


def derivar(html, cfg):
    # ── los datos y la hoja de estilo viven un nivel más arriba y son compartidos ──
    # ⚠️ La hoja SE OLVIDÓ la primera vez y los dos sitios salieron sin paneles:
    #    el mapa se dibujaba (lo pinta el canvas) pero toda la interfaz alrededor
    #    era HTML sin estilo, o sea invisible. Un 404 de CSS no rompe nada, sólo
    #    borra la mitad del producto.
    html = html.replace('href="estilo-atlas.css"', 'href="../estilo-atlas.css"')
    html = html.replace('fetch("datos/', 'fetch("../datos/')
    html = html.replace('fetch(`datos/', 'fetch(`../datos/')
    # ── cada tablero, su par de archivos ──
    html = html.replace('"../datos/catalogo_tablero.json"', f'"../datos/{cfg["catalogo"]}"')
    html = html.replace('"../datos/municipios.json"', f'"../datos/{cfg["municipios"]}"')
    # ── título y cabecera ──
    html = re.sub(r"<title>.*?</title>", f"<title>{cfg['titulo']}</title>", html, count=1)
    html = re.sub(r'(<div class="t-h">).*?(</div>)',
                  lambda m: m.group(1) + cfg["cabecera"] + m.group(2), html, count=1)
    if not cfg["toggle"]:
        # ⚠️ El conmutador se OCULTA, no se borra. Al quitar los botones del HTML,
        #    `document.querySelector('#niv button[data-n="manzana"]')` devolvía
        #    null y la línea siguiente (`bMz.disabled = …`) tiraba TypeError: la
        #    página quedaba con el mapa base y nada más. Ocultarlo deja todos los
        #    selectores en pie y el nivel fijo en "municipio".
        #   ⚠️ La regla es `.niv{`, por CLASE, no `#niv{`: apuntar al id no
        #      coincidía con nada y el conmutador seguía a la vista, apagado.
        html = html.replace(".niv{display:flex", ".niv{display:none")
    return html


def main():
    if not FUENTE.exists():
        sys.exit(f"no encuentro {FUENTE}")
    base = FUENTE.read_text(encoding="utf-8")
    for slug, cfg in SITIOS.items():
        d = RAIZ / "web" / slug
        d.mkdir(exist_ok=True)
        out = d / "index.html"
        out.write_text(derivar(base, cfg), encoding="utf-8")
        print(f"  -> web/{slug}/index.html   {out.stat().st_size/1024:.0f} KB "
              f"· {cfg['catalogo']} · toggle {'sí' if cfg['toggle'] else 'no'}")


if __name__ == "__main__":
    main()
