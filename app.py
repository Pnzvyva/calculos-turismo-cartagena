import streamlit as st
import pandas as pd
from scipy.stats import shapiro
import backend

# Título principal
st.title("Análisis Económico de Eventos de Turismo Religioso")

# Subida de archivos
st.sidebar.header("Subir Archivos")
eed_file = st.sidebar.file_uploader("Efecto Económico Directo (EED.xlsx)", type=["xlsx"])
multi_file = st.sidebar.file_uploader("Multiplicadores (Multiplicador.xlsx)", type=["xlsx"])
encuesta_file = st.sidebar.file_uploader("Encuesta (S123...EXCEL.xlsx)", type=["xlsx"])
aforo_file = st.sidebar.file_uploader("Potencial de Aforo (Potencial de aforo.xlsx)", type=["xlsx"])

# Criterio de cálculo
criterio = st.sidebar.selectbox("Criterio de cálculo para gastos:", ["Mediana", "Promedio"])

# Si todos los archivos están subidos
if eed_file and multi_file and encuesta_file and aforo_file:

    # Leer archivos
    df_eed = pd.read_excel(eed_file, engine="openpyxl")
    df_multi = pd.read_excel(multi_file, engine="openpyxl")
    df_encuesta = pd.read_excel(encuesta_file, engine="openpyxl")
    df_aforo = pd.read_excel(aforo_file, engine="openpyxl")

    # Mostrar evento a seleccionar
    eventos = df_aforo["Evento"].unique()
    evento_seleccionado = st.selectbox("Selecciona el Evento:", eventos)

    # Filtrar aforo del evento
    aforo_evento = df_aforo[df_aforo["Evento"] == evento_seleccionado]
    potencial_aforo = aforo_evento["Potencial de aforo"].sum()

    st.write(f"**Potencial de aforo del evento seleccionado:** {potencial_aforo:,.0f}")

    # Efecto Económico Directo
    df_directo = df_eed.copy()
    suma_efecto_directo = df_directo["V_EED"].sum()
    st.write(f"**Suma total de efecto económico directo:** ${suma_efecto_directo:,.0f}")

    # 🔹 ESTIMACIÓN DEL PNL con limpieza y detalle

    st.subheader("Cálculo Detallado del Factor de Población (PNL)")

    # 🔹 1. Filtrar encuestados con respuesta "Sí" o "No"
    df_encuesta_responde = df_encuesta[
        df_encuesta["¿Reside en la ciudad de Cartagena de Indias?"]
        .str.strip()
        .str.lower()
        .isin(["sí", "si", "no"])
    ]

    total_encuestados = df_encuesta_responde.shape[0]
    st.write(f"Total de encuestados que respondieron residencia (sí/no): **{total_encuestados}**")

    # 🔹 2. Potencial de aforo = suma de todos los eventos
    potencial_aforo = df_aforo["Potencial de aforo"].sum()
    st.write(f"Potencial de aforo (suma de todos los eventos): **{potencial_aforo:,.0f}**")

    # 🔹 3. Filtrar NO residentes
    no_reside = df_encuesta_responde[
        df_encuesta_responde["¿Reside en la ciudad de Cartagena de Indias?"]
        .str.strip()
        .str.lower()
        .eq("no")
    ]

    total_no_reside = no_reside.shape[0]
    st.write(f"Total de encuestados NO residentes: **{total_no_reside}**")

    # 🔹 4. Homogeneizar columna de motivo
    no_reside["Motivo_normalizado"] = (
        no_reside["¿Cuál fue el motivo de su viaje a la ciudad de Cartagena?"]
        .fillna("sin respuesta")
        .str.strip()
        .str.lower()
    )

    # 🔹 5. Contar categorías relevantes
    motivo_religioso = "venir a los eventos religiosos"
    motivo_ocio = "vacaciones/ocio"

    total_religioso = no_reside[
        no_reside["Motivo_normalizado"] == motivo_religioso
    ].shape[0]
    total_ocio = no_reside[
        no_reside["Motivo_normalizado"] == motivo_ocio
    ].shape[0]

    total_otros_o_sin_respuesta = total_no_reside - total_religioso - total_ocio

    # 🔹 6. Mostrar conteos intermedios
    st.write("**Conteo de motivos de viaje entre NO residentes:**")
    st.write(f"- Venir a los eventos religiosos: **{total_religioso}**")
    st.write(f"- Vacaciones/ocio: **{total_ocio}**")
    st.write(f"- Otros o sin respuesta: **{total_otros_o_sin_respuesta}**")
    st.write(f"- Total NO residentes: **{total_no_reside}**")

    # Validación
    if total_no_reside == 0 or total_encuestados == 0:
        st.error("No hay suficientes datos de encuesta para calcular el PNL.")
        st.stop()


    # 🔹 7. Cálculo paso a paso
    proporcion_turismo = total_no_reside / total_encuestados
    ponderador = (
        1 * (total_religioso / total_no_reside) +
        0.5 * ((total_ocio + total_otros_o_sin_respuesta) / total_no_reside)
    )

    st.write(f"Proporción de no residentes sobre total encuestados: **{proporcion_turismo:.4f}**")
    st.write(f"Ponderador de motivos (religioso/ocio): **{ponderador:.4f}**")

    # 🔹 8. Cálculo final del PNL
    PNL = (potencial_aforo * proporcion_turismo) * ponderador
    st.success(f"**Población estimada (PNL): {PNL:,.2f}**")


    # Merge con multiplicadores
    df_merge = df_directo.merge(
        df_multi,
        how="inner",
        on="C_Sector"
    )
    df_merge["Efecto_Indirecto"] = df_merge["V_EED"] * df_merge["Multiplicador intraregional para Bolívar"]
    df_merge["Efecto_Inducido_Neto_Directo"] = df_merge["Efecto_Indirecto"] - df_merge["V_EED"]

    st.subheader("Efectos Directo e Indirecto por Sector")
    st.dataframe(df_merge)

    # Aquí seguirían los cálculos de estancia y gastos, que puedes dejar igual por ahora

else:
    st.warning("Por favor sube los 4 archivos para iniciar.")

