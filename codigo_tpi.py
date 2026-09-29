import math

SISS_LIMITE_HUMEDAD = 70.0  # % máximo de humedad para disposición en relleno (exigencia SISS)

# Fuente: Design Guidelines for Sewage Works, tabla 17-2, Ministerio del Medio Ambiente de Ontario
RANGOS_SEQUEDAD = {
    "activado": (12.0, 15.0),   # % sólidos, centrífuga con polímero, lodo activado (WAS)
    "digerido": (15.0, 30.0),   # % sólidos, lodo mezclado o digerido
}


def calcular_linea_base(q_in_m3h, solidos_in_pct):
    densidad_lodo = 1000.0  # kg/m3 (aproximado a lodo diluido)
    flujo_masico_in = q_in_m3h * densidad_lodo  # kg/h
    solidos_secos_in = flujo_masico_in * (solidos_in_pct / 100.0)  # kg MS/h

    captura_solidos = 0.96  # Eficiencia estándar de separación (96%)
    ms_recuperada = solidos_secos_in * captura_solidos

    humedad_base_pct = 85.0  # Línea base del filtro de banda actual
    ms_base_pct = 100.0 - humedad_base_pct
    torta_base_kgh = ms_recuperada / (ms_base_pct / 100.0)
    agua_torta_base_kgh = torta_base_kgh - ms_recuperada

    return {
        "flujo_masico_in": flujo_masico_in,
        "ms_recuperada": ms_recuperada,
        "torta_base_kgh": torta_base_kgh,
        "agua_torta_base_kgh": agua_torta_base_kgh,
    }


def estimar_sequedad(fuerza_g, tipo_lodo):
    rango_min, rango_max = RANGOS_SEQUEDAD[tipo_lodo]
    # Normaliza la fuerza G en el rango típico de decanters (1.000 a 5.000 G) a un factor 0-1
    factor_norm = math.log10(max(fuerza_g, 1000.0) / 1000.0) / math.log10(5.0)
    factor_norm = min(max(factor_norm, 0.0), 1.0)
    punto = rango_min + factor_norm * (rango_max - rango_min)
    return punto, rango_min, rango_max


def balance_maquina(ms_recuperada, flujo_masico_in, solidos_salida_pct):
    torta_kgh = ms_recuperada / (solidos_salida_pct / 100.0)
    agua_torta_kgh = torta_kgh - ms_recuperada
    agua_separada_kgh = flujo_masico_in - torta_kgh
    return torta_kgh, agua_torta_kgh, agua_separada_kgh


def evaluar_maquina(nombre, fuerza_g, potencia_kw, tarifa_kwh, horas_dia, tipo_lodo, q_in_m3h, base):
    punto, rango_min, rango_max = estimar_sequedad(fuerza_g, tipo_lodo)
    torta_kgh, agua_torta_kgh, agua_separada_kgh = balance_maquina(
        base["ms_recuperada"], base["flujo_masico_in"], punto
    )

    humedad_punto = 100.0 - punto
    humedad_min = 100.0 - rango_max  # mejor caso posible (mayor sequedad)
    humedad_max = 100.0 - rango_min  # peor caso posible (menor sequedad)

    if humedad_punto <= SISS_LIMITE_HUMEDAD:
        estado_siss = "CUMPLE"
    elif humedad_min <= SISS_LIMITE_HUMEDAD:
        estado_siss = "INCIERTO"
    else:
        estado_siss = "NO CUMPLE"

    reduccion_agua_pct = ((base["agua_torta_base_kgh"] - agua_torta_kgh) / base["agua_torta_base_kgh"]) * 100.0
    reduccion_peso_torta_pct = ((base["torta_base_kgh"] - torta_kgh) / base["torta_base_kgh"]) * 100.0

    factor_carga = 0.75  # Carga media de motor en régimen
    consumo_kwh_h = potencia_kw * factor_carga
    costo_electrico_dia = consumo_kwh_h * horas_dia * tarifa_kwh
    costo_electrico_mes = costo_electrico_dia * 30.0
    consumo_especifico_m3 = consumo_kwh_h / q_in_m3h

    return {
        "nombre": nombre,
        "solidos_punto": punto,
        "solidos_rango": (rango_min, rango_max),
        "humedad_punto": humedad_punto,
        "humedad_rango": (humedad_min, humedad_max),
        "estado_siss": estado_siss,
        "torta_kgh": torta_kgh,
        "agua_torta_kgh": agua_torta_kgh,
        "agua_separada_kgh": agua_separada_kgh,
        "reduccion_agua_pct": reduccion_agua_pct,
        "reduccion_peso_torta_pct": reduccion_peso_torta_pct,
        "consumo_especifico_m3": consumo_especifico_m3,
        "costo_electrico_mes": costo_electrico_mes,
        "horas_dia": horas_dia,
    }


def imprimir_reporte(r):
    print("\n" + "=" * 65)
    print(f"      RESULTADOS DE SIMULACIÓN: {r['nombre'].upper()}")
    print("=" * 65)
    print(f"• Sequedad estimada en torta:         {r['solidos_punto']:.2f} % "
          f"(rango literatura: {r['solidos_rango'][0]:.1f}-{r['solidos_rango'][1]:.1f} %)")
    print(f"• Humedad de salida estimada:         {r['humedad_punto']:.2f} % "
          f"(rango: {r['humedad_rango'][0]:.1f}-{r['humedad_rango'][1]:.1f} %)")
    print(f"• Exigencia SISS (<={SISS_LIMITE_HUMEDAD:.0f}% humedad):        {r['estado_siss']}")
    print("-" * 65)
    print(f"• Torta húmeda producida:             {r['torta_kgh']:.1f} kg/h  "
          f"({r['torta_kgh'] * r['horas_dia']:.1f} kg/día)")
    print(f"• Agua retenida en la torta:          {r['agua_torta_kgh']:.1f} kg/h")
    print(f"• Agua extraída mecánicamente:        {r['agua_separada_kgh']:.1f} kg/h (retorna a cabecera)")
    print("-" * 65)
    print("COMPARATIVA FRENTE AL FILTRO DE BANDA ACTUAL (Base 85% humedad):")
    print(f"• Variación de masa de agua a galpón: {r['reduccion_agua_pct']:+.1f} % "
          f"(positivo = reduce agua, negativo = empeora respecto al filtro actual)")
    print(f"• Variación de peso total de torta:   {r['reduccion_peso_torta_pct']:+.1f} % "
          f"(positivo = reduce peso, negativo = empeora respecto al filtro actual)")
    print("-" * 65)
    print("ESTIMACIÓN ENERGÉTICA DE OPERACIÓN:")
    print(f"• Consumo específico:                 {r['consumo_especifico_m3']:.2f} kWh/m3 procesado")
    print(f"• Gasto eléctrico mensual estimado:   ${r['costo_electrico_mes']:,.0f} CLP/mes "
          f"(a {r['horas_dia']:.1f} h/día)")
    print("=" * 65)


def imprimir_comparacion(resultados):
    print("\n" + "=" * 65)
    print("   TABLA COMPARATIVA DE EQUIPOS EVALUADOS")
    print("=" * 65)
    print(f"{'Equipo':<24}{'Sequedad %':<12}{'Humedad %':<12}{'SISS':<12}{'$/mes':>14}")
    print("-" * 65)
    for r in resultados:
        print(f"{r['nombre'][:23]:<24}{r['solidos_punto']:<12.2f}{r['humedad_punto']:<12.2f}"
              f"{r['estado_siss']:<12}{r['costo_electrico_mes']:>14,.0f}")
    print("=" * 65)


def simular_deshidratacion():
    print("=" * 65)
    print("   SIMULADOR TÉCNICO DE DESHIDRATACIÓN - AGUAS IZARRA S.A.   ")
    print("=" * 65)

    print("\n--- 1. CONDICIONES DEL LODO DE PLANTA ---")
    q_in_m3h = float(input("Caudal de alimentación de lodo (m3/h) [Ej: 3.0]: ") or 3.0)
    solidos_in_pct = float(input("Concentración de sólidos de entrada (% MS) [Ej: 1.0]: ") or 1.0)
    tipo_lodo_in = (input("Tipo de lodo: activado / digerido [Ej: activado]: ") or "activado").strip().lower()
    tipo_lodo = "digerido" if tipo_lodo_in.startswith(("dig", "mez")) else "activado"

    base = calcular_linea_base(q_in_m3h, solidos_in_pct)

    resultados = []
    while True:
        print("\n--- 2. DATOS DE LA MÁQUINA A EVALUAR ---")
        nombre_equipo = input("Nombre o modelo del equipo [Ej: HAUS DDE-2342]: ") or "Decanter Evaluado"
        fuerza_g = float(input("Fuerza Centrífuga declarada (G) [Ej: 3575]: ") or 3575)
        potencia_kw = float(input("Potencia instalada de placa (kW) [Ej: 9.7]: ") or 9.7)
        tarifa_kwh = float(input("Tarifa eléctrica ($/kWh) [Ej: 120]: ") or 120)
        horas_dia = float(input("Horas de operación diaria estimadas (h/día) [Ej: 3.0]: ") or 3.0)

        resultado = evaluar_maquina(
            nombre_equipo, fuerza_g, potencia_kw, tarifa_kwh, horas_dia, tipo_lodo, q_in_m3h, base
        )
        imprimir_reporte(resultado)
        resultados.append(resultado)

        otra = (input("\n¿Evaluar otra máquina para comparar? (s/n) [n]: ") or "n").strip().lower()
        if not otra.startswith("s"):
            break

    if len(resultados) > 1:
        imprimir_comparacion(resultados)


if __name__ == "__main__":
    simular_deshidratacion()
