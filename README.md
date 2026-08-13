# Motor de indicadores censales

Calcula indicadores de los **343 municipios de Bolivia** en los **dos censos
(2012 y 2024)** directamente desde el microdato, y **verifica cada uno contra el
tabulado publicado del INE**.

Empezó como un tablero de la región metropolitana de Santa Cruz. El recorte a los
9 municipios pasa en la última línea (`armar_metro.py`), así que el alcance real
es nacional: el Atlas Socioeconómico recalculado sale de la misma corrida.

## Cómo se corre

Desde `catalogo/`, en este orden:

```bash
python motor.py           # vivienda 2012+2024 (+ agregado urbano) · ~6 min
python motor_persona.py   # personas · minutos con las cachés calientes
python motor_nbi.py       # NBI, del Excel del INE · segundos
python motor_otros.py     # emigración y mortalidad · ~1 min
python motor_manzana.py   # nivel manzana, desde las fichas del geoportal
python motor_flujos.py    # matrices origen-destino (sólo 2024)

python chequeo.py         # puerta de sanidad — sale 1 si hay ERROR
python validar.py         # vivienda contra los tabulados del INE
python validar_persona.py # personas contra los tabulados
python armar_metro.py     # une todo y recorta a los 9 municipios
```

⚠️ **No correr dos motores a la vez**: la máquina se queda sin memoria.

Los microdatos no están en el repo. Se esperan en `C:\Users\HP\cpv2024`
(CPV 2024) y en la base Redatam del CPV 2012. La primera corrida construye
cachés en parquet; a partir de ahí es cuestión de minutos.

## Estado de la verificación

|  | resultado |
|---|---|
| vivienda, contra el INE | **100%** en los dos censos (25.382 y 20.923 comparaciones) |
| personas, contra el INE | 97,8% (2024) y 97,1% (2012) |
| indicadores con verificación externa | **111 de 210** |
| `chequeo.py` | sin errores |

★ **Los dos niveles de garantía no son lo mismo y conviene no fundirlos**: 111
indicadores reproducen el registro del INE municipio por municipio; los otros 99
son cálculo propio que pasa el chequeo de formas pero que nadie externo confirmó.
El INE no publica una hoja municipal para todo.

## Las piezas

| archivo | qué hace |
|---|---|
| `catalogo/catalogo.py` | **fuente única y declarativa**: agregar un indicador es agregar una fila |
| `catalogo/motor*.py` | vivienda · personas · NBI · otros · manzana · flujos |
| `catalogo/lector.py` | lector genérico de los tabulados del INE (143 de 145 hojas) |
| `catalogo/chequeo.py` | reconoce las *formas* de un indicador roto, no su valor |
| `catalogo/validar*.py` | contraste contra el registro del INE |
| `catalogo/generar_atlas.py` | regenera el `data.json` del Atlas nacional |
| `catalogo/barrido_atlas.py` | qué se mueve al reemplazar el Atlas, y con qué respaldo |

## Lo que hay que saber antes de tocarlo

- **Los códigos de respuesta CAMBIAN entre censos.** Escribir `combustible == 1`
  da "gas domiciliario" en 2012 y "garrafa" en 2024: no falla, devuelve otro
  indicador. Por eso hay una capa de armonización (`MAPEO`) y las reglas se
  escriben contra códigos canónicos con nombre.
- **La armonización va en la capa de REGLAS, no al derivar.** Las cachés guardan
  el código crudo de cada censo, así corregir una tabla no obliga a rehacerlas.
- **Lo que un censo no puede separar se declara**, no se fuerza: va vacío, nunca
  en 0%. Un 0 se lee como "no hay ninguno" y fabrica un cambio intercensal que
  nunca ocurrió.
- **`chequeo.py` no valida cifras, valida formas.** Una tasa de mortalidad de 33
  por mil no es "imposible" y pasaba el chequeo estando mal por un factor de 5.
  Sólo la comparación contra un registro externo la agarró.
- ⚠️ **Antes de tocar el motor, comparar los números.** Más de una vez el
  indicador estaba bien y el error estaba en el caso de validación.

## Divergencias abiertas con el INE

Documentadas, no escondidas:

- `paridez_media` — el universo del INE incluye a quienes no declararon; el
  nuestro no
- `prom_anios_estudio` 2012 — 238/343; el residuo está en el tramo superior
- `pct_hogar_unipersonal` — 301/343 dentro de 0,5 pp (universo de hogares)
- `tasa_ocupacion` / `tasa_participacion` — **divergen a propósito**: la base del
  INE cambia entre censos (7+ en 2024, 10+ en 2012) y adoptarla rompería la serie
