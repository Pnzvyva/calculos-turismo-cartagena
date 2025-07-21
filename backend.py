import pandas as pd
import streamlit as st
from scipy.stats import shapiro
import numpy as np
from difflib import get_close_matches

def extraer_columnas_validas(df_encuesta):
    """
    Busca las columnas más parecidas a las esperadas en el DataFrame recibido.
    Devuelve un diccionario con alias y nombres reales.
    """
    columnas_esperadas = {
        "gasto_evento": "¿Cuánto ha gastado aproximadamente en actividades relacionadas con LOS EVENTOS RELIGIOSOS DE SEMANA SANTA EN CARTAGENA (souvenirs, artesanías, libros, etc.)?",
        "dias_estadia": "¿Cuántos días estará en la ciudad de Cartagena?",
        "gasto_alojamiento": "¿Cuánto está gastando gasto diariamente en alojamiento? (Por persona):",
        "gasto_alimentacion": "En promedio ¿Cuánto ha sido su gasto diario en alimentación y bebidas durante su estadía en la ciudad?",
        "gasto_transporte": "En promedio ¿Cuánto ha sido su gasto diario en transporte durante su estadía en la ciudad?"
    }

    mapeo_resultante = {}
    columnas_disponibles = df_encuesta.columns.tolist()

    for alias, col_esperada in columnas_esperadas.items():
        coincidencias = get_close_matches(col_esperada.strip(), columnas_disponibles, n=1, cutoff=0.7)
        if coincidencias:
            mapeo_resultante[alias] = coincidencias[0]
        else:
            mapeo_resultante[alias] = None  # No encontrada

    return mapeo_resultante

def calcular_pnl(df_encuesta, df_aforo):
    # 🔹 1. Filtrar encuestados con respuesta "Sí" o "No"
    df_encuesta_responde = df_encuesta[
        df_encuesta["¿Reside en la ciudad de Cartagena de Indias?"]
        .str.strip()
        .str.lower()
        .isin(["sí", "si", "no"])
    ]

    total_encuestados = df_encuesta_responde.shape[0]

    # 🔹 2. Potencial de aforo = suma de todos los eventos
    potencial_aforo = df_aforo["Potencial de aforo"].sum()

    # 🔹 3. Filtrar NO residentes
    no_reside = df_encuesta_responde[
        df_encuesta_responde["¿Reside en la ciudad de Cartagena de Indias?"]
        .str.strip()
        .str.lower()
        .eq("no")
    ]

    total_no_reside = no_reside.shape[0]

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

    # 🔹 6. Cálculo paso a paso
    proporcion_turismo = total_no_reside / total_encuestados
    ponderador = (
        1 * (total_religioso / total_no_reside) +
        0.5 * ((total_ocio + total_otros_o_sin_respuesta) / total_no_reside)
    )

    # 🔹 7. Cálculo final del PNL
    PNL = (potencial_aforo * proporcion_turismo) * ponderador

    return {
        "PNL": PNL,
        "total_encuestados": total_encuestados,
        "potencial_aforo": potencial_aforo,
        "total_no_reside": total_no_reside,
        "total_religioso": total_religioso,
        "total_ocio": total_ocio,
        "total_otros": total_otros_o_sin_respuesta,
        "proporcion_turismo": proporcion_turismo,
        "ponderador": ponderador,
        "no_reside": no_reside
    }

def calcular_efecto_indirecto(df_encuesta_no_reside, pnl, criterio="Mediana"):
    """
    Calcula el efecto económico indirecto con base en la normalidad de las variables.

    Parámetros:
        df_encuesta_no_reside: DataFrame con solo no residentes
        pnl: Población estimada
        criterio: "Mediana" o "Promedio"

    Retorna:
        efecto_indirecto_estimado: valor numérico
        valores_usados: diccionario con estadísticos usados para cada variable
    """

    df = df_encuesta_no_reside.copy()
    columnas_dict = extraer_columnas_validas(df)

    datos_limpios = {}
    normalidades = {}
    valores_usados = {}

    for alias, col in columnas_dict.items():
        if col is None:
            valores_usados[alias] = np.nan
            continue
        df[alias] = pd.to_numeric(df[col], errors="coerce")
        df_valid = df[alias].dropna()
        if len(df_valid) > 3:
            _, p_val = shapiro(df_valid)
            normalidades[alias] = p_val > 0.05
            if criterio == "Promedio" and p_val > 0.05:
                valores_usados[alias] = df_valid.mean()
            else:
                valores_usados[alias] = df_valid.median()
        else:
            valores_usados[alias] = np.nan

    efecto_indirecto_estimado = pnl * valores_usados["gasto_evento"] * valores_usados["dias_estadia"]

    return efecto_indirecto_estimado, valores_usados

def calcular_efecto_inducido(df_merge, efecto_indirecto_estimado):
    """
    Calcula el efecto inducido neto por sector.

    Parámetros:
        df_merge: DataFrame con columnas 'C_Sector', 'Sector_EED', 'Multiplicador intraregional para Bolívar'
        efecto_indirecto_estimado: valor numérico del efecto indirecto común
    Retorna:
        DataFrame con columnas necesarias para mostrar en la interfaz.
    """
    df = df_merge.copy()
    df["Efecto_Economico_Directo"] = df["V_EED"]
    df["Efecto_Economico_Indirecto"] = efecto_indirecto_estimado
    df["Efecto_Inducido_Neto"] = (df["Efecto_Economico_Indirecto"] * df["Multiplicador intraregional para Bolívar"]) - df["Efecto_Economico_Indirecto"]

    columnas = ["C_Sector", "Sector_EED", "Efecto_Economico_Directo", "Efecto_Economico_Indirecto", "Efecto_Inducido_Neto"]
    return df[columnas]
