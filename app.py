import streamlit as st
import pandas as pd
import io
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

# --- Descarga del archivo de multiplicadores (local) ---
st.sidebar.markdown("### Archivo de multiplicadores")
st.sidebar.caption("Descarga el archivo de multiplicadores para editarlo y seleccionar sectores a conveniencia.")

try:
    with open("data/multiplicadores.xlsx", "rb") as f:
        bytes_xlsx = f.read()

    # Descargar el Excel original
    st.sidebar.download_button(
        label="Descargar multiplicadores",
        data=bytes_xlsx,
        file_name="multiplicadores.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Opción adicional: exportar como CSV
    df_multi_dl = pd.read_excel(io.BytesIO(bytes_xlsx))
    csv_norm = df_multi_dl.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Descargar como CSV",
        data=csv_norm,
        file_name="multiplicadores.csv",
        mime="text/csv"
    )

except FileNotFoundError:
    st.sidebar.warning("No se encontró 'data/multiplicadores.xlsx'. Verifica la ruta o usa la plantilla.")
    # Plantilla por si no existe el archivo
    plantilla = pd.DataFrame({
        "C_Sector": pd.Series(dtype="Int64"),
        "Sectores": pd.Series(dtype="string"),
        "Multiplicador intraregional para Bolívar": pd.Series(dtype="float")
    })
    csv_tpl = plantilla.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="Descargar plantilla (CSV)",
        data=csv_tpl,
        file_name="Multiplicadores_plantilla.csv",
        mime="text/csv"
    )

if encuesta_file and aforo_file and eed_file:
    try:
        df_encuesta = pd.read_excel(encuesta_file) if encuesta_file.name.endswith(".xlsx") else pd.read_csv(encuesta_file)
        df_aforo = pd.read_excel(aforo_file) if aforo_file.name.endswith(".xlsx") else pd.read_csv(aforo_file)
        df_eed = pd.read_excel(eed_file) if eed_file.name.endswith(".xlsx") else pd.read_csv(eed_file)


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
        st.markdown("### <i class='fas fa-chart-line'></i> Efectos Económicos ", unsafe_allow_html=True)

        # Usar directamente los stats ya calculados
        if "resultados_stats" not in locals():
            st.warning("Primero ejecuta la 'Evaluación de distribución' y selecciona las columnas.")
        else:
            opciones_cols = list(resultados_stats.keys())

            c1, c2 = st.columns(2)
            col_aloj  = c1.selectbox("Columna: gasto diario en alojamiento", opciones_cols)
            col_trans = c2.selectbox("Columna: gasto diario en transporte",  opciones_cols)
            col_alim  = c1.selectbox("Columna: gasto diario en alimentación", opciones_cols)
            col_dias  = c2.selectbox("Columna: días de estadía",             opciones_cols)

            # Multiplicadores: general y por rubro (manuales)
            c3, c4 = st.columns(2)
            m_general = c3.number_input(
                "Multiplicador general",
                min_value=0.0, value=1.0, step=0.01, format="%.4f"
            )
            st.caption("Ajusta los multiplicadores por rubro; por defecto toman el valor del general.")

            c5, c6, c7 = st.columns(3)
            m_aloj  = c5.number_input("Multiplicador alojamiento",  min_value=0.0, value=m_general, step=0.01, format="%.4f")
            m_alim  = c6.number_input("Multiplicador alimentación", min_value=0.0, value=m_general, step=0.01, format="%.4f")
            m_trans = c7.number_input("Multiplicador transporte",   min_value=0.0, value=m_general, step=0.01, format="%.4f")

            # Cálculo con multiplicadores por rubro
            resultado_indirecto, desglose = calcular_efecto_economico_indirecto(
                stats=resultados_stats,
                pnl=resultado_pnl["PNL"],
                multiplicador=m_general,  # general
                multiplicadores={
                    "alojamiento": m_aloj,
                    "alimentacion": m_alim,
                    "transporte": m_trans
                },
                col_aloj=col_aloj,
                col_alim=col_alim,
                col_trans=col_trans,
                col_dias=col_dias
            )

            st.markdown(
                f"<i class='fas fa-industry'></i> Multiplicadores → "
                f"General: <strong>{m_general:.4f}</strong> | "
                f"Aloj: <strong>{m_aloj:.4f}</strong> | "
                f"Alim: <strong>{m_alim:.4f}</strong> | "
                f"Transp: <strong>{m_trans:.4f}</strong>",
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

            # Resumen total
            resumen = {
                "PNL": resultado_indirecto["PNL"],
                "Días de estadía (valor usado)": resultado_indirecto["Días de estadía (valor usado)"],
                "Multiplicador general": resultado_indirecto["Multiplicador general"],
                "Multiplicador alojamiento": resultado_indirecto["Multiplicador alojamiento"],
                "Multiplicador alimentación": resultado_indirecto["Multiplicador alimentación"],
                "Multiplicador transporte": resultado_indirecto["Multiplicador transporte"],
                "Efecto Indirecto Total": resultado_indirecto["Efecto Indirecto Total"],
                "Efecto Inducido Neto Total": resultado_indirecto["Efecto Inducido Neto Total"],
            }
            df_resumen = pd.DataFrame(resumen, index=["Valor"]).T
            df_resumen["Valor"] = df_resumen["Valor"].apply(_fmt_num)

            st.subheader("Resumen total")
            st.dataframe(df_resumen, use_container_width=True)

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
        st.warning("Por favor sube los 3 archivos: Encuesta, Aforo y EED. (El archivo de multiplicadores es opcional y puedes descargar una plantilla en la barra lateral).")
