import pandas as pd
import streamlit as st
from scipy import stats as st  # <-- aquí sí# ahora sí, requerido
import numpy as np
from difflib import get_close_matches
import unicodedata

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

def detectar_categorias_motivo(
    df_encuesta: pd.DataFrame,
    columna_reside: str = "¿Reside en la ciudad de Cartagena de Indias?",
    columna_motivo: str = "¿Cuál fue el motivo de su viaje a la ciudad de Cartagena?"
) -> pd.Series:
    """
    Devuelve un Series con el conteo de categorías de motivo entre NO residentes.
    Sirve para poblar el selectbox en la UI.
    """
    if columna_reside not in df_encuesta.columns:
        raise ValueError(f"No se encontró la columna de residencia: '{columna_reside}'")

    if columna_motivo not in df_encuesta.columns:
        raise ValueError(f"No se encontró la columna de motivo: '{columna_motivo}'")

    # Filtrar respuestas válidas y NO residentes
    df_responde = df_encuesta[
        df_encuesta[columna_reside]
        .astype(str).str.strip().str.lower()
        .isin(["sí", "si", "no"])
    ]
    no_reside = df_responde[
        df_responde[columna_reside]
        .astype(str).str.strip().str.lower()
        .eq("no")
    ]

    if no_reside.empty:
        return pd.Series(dtype="int64")

    motivos = (
        no_reside[columna_motivo]
        .astype(str)
        .str.strip()
        .replace({"": "sin respuesta"})
        .str.lower()
    )

    return motivos.value_counts(dropna=False)


def calcular_pnl(
    df_encuesta: pd.DataFrame,
    df_aforo: pd.DataFrame,
    columna_reside: str = "¿Reside en la ciudad de Cartagena de Indias?",
    columna_motivo: str = "¿Cuál fue el motivo de su viaje a la ciudad de Cartagena?",
    categoria_principal: str | None = None,
    peso_principal: float = 1.0,
    peso_otros: float = 0.5,
    activar_factor_correccion: bool = False,  # <-- AQUI (con rr)
) -> dict:
    """
    Calcula el PNL permitiendo seleccionar qué categoría de motivo es la 'principal'
    para el ponderador. El resto de categorías toman 'peso_otros'.

    Ponderador = peso_principal * (total_motivo_seleccionado / total_no_reside)
               + peso_otros     * ((total_no_reside - total_motivo_seleccionado) / total_no_reside)
    """
    # 1) Filtrado de respuestas válidas
    if columna_reside not in df_encuesta.columns:
        raise ValueError(f"No se encontró la columna de residencia: '{columna_reside}'")

    df_encuesta_responde = df_encuesta[
        df_encuesta[columna_reside]
        .astype(str).str.strip().str.lower()
        .isin(["sí", "si", "no"])
    ]
    total_encuestados = df_encuesta_responde.shape[0]
    if total_encuestados == 0:
        raise ValueError("No hay encuestados válidos (Sí/No) en la columna de residencia.")

    # 2) Potencial de aforo (suma de todos los eventos)
    if "Potencial de aforo" not in df_aforo.columns:
        raise ValueError("El archivo de Aforo debe tener la columna 'Potencial de aforo'.")
    potencial_aforo = pd.to_numeric(df_aforo["Potencial de aforo"], errors="coerce").fillna(0).sum()

    # 3) NO residentes
    no_reside = df_encuesta_responde[
        df_encuesta_responde[columna_reside]
        .astype(str).str.strip().str.lower()
        .eq("no")
    ]
    total_no_reside = no_reside.shape[0]
    if total_no_reside == 0:
        # Sin no-residentes => PNL = 0
        return {
            "PNL": 0.0,
            "total_encuestados": total_encuestados,
            "potencial_aforo": potencial_aforo,
            "total_no_reside": 0,
            "total_motivo_seleccionado": 0,
            "proporcion_turismo": 0.0,
            "ponderador": 0.0,
            "no_reside": no_reside,
            "categoria_principal": categoria_principal,
            "peso_principal": peso_principal,
            "peso_otros": peso_otros
        }

    # 4) Homogeneizar motivo
    if columna_motivo not in df_encuesta.columns:
        raise ValueError(f"No se encontró la columna de motivo: '{columna_motivo}'")

    motivos_norm = (
        no_reside[columna_motivo]
        .astype(str)
        .str.strip()
        .replace({"": "sin respuesta"})
        .str.lower()
    )

    # 5) Selección de categoría principal
    # Si no se especifica, intenta usar 'venir a los eventos religiosos' si existe; si no, toma la más frecuente
    if categoria_principal is None:
        vc = motivos_norm.value_counts(dropna=False)
        if "venir a los eventos religiosos" in vc.index:
            categoria_principal = "venir a los eventos religiosos"
        elif not vc.empty:
            categoria_principal = vc.idxmax()
        else:
            categoria_principal = "sin respuesta"

    # 6) Conteos
    total_motivo_sel = (motivos_norm == categoria_principal).sum()
    total_otras = total_no_reside - total_motivo_sel

    # 7) Proporción turismo (igual a antes)
    proporcion_turismo = total_no_reside / total_encuestados

    # 8) Ponderador con la categoría elegida
    # Evita división por cero (ya controlado total_no_reside>0, pero dejamos la guardia)
    if total_no_reside == 0:
        ponderador = 0.0
    else:
        ponderador = (
            peso_principal * (total_motivo_sel / total_no_reside) +
            peso_otros     * (total_otras / total_no_reside)
        )

    # 9) PNL final
    PNL = (potencial_aforo * proporcion_turismo) * ponderador

    # 10) Detección de >2 categorías en motivos (solo no residentes)
    num_categorias = motivos_norm.nunique(dropna=False)
    detecto_mas_de_dos = num_categorias > 2

    # 11) Fracciones base
    frac_principal = (total_motivo_sel / total_no_reside) if total_no_reside else 0.0
    frac_otras     = ((total_no_reside - total_motivo_sel) / total_no_reside) if total_no_reside else 0.0

    # 12) Ponderador:
    #     - Si hay >2 categorías Y activar_factor_correccion=True:
    #         ponderador = ( (peso_principal - frac_otras) * frac_principal ) + ( peso_otros * frac_otras )
    #     - En caso contrario (comportamiento original):
    #         ponderador = ( peso_principal * frac_principal ) + ( peso_otros * frac_otras )
    if detecto_mas_de_dos and activar_factor_correccion:
        ponderador = ((peso_principal - frac_otras) * frac_principal) + (peso_otros * frac_otras)
        peso_principal_efectivo = (peso_principal - frac_otras)
        correccion_activada = True
    else:
        ponderador = (peso_principal * frac_principal) + (peso_otros * frac_otras)
        peso_principal_efectivo = peso_principal
        correccion_activada = False

    # 13) PNL final
    PNL = (potencial_aforo * proporcion_turismo) * ponderador

    return {
        "PNL": float(PNL),
        "total_encuestados": int(total_encuestados),
        "potencial_aforo": float(potencial_aforo),
        "total_no_reside": int(total_no_reside),
        "total_motivo_seleccionado": int(total_motivo_sel),
        "proporcion_turismo": float(proporcion_turismo),
        "ponderador": float(ponderador),
        "no_reside": no_reside,
        "categoria_principal": categoria_principal,
        "peso_principal": float(peso_principal),
        "peso_otros": float(peso_otros),
        "peso_principal_efectivo": float(peso_principal_efectivo),
        "detecto_mas_de_dos_categorias": bool(detecto_mas_de_dos),
        "num_categorias_motivo": int(num_categorias),
        "factor_correccion_aplicado": float(frac_otras),  # (total_otras/total_no_reside)
        "correccion_activada": bool(correccion_activada),
    }

def evaluar_distribuciones(df: pd.DataFrame, columnas: list[str]) -> dict:
    """
    Media, mediana y p-value de normalidad con Shapiro.
    Nota: Shapiro no es fiable para n > 5000, por eso muestreamos hasta 5000.
    """
    resultados = {}
    for col in columnas:
        serie = pd.to_numeric(df[col], errors="coerce").dropna()
        if serie.empty:
            resultados[col] = {"media": float("nan"), "mediana": float("nan"), "p_value_shapiro": float("nan"), "n": 0}
            continue

        media = float(serie.mean())
        mediana = float(serie.median())

        n = len(serie)
        # Shapiro: fiable hasta ~5000 obs; muestreamos si es mayor
        if n > 5000:
            muestra = serie.sample(n=5000, random_state=123).values
        else:
            muestra = serie.values

        try:
            stat, p = st.shapiro(muestra)
            p_value = float(p)
        except Exception:
            p_value = float("nan")

        resultados[col] = {"media": media, "mediana": mediana, "p_value_shapiro": p_value, "n": int(n)}
    return resultados

def calcular_efecto_economico_indirecto(
    stats, pnl, multiplicador, col_aloj, col_alim, col_trans, col_dias, multiplicadores=None
):
    """
    Calcula efectos por rubro usando los valores sugeridos de `stats`.
    Para cada rubro r en {alojamiento, alimentación, transporte}:
        Indirecto_r       = PNL * (valor_sugerido_r) * (dias_sugerido)
        InducidoNeto_r    = (Indirecto_r * m_r) - Indirecto_r
    donde m_r es el multiplicador por rubro si viene en `multiplicadores`,
    o en su defecto `multiplicador` (general).

    Retorna:
      - resultado (resumen total)
      - desglose (lista por rubro y total con valores numéricos)
    """
    def _num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return float("nan")

    def _valor(col):
        sug = stats[col]["sugerencia"]
        return _num(stats[col]["media"] if sug == "Promedio" else stats[col]["mediana"])

    # Valores sugeridos desde stats
    v_aloj  = _valor(col_aloj)
    v_alim  = _valor(col_alim)
    v_trans = _valor(col_trans)
    dias    = _valor(col_dias)

    # Tratar NaN como 0 en gastos y días
    v_aloj0  = 0.0 if pd.isna(v_aloj)  else v_aloj
    v_alim0  = 0.0 if pd.isna(v_alim)  else v_alim
    v_trans0 = 0.0 if pd.isna(v_trans) else v_trans
    dias0    = 0.0 if pd.isna(dias)    else dias

    # Multiplicadores
    m_general = float(multiplicador)
    multiplicadores = multiplicadores or {}
    m_aloj  = float(multiplicadores.get("alojamiento",  m_general))
    m_alim  = float(multiplicadores.get("alimentacion", m_general))
    m_trans = float(multiplicadores.get("transporte",   m_general))

    pnl_f = float(pnl)

    # Indirectos por rubro
    ind_aloj  = pnl_f * v_aloj0  * dias0
    ind_alim  = pnl_f * v_alim0  * dias0
    ind_trans = pnl_f * v_trans0 * dias0

    # Totales
    indirecto_total = ind_aloj + ind_alim + ind_trans

    # Inducidos netos por rubro (explícito)
    inc_aloj  = (ind_aloj  * m_aloj)  - ind_aloj
    inc_alim  = (ind_alim  * m_alim)  - ind_alim
    inc_trans = (ind_trans * m_trans) - ind_trans
    inducido_neto_total = inc_aloj + inc_alim + inc_trans  # suma por rubro

    # Desglose para la UI
    desglose = [
        {"Rubro": "Alojamiento",  "Gasto diario usado": v_aloj0,  "Indirecto": ind_aloj,  "Inducido neto": inc_aloj},
        {"Rubro": "Alimentación", "Gasto diario usado": v_alim0,  "Indirecto": ind_alim,  "Inducido neto": inc_alim},
        {"Rubro": "Transporte",   "Gasto diario usado": v_trans0, "Indirecto": ind_trans, "Inducido neto": inc_trans},
        {"Rubro": "Total",        "Gasto diario usado": v_aloj0 + v_alim0 + v_trans0,
                                   "Indirecto": indirecto_total, "Inducido neto": inducido_neto_total},
    ]

    resultado = {
        "PNL": pnl_f,
        "Días de estadía (valor usado)": dias0,
        "Multiplicador general": m_general,
        "Multiplicador alojamiento": m_aloj,
        "Multiplicador alimentación": m_alim,
        "Multiplicador transporte": m_trans,
        "Efecto Indirecto Total": indirecto_total,
        "Efecto Inducido Neto Total": inducido_neto_total
    }

    return resultado, desglose