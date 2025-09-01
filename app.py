import streamlit as st, numpy, pandas, sys
import importlib
import pandas as pd
import io
from backend import (
    calcular_pnl,
    extraer_columnas_validas,
    evaluar_distribuciones,
    calcular_efecto_economico_indirecto,
    detectar_categorias_motivo
)

# --- PRIMERO: configuración de página (debe ser el primer st.*) ---
st.set_page_config(page_title="Efectos económicos de los festivales y eventos", layout="wide")

# (Opcional) Diagnóstico de versiones: ahora sí, después del set_page_config
st.caption(f"Python: {sys.version.split()[0]}")
st.caption(f"NumPy: {numpy.__version__} | Pandas: {pandas.__version__}")
scipy_spec = importlib.util.find_spec("scipy")
st.caption("SciPy: OK" if scipy_spec else "SciPy: NO ENCONTRADO")

# Font awesome (también después del set_page_config)
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


if encuesta_file and aforo_file and eed_file:
    try:
        df_encuesta = pd.read_excel(encuesta_file) if encuesta_file.name.endswith(".xlsx") else pd.read_csv(encuesta_file)
        df_aforo = pd.read_excel(aforo_file) if aforo_file.name.endswith(".xlsx") else pd.read_csv(aforo_file)
        df_eed = pd.read_excel(eed_file) if eed_file.name.endswith(".xlsx") else pd.read_csv(eed_file)


        # Cálculo del PNL (modo flexible por motivo)
        st.markdown("### <i class='fas fa-users'></i> Potencial de No Locales (PNL)", unsafe_allow_html=True)

        # Columnas usadas
        col_reside = "¿Reside en la ciudad de Cartagena de Indias?"
        col_motivo = "¿Cuál fue el motivo de su viaje a la ciudad de Cartagena?"

        # Detectar categorías disponibles entre NO residentes
        try:
            conteos_motivos = detectar_categorias_motivo(
                df_encuesta,
                columna_reside=col_reside,
                columna_motivo=col_motivo
            )
            categorias_disponibles = conteos_motivos.index.tolist()
        except Exception as e:
            st.error(f"Error detectando categorías de motivo: {e}")
            categorias_disponibles = []

        # UI: selección de motivo principal y pesos
        if categorias_disponibles:
            cat_default = "venir a los eventos religiosos" if "venir a los eventos religiosos" in categorias_disponibles else categorias_disponibles[0]
            categoria_principal = st.selectbox(
                "Selecciona la categoría de motivo 'principal' para el ponderador",
                options=categorias_disponibles,
                index=categorias_disponibles.index(cat_default)
            )
        else:
            st.info("No se encontraron categorías de motivo entre NO residentes. Se usará selección automática en backend.")
            categoria_principal = None  # backend decide

        c1, c2 = st.columns(2)
        peso_principal = c1.number_input("Peso categoría principal", min_value=0.0, value=1.0, step=0.1, format="%.2f")
        peso_otros     = c2.number_input("Peso otras categorías / sin respuesta", min_value=0.0, value=0.5, step=0.1, format="%.2f")

        # ¿Hay >2 categorías? (solo entre NO residentes)
        hay_mas_de_dos = len(categorias_disponibles) > 2 if categorias_disponibles else False

        # Checkbox solo si hay >2 categorías
        activar_factor_correccion = False
        if hay_mas_de_dos:
            activar_factor_correccion = st.checkbox(
                'Se detectó > 2 categorías en la columna "¿Cuál fue el motivo de su viaje a la ciudad de Cartagena?" ¿Desea activar el factor de corrección?',
                value=False
            )

        # Cálculo FINAL con/ sin corrección según checkbox
        resultado_pnl = calcular_pnl(
            df_encuesta=df_encuesta,
            df_aforo=df_aforo,
            columna_reside=col_reside,
            columna_motivo=col_motivo,
            categoria_principal=categoria_principal,
            peso_principal=peso_principal,
            peso_otros=peso_otros,
            activar_factor_correccion=activar_factor_correccion
        )

        st.metric("PNL estimado", f"{resultado_pnl['PNL']:,.0f}")
        st.write("Detalles:")
        st.write({
            "Encuestados": resultado_pnl['total_encuestados'],
            "No residentes": resultado_pnl['total_no_reside'],
            "Motivo principal seleccionado": resultado_pnl['categoria_principal'],
            "Total motivo principal": resultado_pnl['total_motivo_seleccionado'],
            "Proporción turismo": f"{resultado_pnl['proporcion_turismo']:.2%}",
            "Ponderador": f"{resultado_pnl['ponderador']:.4f}",
            "Peso categoría principal (input)": f"{resultado_pnl['peso_principal']:.2f}",
            "Peso otras categorías (input)": f"{resultado_pnl['peso_otros']:.2f}",
            "N° categorías motivo (no residentes)": resultado_pnl.get("num_categorias_motivo", None),
            "Fracción 'otras' usada": f"{resultado_pnl.get('factor_correccion_aplicado', 0.0):.4f}",
            "Peso principal efectivo": f"{resultado_pnl.get('peso_principal_efectivo', peso_principal):.4f}",
            "Corrección activada": resultado_pnl.get("correccion_activada", False),
        })

        # Aviso visual si la corrección está activa
        if resultado_pnl.get("correccion_activada", False):
            st.warning(
                f"Corrección activada: se aplicó (peso_principal - fracción_otras) en el ponderador. "
                f"Peso principal efectivo = {resultado_pnl.get('peso_principal_efectivo', peso_principal):.4f}"
            )

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
            # --- Efecto económico directo total (desde EED) ---
            if "V_EED" in df_eed.columns:
                efecto_directo_total = pd.to_numeric(df_eed["V_EED"], errors="coerce").sum()
            else:
                st.warning("La columna 'V_EED' no existe en el archivo EED. No se puede calcular el efecto directo total.")
                efecto_directo_total = float("nan")

            # --- Efecto económico total = Directo + Indirecto + Inducido neto ---
            efecto_economico_total = (
                (resultado_indirecto["Efecto Indirecto Total"] or 0.0) +
                (resultado_indirecto["Efecto Inducido Neto Total"] or 0.0) +
                (efecto_directo_total if pd.notna(efecto_directo_total) else 0.0)
            )

            resumen = {
                "PNL": resultado_indirecto["PNL"],
                "Días de estadía (valor usado)": resultado_indirecto["Días de estadía (valor usado)"],
                "Multiplicador general": resultado_indirecto["Multiplicador general"],
                "Multiplicador alojamiento": resultado_indirecto["Multiplicador alojamiento"],
                "Multiplicador alimentación": resultado_indirecto["Multiplicador alimentación"],
                "Multiplicador transporte": resultado_indirecto["Multiplicador transporte"],
                "Efecto Directo Total (EED)": efecto_directo_total,
                "Efecto Indirecto Total": resultado_indirecto["Efecto Indirecto Total"],
                "Efecto Inducido Neto Total": resultado_indirecto["Efecto Inducido Neto Total"],
                "Efecto Económico Total": efecto_economico_total,
            }

            df_resumen = pd.DataFrame(resumen, index=["Valor"]).T

            # Formatear sólo numéricos
            def _fmt_num(x):
                try:
                    return f"{float(x):,.2f}"
                except (ValueError, TypeError):
                    return x

            df_resumen["Valor"] = df_resumen["Valor"].apply(_fmt_num)

            st.subheader("Resumen total")
            st.dataframe(df_resumen, use_container_width=True)

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
else:
        st.warning("Por favor sube los 3 archivos: Encuesta, Aforo y EED. (El archivo de multiplicadores es opcional y puedes descargar una plantilla en la barra lateral).")
