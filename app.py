import streamlit as st
import pandas as pd

# Título
st.title("Análisis Económico de Eventos de Turismo Religioso")

# Subida de archivos
st.sidebar.header("Subir Archivos")
efecto_directo_file = st.sidebar.file_uploader("Efecto Económico Directo (.xlsx)", type=["xlsx"])
multiplicadores_file = st.sidebar.file_uploader("Multiplicadores (.xlsx)", type=["xlsx"])
encuesta_file = st.sidebar.file_uploader("Encuesta (.xlsx)", type=["xlsx"])
aforo_file = st.sidebar.file_uploader("Potencial de Aforo (.xlsx)", type=["xlsx"])

# Si todos los archivos se suben
if efecto_directo_file and multiplicadores_file and encuesta_file and aforo_file:
    # Cargar datos
    df_directo = pd.read_excel(efecto_directo_file)
    df_multi = pd.read_excel(multiplicadores_file)
    df_encuesta = pd.read_excel(encuesta_file)
    df_aforo = pd.read_excel(aforo_file)

    # Mostrar una muestra de datos
    st.subheader("Vista previa de Efecto Económico Directo")
    st.write(df_directo.head())

    # Selección de evento
    eventos = df_aforo['Evento'].unique()
    evento_seleccionado = st.selectbox("Selecciona el Evento:", eventos)

    # Filtrar datos de aforo según evento
    aforo_evento = df_aforo[df_aforo['Evento'] == evento_seleccionado]

    # Ejemplo de cálculo (ajusta fórmulas según tus datos reales)
    df_resultados = df_directo.copy()
    df_resultados = df_resultados.merge(df_multi, on=['Codigo','Nombre'])

    # Efecto Indirecto = Ventas * Multiplicador
    df_resultados['Efecto_Indirecto'] = df_resultados['Ventas'] * df_resultados['Multiplicador']

    # Efecto Inducido Neto = Ventas * % aforo (ejemplo)
    porc_aforo = aforo_evento['Porcentaje'].values[0] / 100
    df_resultados['Efecto_Inducido'] = df_resultados['Ventas'] * porc_aforo

    # Efecto Total
    df_resultados['Efecto_Total'] = df_resultados['Ventas'] + df_resultados['Efecto_Indirecto'] + df_resultados['Efecto_Inducido']

    # Conversión a millones de pesos
    for col in ['Ventas', 'Efecto_Indirecto', 'Efecto_Inducido', 'Efecto_Total']:
        df_resultados[col] = df_resultados[col] / 1e6

    # Cálculo de porcentajes
    totales = df_resultados[['Ventas','Efecto_Indirecto','Efecto_Inducido','Efecto_Total']].sum()
    df_resultados['% Directo'] = (df_resultados['Ventas'] / totales['Ventas']) * 100
    df_resultados['% Indirecto'] = (df_resultados['Efecto_Indirecto'] / totales['Efecto_Indirecto']) * 100
    df_resultados['% Inducido'] = (df_resultados['Efecto_Inducido'] / totales['Efecto_Inducido']) * 100
    df_resultados['% Total'] = (df_resultados['Efecto_Total'] / totales['Efecto_Total']) * 100

    # Mostrar tabla de resultados
    st.subheader(f"Resultados del Evento: {evento_seleccionado}")
    st.dataframe(df_resultados)

    # Descargar CSV
    csv = df_resultados.to_csv(index=False).encode()
    st.download_button("Descargar CSV", data=csv, file_name="resultados_evento.csv")

else:
    st.warning("Por favor sube los 4 archivos requeridos.")
