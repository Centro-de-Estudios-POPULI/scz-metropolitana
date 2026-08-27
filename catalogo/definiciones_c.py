# -*- coding: utf-8 -*-
"""QUÉ BUSCA MEDIR CADA INDICADOR — parte C: los 30 fiscales.

⛔ POR QUÉ ESTA PARTE LLEGÓ TARDE. Las partes A y B cubrieron los 237
   indicadores censales y se dio la tarea por cerrada, pero el tablero municipal
   tiene 243: los 30 fiscales NO pasaban por `describir()`. `armar_tableros.py`
   los copia tal cual del catálogo anterior —no salen del microdato censal sino
   de la ejecución presupuestaria del MEFP— y esa copia se saltaba tanto la
   descripción como el aviso de «sin definición declarada». O sea que el aviso
   existía, decía la verdad sobre lo que miraba, y no miraba estos.
   Resultado: los treinta seguían con el texto de origen, y ese texto es
   exactamente lo que se pidió quitar. El primero decía «Porcentaje del ingreso
   total que proviene de la Coparticipación Tributaria del TGN»: empieza por la
   fórmula, nombra el denominador y usa una sigla sin abrir.
   Arreglado en `armar_tableros.py`: el bloque fiscal ahora pasa por
   `describir()` como todos los demás.

★ MISMA REGLA DE ESCRITURA QUE EN A Y B (ver `definiciones_a.py`), con una
  precisión propia de lo fiscal: en un cociente el denominador NO es contabilidad
  sobrante, es el significado —«sobre el ingreso total» y «sobre el ingreso
  corriente» son dos preguntas distintas—, así que se nombra en castellano llano
  y no como partida. Las siglas se abren: nada de TGN, COFOG, RPF, F.1 ni ΔCxP.

★ DOS EXPRESIONES QUE SE REPITEN A PROPÓSITO, porque distinguen los dos bloques
  que el tablero separa y conviene que suenen igual siempre:
    · «todo el dinero que entra al municipio»  = ingreso total (con capital y deuda)
    · «el ingreso con que el municipio se sostiene año a año» = ingreso corriente
"""

DEF_C = {
# ── Fiscal · Estructura de Ingresos ─────────────────────────────────────────
"fi_cp_it": "Peso de la coparticipación tributaria que gira el Estado nacional dentro de todo el dinero que entra al municipio en el año; cuanto más alto, más depende de una decisión que se toma fuera.",
"fi_idh_it": "Peso de la renta de los hidrocarburos dentro de todo el dinero que entra al municipio en el año.",
"fi_rp_it": "Peso de lo que el municipio recauda por su cuenta —tasas, impuestos municipales y venta de bienes y servicios— dentro de todo el dinero que le entra.",
"fi_rc_it": "Peso de las regalías y de las transferencias destinadas a obras dentro de todo el dinero que entra al municipio en el año.",
"fi_rc_ic": "Tamaño de los recursos destinados a obras frente al ingreso con que el municipio se sostiene año a año; muestra cuánto de lo que construye descansa en plata que puede no repetirse.",

# ── Fiscal · Sostenibilidad de Ing. Corrientes ──────────────────────────────
"fi_cp_ic": "Peso de la coparticipación del Estado nacional dentro del ingreso con que el municipio se sostiene año a año, dejando fuera obras y deuda.",
"fi_idh_ic": "Peso de la renta de los hidrocarburos dentro del ingreso con que el municipio se sostiene año a año.",
"fi_rp_ic": "Peso de la recaudación propia dentro del ingreso con que el municipio se sostiene año a año; es la medida más exigente de autonomía fiscal.",

# ── Fiscal · Estructura del Gasto ───────────────────────────────────────────
"fi_gc_gt": "Peso de lo que cuesta hacer funcionar el municipio —sueldos, bienes, servicios y transferencias— dentro de todo lo que gasta; cuanto más alto, menos margen queda para obras.",
"fi_ge_gt": "Peso de las obras y el equipamiento dentro de todo lo que gasta el municipio.",
"fi_f1_gt": "Peso del pago de créditos con bancos y tenedores de bonos dentro de todo lo que gasta el municipio.",
"fi_f2_gt": "Peso del pago de cuentas que quedaron pendientes de gestiones anteriores dentro de todo lo que gasta el municipio.",

# ── Fiscal · Gasto por Sectores ─────────────────────────────────────────────
# El denominador de este bloque no es el gasto total sino la parte del gasto que
# está repartida entre sectores: por eso se nombra así y no «del gasto».
"fi_s_adm": "Parte del gasto repartido entre sectores que se va en administrar el municipio.",
"fi_s_edu": "Parte del gasto repartido entre sectores que se destina a educación: escuelas, equipamiento y programas educativos.",
"fi_s_sal": "Parte del gasto repartido entre sectores que se destina a salud: centros, hospitales y equipamiento médico.",
"fi_s_eco": "Parte del gasto repartido entre sectores que se destina a la economía local: agricultura, transporte, energía, industria y comercio.",
"fi_s_viv": "Parte del gasto repartido entre sectores que se destina a vivienda e infraestructura urbana: agua, alcantarillado, urbanismo y construcción.",
"fi_s_prt": "Parte del gasto repartido entre sectores que se destina a protección social: adultos mayores, programas sociales y atención a grupos vulnerables.",
"fi_s_seg": "Parte del gasto repartido entre sectores que se destina a seguridad: policía municipal, bomberos y defensa civil.",
"fi_s_med": "Parte del gasto repartido entre sectores que se destina a medio ambiente: recojo de residuos, parques y saneamiento.",
"fi_s_cul": "Parte del gasto repartido entre sectores que se destina a cultura, deporte y recreación.",

# ── Fiscal · Per Cápita ─────────────────────────────────────────────────────
"fi_it_pc": "Dinero que entra al municipio en el año por cada habitante.",
"fi_sl_pc": "Dinero que el municipio gasta en salud por cada habitante.",
"fi_ed_pc": "Dinero que el municipio gasta en educación por cada habitante.",
"fi_inv_pc": "Dinero que el municipio destina a obras y equipamiento por cada habitante.",
"fi_ic_pc": "Dinero con que el municipio se sostiene año a año, por cada habitante; deja fuera lo que llega para obras y lo que llega como deuda.",

# ── Fiscal · Resultado Fiscal ───────────────────────────────────────────────
"fi_rpf_ic": "Cuánto le sobró o le faltó al municipio en el año antes de tocar deuda, comparado con el ingreso con que se sostiene; en negativo, gastó más de lo que generó.",
"fi_dcj_ic": "Cuánto le sobró o le faltó al municipio en el año una vez pagadas las deudas que vencían, comparado con el ingreso con que se sostiene.",
"fi_f1_it": "Peso del pago de créditos con bancos y tenedores de bonos dentro de todo el dinero que entra al municipio.",
"fi_op_it": "Cuánto creció o bajó en el año lo que el municipio debe a sus proveedores, comparado con todo el dinero que le entra; en positivo, está postergando pagos.",
}
