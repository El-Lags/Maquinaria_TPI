import altair as alt
import pandas as pd
import streamlit as st

from codigo_tpi import SISS_LIMITE_HUMEDAD, calcular_linea_base, evaluar_maquina

ESTADO_COLORES = {
    "CUMPLE": "#2E7D32",
    "INCIERTO": "#F9A825",
    "NO CUMPLE": "#C62828",
}

st.set_page_config(page_title="Simulador de Deshidratación — Aguas Izarra", layout="wide")
st.title("Simulador técnico de deshidratación — Aguas Izarra S.A.")

st.header("1. Condiciones del lodo de planta")
col1, col2, col3 = st.columns(3)
with col1:
    q_in_m3h = st.number_input("Caudal de alimentación de lodo (m3/h)", min_value=0.1, value=3.0, step=0.1)
with col2:
    solidos_in_pct = st.number_input("Concentración de sólidos de entrada (% MS)", min_value=0.1, value=2.0, step=0.1)
with col3:
    tipo_lodo_label = st.selectbox("Tipo de lodo", ["Activado (WAS)", "Digerido o mezclado"])
tipo_lodo = "digerido" if tipo_lodo_label.startswith("Digerido") else "activado"

base = calcular_linea_base(q_in_m3h, solidos_in_pct)

st.header("2. Máquinas a evaluar")

if "maquinas" not in st.session_state:
    st.session_state.maquinas = []

with st.form("nueva_maquina", clear_on_submit=True):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        nombre = st.text_input("Nombre / modelo", value="Decanter Evaluado")
    with c2:
        fuerza_g = st.number_input("Fuerza G", min_value=100.0, value=3575.0, step=1.0)
    with c3:
        potencia_kw = st.number_input("Potencia (kW)", min_value=0.1, value=9.7, step=0.1)
    with c4:
        tarifa_kwh = st.number_input("Tarifa ($/kWh)", min_value=1.0, value=120.0, step=1.0)
    with c5:
        horas_dia = st.number_input("Horas/día", min_value=0.1, value=6.0, step=0.5)
    submitted = st.form_submit_button("Agregar máquina", type="primary")
    if submitted:
        st.session_state.maquinas.append(
            {
                "nombre": nombre,
                "fuerza_g": fuerza_g,
                "potencia_kw": potencia_kw,
                "tarifa_kwh": tarifa_kwh,
                "horas_dia": horas_dia,
            }
        )

if st.session_state.maquinas and st.button("Limpiar máquinas"):
    st.session_state.maquinas = []
    st.rerun()

resultados = [
    evaluar_maquina(
        m["nombre"], m["fuerza_g"], m["potencia_kw"], m["tarifa_kwh"], m["horas_dia"], tipo_lodo, q_in_m3h, base
    )
    for m in st.session_state.maquinas
]

if not resultados:
    st.info("Agrega al menos una máquina para ver resultados.")
    st.stop()

st.header("3. Resultados por máquina")
for r in resultados:
    with st.expander(f"{r['nombre']} — {r['estado_siss']}", expanded=True):
        colA, colB, colC = st.columns(3)
        colA.metric("Sequedad estimada", f"{r['solidos_punto']:.2f} %")
        colA.caption(f"Rango literatura: {r['solidos_rango'][0]:.1f}-{r['solidos_rango'][1]:.1f} %")
        colB.metric("Humedad de salida", f"{r['humedad_punto']:.2f} %")
        colB.caption(f"Rango: {r['humedad_rango'][0]:.1f}-{r['humedad_rango'][1]:.1f} %")
        colC.metric("Exigencia SISS (≤70%)", r["estado_siss"])

        st.write(
            f"**Torta húmeda producida:** {r['torta_kgh']:.1f} kg/h "
            f"({r['torta_kgh'] * r['horas_dia']:.1f} kg/día)"
        )
        st.write(f"**Agua retenida en la torta:** {r['agua_torta_kgh']:.1f} kg/h")
        st.write(f"**Agua extraída mecánicamente:** {r['agua_separada_kgh']:.1f} kg/h")
        st.write(
            f"**Variación de masa de agua vs filtro de banda:** "
            f"{r['reduccion_agua_pct']:+.1f} % (positivo = mejora)"
        )
        st.write(
            f"**Variación de peso de torta vs filtro de banda:** "
            f"{r['reduccion_peso_torta_pct']:+.1f} % (positivo = mejora)"
        )
        st.write(f"**Consumo específico:** {r['consumo_especifico_m3']:.2f} kWh/m3")
        st.write(f"**Gasto eléctrico mensual:** ${r['costo_electrico_mes']:,.0f} CLP/mes")

st.header("4. Comparación")

df = pd.DataFrame(
    [
        {
            "Equipo": r["nombre"],
            "Sequedad %": round(r["solidos_punto"], 2),
            "Humedad %": round(r["humedad_punto"], 2),
            "SISS": r["estado_siss"],
            "Gasto mensual (CLP)": f"${r['costo_electrico_mes']:,.0f}",
        }
        for r in resultados
    ]
)
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Humedad de salida vs límite SISS")
chart_df = pd.DataFrame(
    {
        "Equipo": [r["nombre"] for r in resultados],
        "Humedad (%)": [r["humedad_punto"] for r in resultados],
        "Estado": [r["estado_siss"] for r in resultados],
    }
)

bars = (
    alt.Chart(chart_df)
    .mark_bar(size=40, cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X("Equipo:N", sort=None, title=None),
        y=alt.Y("Humedad (%):Q", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color(
            "Estado:N",
            scale=alt.Scale(domain=list(ESTADO_COLORES.keys()), range=list(ESTADO_COLORES.values())),
            legend=alt.Legend(title="Exigencia SISS"),
        ),
        tooltip=["Equipo", "Humedad (%)", "Estado"],
    )
)
labels = bars.mark_text(dy=-8, color="#3A3A3A").encode(text=alt.Text("Humedad (%):Q", format=".1f"))
limite = (
    alt.Chart(pd.DataFrame({"y": [SISS_LIMITE_HUMEDAD]}))
    .mark_rule(strokeDash=[6, 4], color="#3A3A3A")
    .encode(y="y:Q")
)
limite_label = (
    alt.Chart(pd.DataFrame({"y": [SISS_LIMITE_HUMEDAD], "label": [f"Límite SISS ({SISS_LIMITE_HUMEDAD:.0f}%)"]}))
    .mark_text(align="left", dx=6, dy=-6, color="#3A3A3A")
    .encode(y="y:Q", text="label")
)

st.altair_chart((bars + labels + limite + limite_label).properties(height=360), use_container_width=True)
