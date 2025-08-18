import streamlit as st
import pandas as pd
from backend import (
    calcular_pnl,
    extraer_columnas_validas,
    evaluar_distribuciones,
    calcular_efecto_economico_indirecto
)

# Configuración inicial de la app
st.set_page_config(page_title="Efectos económicos de los festivales y eventos", layout="wide")

# Font awesome
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

#Font awesome serviar siempre y cuando se use con st.markdown y unsafe_allow_html=True sino no renderiza el html

# Título
st.markdown("""
<div style="text-align:center; font-size:32px; margin-bottom:20px;">
  <i class="fa fa-angle-double-right" aria-hidden="true"></i>
 <strong>Efectos económicos de los festivales y eventos</strong>
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

        # Verificar columnas correctas en df_multi (selección por NOMBRE de sector)
        if not {"Sectores", "Multiplicador intraregional para Bolívar"}.issubset(df_multi.columns):
            st.error("El archivo de multiplicadores debe incluir las columnas 'Sectores' y 'Multiplicador intraregional para Bolívar'.")
        else:
            # Selección de sector por nombre
            opciones_sectores = sorted(df_multi["Sectores"].dropna().astype(str).unique())
            sector_nombre = st.selectbox(
                "Selecciona el sector para aplicar el multiplicador:",
                options=opciones_sectores
            )
            multiplicador_seleccionado = pd.to_numeric(
                df_multi.loc[
                    df_multi["Sectores"].astype(str).str.strip() == sector_nombre,
                    "Multiplicador intraregional para Bolívar"
                ].iloc[0],
                errors="coerce"
            )

            if pd.isna(multiplicador_seleccionado):
                st.error("El multiplicador seleccionado no es numérico. Revisa el archivo de multiplicadores.")
            else:
                # --- Usar los stats ya calculados arriba ---
                if "resultados_stats" not in locals():
                    st.warning("Primero ejecuta la 'Evaluación de distribución' y selecciona las columnas.")
                else:
                    opciones_cols = list(resultados_stats.keys())

                    c1, c2 = st.columns(2)
                    col_aloj  = c1.selectbox("Columna: gasto diario en alojamiento", opciones_cols)
                    col_trans = c2.selectbox("Columna: gasto diario en transporte",  opciones_cols)
                    col_alim  = c1.selectbox("Columna: gasto diario en alimentación", opciones_cols)
                    col_dias  = c2.selectbox("Columna: días de estadía",             opciones_cols)

                    resultado_indirecto, desglose = calcular_efecto_economico_indirecto(
                    stats=resultados_stats,
                    pnl=resultado_pnl["PNL"],
                    multiplicador=float(multiplicador_seleccionado),
                    col_aloj=col_aloj,
                    col_alim=col_alim,
                    col_trans=col_trans,
                    col_dias=col_dias
                )

                st.markdown(
                    f"<i class='fas fa-industry'></i> Sector: <strong>{sector_nombre}</strong> — "
                    f"Multiplicador: <strong>{float(multiplicador_seleccionado):.4f}</strong>",
                    unsafe_allow_html=True
                )

                # ---- Tablas de salida ----
                def _fmt_num(x):
                    try:
                        return f"{float(x):,.2f}"
                    except (ValueError, TypeError):
                        return x

                # Desglose por rubro (Indirecto vs Inducido neto)
                df_desglose = pd.DataFrame(desglose, columns=["Rubro", "Gasto diario usado", "Indirecto", "Inducido neto"])
                for c in ["Gasto diario usado", "Indirecto", "Inducido neto"]:
                    df_desglose[c] = df_desglose[c].apply(_fmt_num)

                st.subheader("Desglose por rubro")
                st.dataframe(df_desglose, use_container_width=True)

                # Resumen total y trazabilidad de métodos
                resumen = {
                    "PNL": resultado_indirecto["PNL"],
                    "Días de estadía (valor usado)": resultado_indirecto["Días de estadía (valor usado)"],
                    "Multiplicador": resultado_indirecto["Multiplicador"],
                    "Efecto Indirecto Total": resultado_indirecto["Efecto Indirecto Total"],
                    "Efecto Inducido Neto Total": resultado_indirecto["Efecto Inducido Neto Total"],
                    "Método alojamiento": resultado_indirecto["Método alojamiento"],
                    "Método alimentación": resultado_indirecto["Método alimentación"],
                    "Método transporte": resultado_indirecto["Método transporte"],
                    "Método días": resultado_indirecto["Método días"],
                }
                df_resumen = pd.DataFrame(resumen, index=["Valor"]).T
                df_resumen["Valor"] = df_resumen["Valor"].apply(_fmt_num)

                st.subheader("Resumen total")
                st.dataframe(df_resumen, use_container_width=True)

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
    st.warning("Por favor sube los 4 archivos: Encuesta, Aforo, EED y Multiplicadores.")