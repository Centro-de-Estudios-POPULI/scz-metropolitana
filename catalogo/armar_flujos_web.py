# -*- coding: utf-8 -*-
"""
LLEVA LAS MATRICES ORIGEN-DESTINO A LA WEB.
============================================

`motor_flujos.py` calcula 125.110 pares O-D y no emitía nada que la web pudiera
leer. Acá se recorta a la Región Metropolitana y se emite un JSON chico
(9×9 × 3 matrices) para una vista propia: **no son coropléticos**, un número por
PAR de municipios no entra en un mapa de colores.

★ EL PROBLEMA DE FONDO ES EL DENOMINADOR. La sub-matriz 9×9 no suma el universo:
  faltan los destinos fuera de la región. Si la retención se calcula dentro del
  9×9 da 71,4% para Porongo y sobre todos los destinos declarados da 69,9%. Por
  eso cada fila viaja con `fuera` y con su total declarado: una fila que no
  cierra invita a leer porcentajes de un universo que no es el suyo.

⚠️⚠️ NO REPRODUCE `autocontencion_laboral`, Y NO ES UN ERROR DE ACÁ.
  Los dos motores usan universos DISTINTOS para el mismo concepto:

      motor_persona.py:517   ocu = d.ocupado & (d.edad >= 14) & res
      motor_flujos.py:67     uni = d.ocupado & d.residente

  El indicador publicado corta en 14 años y la matriz no. Verificado sobre el
  microdato: aplicando el corte de 14 a numerador y denominador, los 9 municipios
  reproducen el indicador AL DECIMAL. Sin él la retención queda **+0,1 a +0,4 pp
  más alta** — chico, pero son 14.507 ocupados menores de 14 años que declaran
  municipio de trabajo sólo en los 9, y son dos definiciones conviviendo.
  ⚠️ Y OJO CON EL DIAGNÓSTICO: la primera medición dio +5,3 pp y era falsa. Salía
    de filtrar `nivel == "municipio"` en este script, que tira las declaraciones
    parciales y achica el denominador. Antes de culpar a otro motor, cerrar la
    propia fila.
  ⇒ Acá NO se corrige, a propósito: alinear el motor de flujos movería cifras YA
    PUBLICADAS (`poblacion_flotante`, `saldo_migratorio`, `entran_a_trabajar`).
    Es una decisión de Carlos, y hasta que se tome esta salida declara su propio
    universo en `universo_nota` para que la vista lo diga en pantalla en vez de
    contradecir en silencio a la ficha del municipio.

★ LOS PARCIALES NO SE TIRAN. El INE codifica "departamento sin municipio
  especificado" como `XX9999`: `motor_flujos.py` los conserva con su `nivel`, y
  acá caen en `fuera` en vez de desaparecer.

    python armar_flujos_web.py
"""
import json, pathlib
import pandas as pd

AQUI = pathlib.Path(__file__).parent
RAIZ = AQUI.parent
SALIDA = RAIZ / "web" / "datos"

TIPOS = {
    "trabajo":     ("Dónde trabaja", "municipio de residencia → municipio donde trabaja",
                    "ocupados residentes que declararon en qué municipio trabajan, "
                    "SIN corte de edad (el indicador «Autocontención laboral» corta "
                    "en 14 años, así que sus porcentajes no son intercambiables)"),
    "residencia5": ("Dónde vivía hace 5 años", "municipio hace 5 años → municipio actual",
                    "residentes de 5 años o más que declararon dónde vivían en 2019"),
    "nacimiento":  ("Dónde nació", "municipio de nacimiento → municipio de residencia",
                    "residentes que declararon en qué municipio nacieron"),
}


def main():
    muns = json.loads((RAIZ / "datos" / "municipios.json").read_text(encoding="utf-8"))
    n9 = {m["cod_ine"]: m["nombre"] for m in muns}
    orden = sorted(n9, key=lambda c: n9[c])

    f = pd.read_csv(AQUI / "flujos_2024.csv", dtype={"origen": str, "destino": str})
    # ⚠️ NO se filtra por `nivel == "municipio"`. Ese filtro tira las
    #    DECLARACIONES PARCIALES —"departamento sin municipio especificado"
    #    (`XX9999`) y "provincia sin municipio" (`XXYY99`)—, que son el 12% de los
    #    flujos y que `motor_flujos.py` conserva a propósito. Descartarlas achica
    #    el denominador de cada fila y **infla la retención**: Warnes pasaba de
    #    77,5% a 81,1% sólo por eso. Van a su propia columna, visibles.

    salida = {"municipios": [{"cod_ine": c, "nombre": n9[c]} for c in orden], "matrices": {}}
    for tipo, (titulo, eje, universo) in TIPOS.items():
        s = f[f.tipo == tipo]
        m = {}
        for o in orden:
            fila = s[s.origen == o]
            exacto = fila[fila.nivel == "municipio"]
            dentro = {d: int(exacto[exacto.destino == d].personas.sum()) for d in orden}
            total = int(fila.personas.sum())
            parcial = int(fila[fila.nivel != "municipio"].personas.sum())
            # la fila cierra sobre SU universo: los 9 de la región, el resto del
            # país con municipio exacto, y lo declarado sólo hasta departamento o
            # provincia. No se mezcla con el denominador del indicador, que es
            # otro (ver la advertencia del encabezado).
            m[o] = {"a": [dentro[d] for d in orden],
                    "fuera": total - parcial - sum(dentro.values()),
                    "parcial": parcial,
                    "declarado": total}
        salida["matrices"][tipo] = {"titulo": titulo, "eje": eje, "universo_nota": universo,
                                    "filas": m}
        tot = sum(v["declarado"] for v in m.values())
        prop = sum(v["a"][orden.index(o)] for o, v in m.items())
        print(f"{tipo:12} · {tot:>9,} declarados · {100*prop/tot:5.1f}% se queda en su municipio")

    # ── LA DIVERGENCIA, DICHA EN VOZ ALTA EN CADA CORRIDA ────────────────────
    # Mientras los dos motores no compartan universo, esta salida y la ficha del
    # municipio van a mostrar dos números distintos para lo mismo. Que se vea.
    pub = {x["cod_ine"]: x["municipal"].get("autocontencion_laboral")
           for x in json.loads((SALIDA / "municipios_municipal.json").read_text(encoding="utf-8"))}
    filas = salida["matrices"]["trabajo"]["filas"]
    peor = max(orden, key=lambda c: abs(100 * filas[c]["a"][orden.index(c)] / filas[c]["declarado"]
                                        - (pub.get(c) or 0)))
    d_peor = 100 * filas[peor]["a"][orden.index(peor)] / filas[peor]["declarado"] - pub[peor]
    print(f"\n⚠️ retención de esta matriz vs. «Autocontención laboral» publicada: "
          f"difieren hasta {d_peor:+.1f} pp ({n9[peor]}).")
    print("   Causa: el indicador corta en 14 años de edad y el motor de flujos no "
          "(motor_persona.py:517 vs motor_flujos.py:67). No se corrige acá porque "
          "alinearlo movería cifras ya publicadas.")

    SALIDA.mkdir(parents=True, exist_ok=True)
    p = SALIDA / "flujos_metro.json"
    p.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {p.name}  {p.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
