import streamlit as st
import pandas as pd
from backend import (
    calcular_pnl,
    extraer_columnas_validas,
    evaluar_distribuciones,
    calcular_efecto_economico_indirecto
)

# Configuración inicial de la app
st.set_page_config(page_title="Impacto Económico del Turismo Religioso", layout="wide")

# Font awesome
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

#Font awesome serviar siempre y cuando se use con st.markdown y unsafe_allow_html=True sino no renderiza el html

# Título
st.markdown("""
<div style="text-align:center; font-size:32px; margin-bottom:20px;">
  <i class="fas fa-church"></i> <strong>Análisis Económico del Turismo Religioso en Cartagena</strong>
</div>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("### <i class='fas fa-folder-open'></i> Carga los 4 archivos necesarios", unsafe_allow_html=True)
encuesta_file = st.sidebar.file_uploader(" Encuesta ", type=["xlsx", "csv"])
aforo_file = st.sidebar.file_uploader(" Potencial de Aforo ", type=["xlsx", "csv"])
eed_file = st.sidebar.file_uploader(" EED ", type=["xlsx", "csv"])
multi_file = st.sidebar.file_uploader(" Multiplicadores ", type=["xlsx", "csv"])

if encuesta_file and aforo_file and eed_file and multi_file:
    try:
        df_encuesta = pd.read_excel(encuesta_file) if encuesta_file.name.endswith(".xlsx") else pd.read_csv(encuesta_file)
        df_aforo = pd.read_excel(aforo_file) if aforo_file.name.endswith(".xlsx") else pd.read_csv(aforo_file)
        df_eed = pd.read_excel(eed_file) if eed_file.name.endswith(".xlsx") else pd.read_csv(eed_file)
        df_multi = pd.read_excel(multi_file) if multi_file.name.endswith(".xlsx") else pd.read_csv(multi_file)

        # Cálculo del PNL
        st.markdown("### <i class='fas fa-users'></i> Potencial de No Locales (PNL)", unsafe_allow_html=True)
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

        # Mapeo de columnas detectadas
        mapeo = extraer_columnas_validas(resultado_pnl["no_reside"])
        st.subheader("Mapeo de columnas detectadas")
        st.json(mapeo)

        # Pruebas de normalidad de encuestas no residentes.

        st.markdown("### <i class='fas fa-microscope'></i> Evaluación de distribución de variables", unsafe_allow_html=True)

        columnas_numericas = resultado_pnl["no_reside"].select_dtypes(include='number').columns.tolist()
        columnas_seleccionadas = st.multiselect(
            "Selecciona columnas para análisis estadístico",
            options=resultado_pnl["no_reside"].columns,
            default=[col for col in columnas_numericas if col not in ['orden', 'secuencia_p']]
        )

        if columnas_seleccionadas:
            from backend import evaluar_distribuciones  # importa la función nueva
            resultados_stats = evaluar_distribuciones(resultado_pnl["no_reside"], columnas_seleccionadas)

            df_resultados = pd.DataFrame(resultados_stats).T
            st.dataframe(df_resultados.style.format({
                "p_value": "{:.3f}",
                "media": "{:,.2f}",
                "mediana": "{:,.2f}"
            }))
        
        #Calculo de efecto economico indirecto
        st.markdown("### <i class='fas fa-chart-line'></i> Efecto Económico Indirecto", unsafe_allow_html=True)

        # Verificar columnas correctas en df_multi
        if not {"C_Sector", "Multiplicador intraregional para Bolívar"}.issubset(df_multi.columns):
            st.error("El archivo de multiplicadores no tiene las columnas necesarias.")
        else:
            # Selección de sector
            sector = st.selectbox(
                "Selecciona el sector para aplicar el multiplicador:",
                options=df_multi["C_Sector"].dropna().unique()
            )

            multiplicador_seleccionado = df_multi.loc[
                df_multi["C_Sector"] == sector, 
                "Multiplicador intraregional para Bolívar"
            ].values[0]

            resultado_indirecto, detalle_estadistico = calcular_efecto_economico_indirecto(
                resultado_pnl["no_reside"],
                resultado_pnl["PNL"],
                multiplicador=multiplicador_seleccionado
            )

            st.markdown(f"<i class='fas fa-industry'></i> Multiplicador aplicado: <strong>{multiplicador_seleccionado:.2f}</strong>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([resultado_indirecto]).T.rename(columns={0: "Valor"}).style.format("{:,.2f}"))

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
    st.warning("Por favor sube los 4 archivos: Encuesta, Aforo, EED y Multiplicadores.")