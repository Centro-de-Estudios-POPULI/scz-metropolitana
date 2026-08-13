# -*- coding: utf-8 -*-
"""
MOTOR DE FLUJOS — matrices origen-destino, que no son coropléticos.
===================================================================

Los otros motores producen UN número por municipio. Éste produce un número por
PAR de municipios, así que necesita salida propia y, en el tablero, una vista
propia (mapa de flujos o matriz, no un mapa de colores).

Tres matrices, todas de 2024:
  · `nacimiento`   municipio de nacimiento  → municipio de residencia
  · `residencia5`  municipio hace 5 años    → municipio de residencia
  · `trabajo`      municipio de residencia  → municipio donde trabaja

⚠️ 2012 NO ENTRA, y no es por pereza. Sus variables de migración (`P32G`,
   `P32H`, `P32H1`, `P34F`, `P34G`…) **no traen etiquetas en el diccionario
   Redatam** y no se comportan como códigos de municipio: `P32H` tiene diez
   valores y su categoría 1 sola reúne 1,58 M de personas. Reconstruir el
   esquema a ojo produciría flujos verosímiles y falsos, que es exactamente el
   modo de falla que este pipeline viene corrigiendo. Queda pendiente del
   cuestionario/diccionario de 2012.
   (Una nota vieja del proyecto decía que la matriz O-D tenía serie intercensal
   a nivel municipio: es INCORRECTA.)

★ LAS DECLARACIONES PARCIALES SON EL 12% Y NO SE TIRAN.
  El INE codifica "departamento sin provincia ni municipio especificado" como
  `XX9999` y "provincia sin municipio especificado" como `XXYY99`: 119 códigos
  distintos y 1.322.152 personas en el municipio de nacimiento. Descartarlas en
  silencio subestima los flujos y sesga a favor de los orígenes bien declarados.
  Cada fila lleva su `nivel` (municipio / provincia / departamento) para que el
  tablero pueda mostrarlas como "resto del departamento X" en vez de perderlas.
"""
import pathlib, csv, sys
import pandas as pd, numpy as np

AQUI = pathlib.Path(__file__).parent
PARQ = pathlib.Path(r"C:\Users\HP\cpv2024\persona_full.parquet")
SPINE = pathlib.Path(r"C:\Users\HP\OneDrive\Desktop\Proyectos\bo-geo-maestro"
                     r"\spine\municipios.csv")

MATRICES = {"nacimiento": "mun_nac", "residencia5": "mun_res5", "trabajo": "mun_trabaja"}


def nivel_de(cod, espina):
    """Hasta dónde llega la declaración: municipio, provincia o departamento."""
    if cod in espina:
        return "municipio"
    if cod.endswith("9999"):
        return "departamento"
    if cod.endswith("99"):
        return "provincia"
    return "otro"


def main():
    espina = {r["cod_ine"] for r in csv.DictReader(open(SPINE, encoding="utf-8"))}
    cols = ["cod_ine", "edad", "residente", "ocupado"] + list(MATRICES.values())
    d = pd.read_parquet(PARQ, columns=cols)
    d["cod_ine"] = d.cod_ine.astype(str)
    print(f"{len(d):,} personas · espina de {len(espina)} municipios", flush=True)

    filas = []
    for tipo, col in MATRICES.items():
        s = d[col].astype(str)
        # el universo cambia por matriz: la conmutación se define sobre
        # ocupados, la migración sobre residentes
        if tipo == "trabajo":
            uni = d.ocupado & d.residente
        elif tipo == "residencia5":
            uni = d.residente & (d.edad >= 5)   # los menores de 5 no existían
        else:
            uni = d.residente
        m = uni & s.str.len().eq(6)
        sub = pd.DataFrame({"origen": s[m], "destino": d.cod_ine[m]})
        if tipo == "trabajo":                    # acá el par va al revés
            sub = sub.rename(columns={"origen": "destino", "destino": "origen"})
        g = sub.groupby(["origen", "destino"], observed=True).size()
        g = g.reset_index(name="personas")
        g["tipo"] = tipo
        cual = "destino" if tipo == "trabajo" else "origen"
        g["nivel"] = g[cual].map(lambda c: nivel_de(c, espina))
        filas.append(g)
        tot, mun = g.personas.sum(), g.loc[g.nivel == "municipio", "personas"].sum()
        print(f"  {tipo:<12} {len(g):>7,} pares · {tot:>10,} personas · "
              f"{100*mun/tot:5.1f}% con municipio exacto", flush=True)

    f = pd.concat(filas, ignore_index=True)
    f.to_csv(AQUI / "flujos_2024.csv", index=False, encoding="utf-8")

    # ── indicadores municipales que SÍ son un número por municipio ───────────
    # Se emiten aparte para que los pueda consumir el mapa como cualquier otro.
    mun = f[f.nivel == "municipio"]
    out = {}
    for tipo in MATRICES:
        t = mun[mun.tipo == tipo]
        propio = t[t.origen == t.destino].set_index("destino").personas
        entran = t[t.origen != t.destino].groupby("destino").personas.sum()
        salen = t[t.origen != t.destino].groupby("origen").personas.sum()
        if tipo == "residencia5":
            # ★ saldo migratorio reciente: quién llegó menos quién se fue, en
            #   los cinco años previos al censo. Es el indicador que dice si un
            #   municipio gana o pierde gente, y en la región metropolitana es
            #   el corazón del asunto.
            out["inmigrantes_5a"] = entran
            out["emigrantes_internos_5a"] = salen
            out["saldo_migratorio"] = entran.sub(salen, fill_value=0)
        elif tipo == "nacimiento":
            out["inmigrantes_vida"] = entran
            out["emigrantes_internos_vida"] = salen
            out["saldo_migratorio_vida"] = entran.sub(salen, fill_value=0)
        else:
            # ★ población flotante: cuánta gente ENTRA a trabajar menos cuánta
            #   SALE. Positivo = el municipio recibe trabajadores de afuera.
            out["entran_a_trabajar"] = entran
            out["salen_a_trabajar"] = salen
            out["poblacion_flotante"] = entran.sub(salen, fill_value=0)
            out["trabajan_en_su_municipio"] = propio

    r = pd.DataFrame(out).reindex(sorted(espina)).fillna(0).astype("int64")
    r.index.name = "cod_ine"
    r.to_csv(AQUI / "flujos_municipal_2024.csv", encoding="utf-8")
    print(f"\n-> flujos_2024.csv ({len(f):,} filas) · "
          f"flujos_municipal_2024.csv ({len(r)} municipios)")

    print("\nSALDO MIGRATORIO RECIENTE (residencia hace 5 anios) - los 10 extremos")
    print("=" * 62)
    nom = {x["cod_ine"]: x["nombre"] for x in
           csv.DictReader(open(SPINE, encoding="utf-8"))}
    s = r.saldo_migratorio.sort_values()
    for ci in list(s.index[:5]) + list(s.index[-5:]):
        print(f"  {nom.get(ci, ci):<34}{s[ci]:>+9,}")


if __name__ == "__main__":
    main()
