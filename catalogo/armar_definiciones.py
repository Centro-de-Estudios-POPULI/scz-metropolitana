# -*- coding: utf-8 -*-
"""Une las tres partes redactadas en `definiciones.json`, que es lo que lee el
armador de tableros.

La fuente de verdad son los ficheros `definiciones_a/b/c.py`: el JSON es un
producto y se puede borrar y rehacer. Antes de este script el JSON se había
escrito a mano una sola vez desde A y B, y por eso la parte C —los 30 fiscales—
no tenía por dónde entrar.

    python catalogo/armar_definiciones.py
"""
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).resolve().parent


def cargar(nombre, atributo):
    ruta = AQUI / f"definiciones_{nombre}.py"
    spec = importlib.util.spec_from_file_location(f"def_{nombre}", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, atributo)


partes = [("a", "DEF_A"), ("b", "DEF_B"), ("c", "DEF_C")]
todo, choques = {}, []
for nombre, atributo in partes:
    d = cargar(nombre, atributo)
    # Una clave repetida entre partes sería una definición pisando a otra en
    # silencio: se avisa en vez de dejar que gane la última.
    choques += [k for k in d if k in todo]
    todo.update(d)
    print(f"  {atributo}: {len(d)}")

if choques:
    print(f"  ⚠️ claves repetidas entre partes: {', '.join(sorted(set(choques)))}")

(AQUI / "definiciones.json").write_text(
    json.dumps(todo, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"→ definiciones.json  {len(todo)} definiciones")
