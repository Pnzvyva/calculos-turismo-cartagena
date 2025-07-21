import streamlit as st
import pandas as pd
from backend import (
    calcular_pnl,
    calcular_efecto_indirecto,
    calcular_efecto_inducido
)

st.set_page_config(page_title="Impacto Económico del Turismo Religioso", layout="wide")
st.title("📊 Análisis Económico del Turismo Religioso en Cartagena")

# --- Subir archivos (ahora sí los 4 necesarios) ---
st.sidebar.header("📁 Carga los 4 archivos necesarios")
encuesta_file = st.sidebar.file_uploader("📋 Encuesta", type=["xlsx", "csv"])
aforo_file = st.sidebar.file_uploader("🏟️ Potencial de Aforo por evento", type=["xlsx", "csv"])
eed_file = st.sidebar.file_uploader("📊 EED por sector", type=["xlsx", "csv"])
multi_file = st.sidebar.file_uploader("🧮 Multiplicadores por sector", type=["xlsx", "csv"])

criterio = st.sidebar.radio("¿Qué estadístico usar para los efectos económicos?", ["Mediana", "Promedio"])

# Verificar que se hayan cargado todos los archivos necesarios
if encuesta_file and aforo_file and eed_file and multi_file:
    try:
        # Leer archivos según extensión
        df_encuesta = pd.read_excel(encuesta_file) if encuesta_file.name.endswith(".xlsx") else pd.read_csv(encuesta_file)
        df_aforo = pd.read_excel(aforo_file) if aforo_file.name.endswith(".xlsx") else pd.read_csv(aforo_file)
        df_eed = pd.read_excel(eed_file) if eed_file.name.endswith(".xlsx") else pd.read_csv(eed_file)
        df_multi = pd.read_excel(multi_file) if multi_file.name.endswith(".xlsx") else pd.read_csv(multi_file)

        # 🧮 Cálculo del PNL
        st.subheader("📌 Potencial de No Locales (PNL)")
        resultado_pnl = calcular_pnl(df_encuesta, df_aforo)
        st.metric("PNL estimado", f"{resultado_pnl['PNL']:,.0f}")
        st.write("Detalles:")
        st.write({
            "Encuestados": resultado_pnl['total_encuestados'],
            "No residentes": resultado_pnl['total_no_reside'],
            "Religioso": resultado_pnl['total_religioso'],
            "Ocio": resultado_pnl['total_ocio'],
            "Otros/Sin respuesta": resultado_pnl['total_otros'],
            "Proporción turismo": f"{resultado_pnl['proporcion_turismo']:.2%}",
            "Ponderador": f"{resultado_pnl['ponderador']:.2f}"
        })

        # 🧮 Cálculo del efecto económico indirecto
        st.subheader("💵 Efecto Económico Indirecto")
        efecto_indirecto, valores = calcular_efecto_indirecto(
            resultado_pnl["no_reside"], resultado_pnl["PNL"], criterio
        )
        st.write("Estadísticos usados:")
        st.dataframe(pd.DataFrame(valores, index=["Valor"]).T)
        st.success(f"**Efecto económico indirecto estimado: ${efecto_indirecto:,.2f}**")

        # 🧮 Cálculo del efecto inducido
        st.subheader("💼 Efecto Económico Inducido Neto por Sector")
        df_completo = df_eed.merge(df_multi, on="C_Sector", how="left")
        df_inducido = calcular_efecto_inducido(df_completo, efecto_indirecto)
        st.dataframe(df_inducido)

        # Descargar
        st.download_button(
            label="📥 Descargar resultados",
            data=df_inducido.to_csv(index=False).encode("utf-8"),
            file_name="efecto_inducido_por_sector.csv",
            mime="text/csv"
        )

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
    st.warning("Por favor sube los 4 archivos: Encuesta, Aforo, EED y Multiplicadores.")