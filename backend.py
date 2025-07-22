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

def evaluar_distribuciones(df, columnas, criterio="auto"):
    """
    Evalúa si las columnas seleccionadas tienen distribución normal.
    
    Parámetros:
        df: DataFrame
        columnas: Lista de nombres de columnas numéricas
        criterio: 'auto', 'Mediana' o 'Promedio'
    
    Retorna:
        dict con estadísticas (p-value, media, mediana, sugerencia)
    """
    resultados = {}
    for col in columnas:
        datos = pd.to_numeric(df[col], errors='coerce').dropna()
        if len(datos) < 3:
            resultados[col] = {
                "N": len(datos),
                "p_value": np.nan,
                "media": np.nan,
                "mediana": np.nan,
                "sugerencia": "Insuficiente"
            }
            continue

        p_valor = shapiro(datos)[1]
        sugerencia = (
            "Promedio" if (criterio == "auto" and p_valor > 0.05) else "Mediana"
        ) if criterio == "auto" else criterio

        resultados[col] = {
            "N": len(datos),
            "p_value": p_valor,
            "media": datos.mean(),
            "mediana": datos.median(),
            "sugerencia": sugerencia
        }

    return resultados

def calcular_efecto_economico_indirecto(df_no_reside, pnl, multiplicador=1.0):
    columnas_dict = extraer_columnas_validas(df_no_reside)

    # Variables necesarias
    columnas_usar = [
        columnas_dict.get("gasto_evento"),
        columnas_dict.get("gasto_alojamiento"),
        columnas_dict.get("gasto_alimentacion"),
        columnas_dict.get("gasto_transporte"),
        columnas_dict.get("dias_estadia")
    ]
    columnas_usar = [col for col in columnas_usar if col is not None]

    stats = evaluar_distribuciones(df_no_reside, columnas_usar, criterio="auto")

    # Obtener valores sugeridos
    get_valor = lambda col: stats[col]["media"] if stats[col]["sugerencia"] == "Promedio" else stats[col]["mediana"]

    gasto_evento = get_valor(columnas_dict["gasto_evento"])
    gasto_alojamiento = get_valor(columnas_dict["gasto_alojamiento"])
    gasto_alimentacion = get_valor(columnas_dict["gasto_alimentacion"])
    gasto_transporte = get_valor(columnas_dict["gasto_transporte"])
    dias_estadia = get_valor(columnas_dict["dias_estadia"])

    gasto_diario_total = gasto_alojamiento + gasto_alimentacion + gasto_transporte
    gasto_total_por_persona = gasto_evento + (gasto_diario_total * dias_estadia)
    efecto_indirecto = pnl * gasto_total_por_persona * multiplicador

    resultado = {
        "Gasto en eventos": gasto_evento,
        "Gasto diario total": gasto_diario_total,
        "Días de estadía": dias_estadia,
        "Gasto total por persona": gasto_total_por_persona,
        "PNL": pnl,
        "Multiplicador": multiplicador,
        "Efecto Económico Indirecto": efecto_indirecto
    }

    return resultado, stats