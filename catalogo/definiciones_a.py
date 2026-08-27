# -*- coding: utf-8 -*-
"""QUÉ BUSCA MEDIR CADA INDICADOR — parte A.

★ PEDIDO DE CARLOS (2026-08-26): «que se entienda solo leyendo qué nos muestra
  el gráfico. Algunas incluso hoy tienen fórmulas o hablan de la metodología; no
  es la idea, la idea es que nos muestre qué se busca medir».

  La descripción que llegaba a la tarjeta era el título repetido más el
  denominador: «Acceso a fuente mejorada. Porcentaje sobre las viviendas
  particulares ocupadas». Eso es contabilidad, no significado: dice sobre qué se
  divide pero no qué se está mirando ni por qué importa.

★ LA REGLA DE ESCRITURA, para que las 237 suenen a lo mismo:
  1. Una frase. Empieza por el SUJETO que se cuenta, no por el título.
  2. Dice qué entra y qué no cuando el recorte no es obvio.
  3. Si el número tiene una lectura —qué significa que suba o que baje— va al
     final, después de un punto y coma o un guion.
  4. NADA de variables, códigos, denominadores ni fórmulas: el universo ya viaja
     aparte y el motor de cálculo vive en el catálogo.
  5. Se escribe contra la expresión real (`e24`) del catálogo, no contra el
     título: varios títulos prometen más de lo que el dato mide.
"""

DEF_A = {
# ── Demografía y estructura ─────────────────────────────────────────────────
"pob_total": "Todas las personas censadas que viven en el municipio.",
"pob_hombres": "Personas censadas que se declararon hombres.",
"pob_mujeres": "Personas censadas que se declararon mujeres.",
"crec_intercensal": "Cuánto creció la población cada año entre los dos censos; es la velocidad del cambio, no su tamaño.",
"pct_0_4": "Niñas y niños que todavía no llegan a la edad escolar; marcan la demanda de salas cuna, vacunas y control infantil.",
"pct_0_14": "Población en edad escolar o menor a ella.",
"pct_menor20": "Población que aún no cumplió veinte años.",
"pct_15_29": "Personas jóvenes, la franja que entra al mercado de trabajo y a la educación superior.",
"pct_15_64": "Población en edades típicamente activas; es el grupo que sostiene económicamente a los otros dos.",
"pct_60_mas": "Personas de sesenta años o más.",
"pct_65_mas": "Personas adultas mayores.",
"pct_80_mas": "Personas de ochenta años o más, la franja de mayor dependencia de cuidados.",
"edad_mediana": "La edad que parte a la población en dos mitades iguales; sube cuando el municipio envejece.",
"edad_promedio": "El promedio simple de las edades. A diferencia de la mediana, se estira cuando hay muchas personas mayores.",
"indice_masculinidad": "Cuántos hombres hay por cada cien mujeres. Por encima de cien indica una población masculinizada, algo típico de zonas de trabajo agrícola o industrial.",
"razon_dependencia": "Cuántas personas en edades dependientes —menores de quince y de sesenta y cinco o más— hay por cada cien en edad activa.",
"dep_juvenil": "Cuántos menores de quince años hay por cada cien personas en edad activa.",
"dep_senil": "Cuántas personas de sesenta y cinco o más hay por cada cien en edad activa.",
"indice_envejecimiento": "Cuántas personas mayores hay por cada cien niñas y niños; cruzar cien significa que ya hay más viejos que chicos.",
"indice_juventud": "Qué peso tienen las personas jóvenes dentro de la población total.",
"pct_urbano": "Viviendas que el censo ubicó en área urbana. Es la medida de cuánto del municipio es ciudad y cuánto es campo.",
"densidad": "Cuántas personas viven por hectárea. Distingue el tejido compacto del disperso mucho mejor que la población total.",
"pct_20_39": "Población adulta joven.",
"pct_40_59": "Población adulta madura.",

# ── Hogares y jefatura ──────────────────────────────────────────────────────
"tam_hogar": "Cuántas personas viven, en promedio, en cada hogar.",
"pct_hogar_unipersonal": "Hogares formados por una sola persona.",
"pct_hogar_nuclear": "Hogares formados por una pareja, con hijas e hijos o sin ellos.",
"pct_hogar_monoparental": "Hogares donde una sola persona adulta está a cargo de sus hijas e hijos.",
"pct_hogar_extendido": "Hogares donde al núcleo familiar se suman otros parientes: abuelos, tíos, nietos.",
"pct_hogar_compuesto": "Hogares que además de parientes incluyen a personas sin parentesco.",
"pct_jefatura_femenina": "Hogares donde la persona reconocida como jefa es una mujer.",
"pct_hogar_con_menores": "Hogares donde vive al menos una niña o un niño menor de quince años.",
"pct_hogar_con_am": "Hogares donde vive al menos una persona de sesenta y cinco años o más.",
"pct_am_solo": "Personas mayores que viven solas; es una señal directa de necesidad de cuidados y de riesgo de aislamiento.",
"pct_hogar_sin_jefe": "Hogares en los que nadie fue declarado como jefa o jefe.",

# ── Agua ────────────────────────────────────────────────────────────────────
"pct_agua_caneria": "Viviendas cuya agua llega desde una red pública de cañerías.",
"pct_agua_interior": "Viviendas donde el agua sale de una llave dentro de la casa, no del patio ni del lote.",
"pct_agua_lote": "Viviendas donde el agua llega por cañería pero la llave está fuera de la casa, dentro del terreno.",
"pct_agua_sin_caneria": "Viviendas donde el agua no llega por cañería: hay que ir a buscarla o esperar que la traigan.",
"pct_agua_pileta": "Viviendas que se abastecen de una pileta pública compartida.",
"pct_agua_pozo": "Viviendas que sacan su agua de un pozo, con bomba o sin ella.",
"pct_agua_pozo_bomba": "Viviendas con pozo perforado y bomba, que es la forma protegida de usar agua subterránea.",
"pct_agua_rio": "Viviendas que toman el agua directamente de un río, una acequia o una vertiente sin proteger.",
"pct_agua_carro": "Viviendas que le compran el agua a un carro repartidor. Suele ser la opción más cara por litro.",
"pct_agua_lluvia": "Viviendas que recogen agua de lluvia como fuente principal.",
"pct_agua_no_mejorada": "Viviendas cuya agua viene de una fuente que no garantiza potabilidad: pozo sin proteger, río o carro repartidor.",
"pct_agua_mejorada": "Viviendas con agua de una fuente que el INE considera segura. Es la medida básica de si el hogar puede beber sin riesgo.",
"pct_agua_vertiente": "Viviendas abastecidas por una vertiente, esté protegida o no.",

# ── Saneamiento ─────────────────────────────────────────────────────────────
"pct_servicio_sanitario": "Viviendas que tienen baño o letrina, sea propio o compartido.",
"pct_sanitario_exclusivo": "Viviendas cuyo baño usa sólo el hogar que vive ahí.",
"pct_sanitario_compartido": "Viviendas que comparten el baño con otros hogares.",
"pct_sin_sanitario": "Viviendas sin baño ni letrina de ningún tipo.",
"pct_alcantarillado": "Viviendas conectadas a la red de alcantarillado. Es lo que distingue a la ciudad servida de la que se expandió sin red.",
"pct_camara_septica": "Viviendas cuyo desagüe va a una cámara séptica, la solución habitual donde no llegó la red.",
"pct_pozo_ciego": "Viviendas cuyo desagüe descarga en un pozo ciego, sin tratamiento.",
"pct_desague_superficie": "Viviendas que descargan el desagüe a la calle, una quebrada o un río; es la situación de mayor riesgo sanitario.",
"pct_sin_desague": "Viviendas sin ninguna instalación de desagüe.",
"pct_saneamiento_mejorado": "Viviendas con baño propio y desagüe a red o cámara séptica: las dos condiciones juntas, que es lo que evita el contacto con excretas.",

# ── Energía y cocina ────────────────────────────────────────────────────────
"pct_electricidad": "Viviendas con energía eléctrica de cualquier fuente: red, generador o panel solar.",
"pct_elec_red": "Viviendas conectadas al servicio público de electricidad.",
"pct_panel_solar": "Viviendas que resuelven la electricidad con panel solar, casi siempre porque la red no llegó.",
"pct_motor_propio": "Viviendas que generan su propia electricidad con motor.",
"pct_sin_energia": "Viviendas sin electricidad de ninguna fuente.",
"pct_gas_red": "Viviendas con gas domiciliario por cañería, la forma más barata y segura de cocinar.",
"pct_gas_garrafa": "Viviendas que cocinan con garrafa, que obliga a comprarla y trasladarla.",
"pct_lena_guano": "Viviendas que cocinan con leña, guano o bosta. Es la principal fuente de humo dentro de la casa y afecta sobre todo a quien cocina.",
"pct_combustible_limpio": "Viviendas que cocinan sin combustión de biomasa: gas, electricidad o energía solar.",
"pct_cocina_exclusiva": "Viviendas con un cuarto destinado sólo a cocinar, separado de donde se duerme.",
"pct_no_cocina": "Viviendas donde no se cocina.",
"pct_cocina_electricidad": "Viviendas que cocinan con electricidad.",
"pct_cocina_solar": "Viviendas que cocinan con energía solar.",

# ── Residuos ────────────────────────────────────────────────────────────────
"pct_basura_formal": "Viviendas cuya basura entra al sistema de recojo, sea por carro o por contenedor.",
"pct_basura_carro": "Viviendas que entregan la basura al carro recolector.",
"pct_basura_contenedor": "Viviendas que dejan la basura en un contenedor o basurero público.",
"pct_basura_quema": "Viviendas que queman su basura.",
"pct_basura_entierra": "Viviendas que entierran su basura.",
"pct_basura_informal": "Viviendas que botan la basura a un terreno baldío, la calle o el río; es lo que termina en los cursos de agua.",
}
