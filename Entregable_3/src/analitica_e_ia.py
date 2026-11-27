"""
Módulos 3 y 4 (Versión clara y sencilla):
1. Modelo Clasificador de Benefactores (4 categorías basadas en pagos reales).
2. Modelo Predictivo de Llamadas con Alta Probabilidad (RandomForest sin fuga de datos + reglas híbridas).
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def clasificar_un_benefactor(fila) -> str:
    """Embudo sencillo de 3 preguntas sobre los aportes reales confirmados."""
    total_aportes = int(fila["num_aportes_registrados"])
    aportes_recientes = int(fila["aportes_recientes_2024_2026"])

    if aportes_recientes == 0:
        return "Sin aportes recientes que requieren revisión"
    elif total_aportes == 1:
        return "Con un único aporte registrado"
    elif total_aportes >= 4 and aportes_recientes >= 2:
        return "Permanente o recurrente"
    else:
        return "Esporádico"


def ejecutar_clasificacion_benefactores(df_donantes: pd.DataFrame, df_aportes: pd.DataFrame) -> pd.DataFrame:
    """Calcula el resumen histórico de cada donante y lo clasifica en su categoría."""
    ultimo_anio = int(df_aportes["anio"].max())
    anio_corte_ia = ultimo_anio - 2  # Ejemplo: <= 2024 para entrenar IA sin mirar 2025-2026

    resumen_total = df_aportes.groupby("id_benefactor").agg(
        num_aportes_registrados=("id_aporte", "count"),
        valor_acumulado=("monto", "sum"),
        valor_promedio_aporte=("monto", "mean"),
        fecha_primer_aporte=("fecha_referencia", "min"),
        fecha_ultimo_aporte_tx=("fecha_referencia", "max"),
        primer_anio_aporte=("anio", "min"),
        ultimo_anio_aporte=("anio", "max"),
    ).reset_index()

    resumen_reciente = (
        df_aportes[df_aportes["anio"] >= anio_corte_ia]
        .groupby("id_benefactor")
        .agg(aportes_recientes_2024_2026=("id_aporte", "count"))
        .reset_index()
    )

    # Datos solo hasta 2024 para que la IA no espíe el futuro (2025-2026)
    aportes_hasta_2024 = df_aportes[df_aportes["anio"] <= anio_corte_ia]
    resumen_pre_2025 = (
        aportes_hasta_2024.groupby("id_benefactor")
        .agg(
            aportes_hasta_2024=("id_aporte", "count"),
            monto_hasta_2024=("monto", "sum"),
            anios_activos_hasta_2024=("anio", "nunique"),
        )
        .reset_index()
    )
    resumen_solo_2024 = (
        df_aportes[df_aportes["anio"] == anio_corte_ia]
        .groupby("id_benefactor")
        .agg(aportes_en_2024=("id_aporte", "count"), monto_en_2024=("monto", "sum"))
        .reset_index()
    )

    recurso_favorito = (
        df_aportes.groupby(["id_benefactor", "recurso"])["monto"]
        .sum()
        .reset_index()
        .sort_values(["id_benefactor", "monto"], ascending=[True, False])
        .drop_duplicates("id_benefactor")
        .rename(columns={"recurso": "recurso_mayor_contribucion"})
    )

    df = (
        df_donantes
        .merge(resumen_total, on="id_benefactor", how="left")
        .merge(resumen_reciente, on="id_benefactor", how="left")
        .merge(resumen_pre_2025, on="id_benefactor", how="left")
        .merge(resumen_solo_2024, on="id_benefactor", how="left")
        .merge(recurso_favorito[["id_benefactor", "recurso_mayor_contribucion"]], on="id_benefactor", how="left")
    )

    cols_ceros = [
        "num_aportes_registrados", "valor_acumulado", "valor_promedio_aporte",
        "aportes_recientes_2024_2026", "aportes_hasta_2024", "monto_hasta_2024",
        "anios_activos_hasta_2024", "aportes_en_2024", "monto_en_2024",
    ]
    for c in cols_ceros:
        df[c] = df[c].fillna(0)

    # Intervalo promedio en meses entre el primer y el último aporte
    meses_transcurridos = (df["fecha_ultimo_aporte_tx"] - df["fecha_primer_aporte"]).dt.days / 30.44
    df["intervalo_promedio_meses"] = np.where(
        df["num_aportes_registrados"] >= 2,
        meses_transcurridos / (df["num_aportes_registrados"] - 1),
        np.nan,
    )
    df["fecha_ultimo_aporte"] = df[["ult_pago_norm", "fecha_ultimo_aporte_tx"]].max(axis=1)
    df["recurso_mayor_contribucion"] = df["recurso_mayor_contribucion"].fillna("Sin registro monetario")
    df["clasificacion_benefactor"] = df.apply(clasificar_un_benefactor, axis=1)
    return df


def entrenar_modelo_predictivo_llamadas(df: pd.DataFrame, df_aportes: pd.DataFrame) -> dict:
    """
    Entrena el modelo RandomForestClassifier para predecir qué benefactores tienen
    alta probabilidad de responder positivamente a una llamada de captación.
    """
    ultimo_anio = int(df_aportes["anio"].max())
    anio_corte = ultimo_anio - 2

    # Etiquetas objetivo reales en 2025-2026
    donaron_directo_25_26 = set(df_aportes[(df_aportes["anio"] > anio_corte) & (df_aportes["recurso"] == "Donación directa")]["id_benefactor"])
    compraron_bono_25_26 = set(df_aportes[(df_aportes["anio"] > anio_corte) & (df_aportes["recurso"] == "Bono")]["id_benefactor"])
    compraron_banquete = set(df_aportes[df_aportes["recurso"] == "Banquete navideño"]["id_benefactor"])

    socio_txt = df["socio_raw"].fillna("").str.upper()
    notas_txt = df["texto_notas_unido"].fillna("").str.upper()

    df["y_donacion_directa"] = df["id_benefactor"].isin(donaron_directo_25_26).astype(int)
    df["y_bono"] = (df["id_benefactor"].isin(compraron_bono_25_26) | df["bono_2026_raw"].notna() | df["llamar_bonos_2026"].notna()).astype(int)
    df["y_rifa_cantarrilla"] = (df["cantarilla_2026_raw"].notna() | df["rifa_virgen_carmen_raw"].notna() | socio_txt.str.contains("CANTARILLA|RIFA")).astype(int)
    df["y_evento"] = (socio_txt.str.contains("EVENTO|TARDES|NSE|PEREGRIN|RETIRO") | df["encuesta_eventos"].notna()).astype(int)
    df["y_banquete"] = (df["id_benefactor"].isin(compraron_banquete) | socio_txt.str.contains("BANQUETE")).astype(int)

    # Variables de entrada X (100% calculadas sin usar pagos de 2025-2026)
    df["municipio_simple"] = np.where(df["municipio_raw"].fillna("").str.upper().str.contains("MEDELL"), "MEDELLIN", "OTRO_O_SIN_DATO")
    df["paga_domicilio"] = (df["tipo_pago_norm"] == "DOMICILIO").astype(int)

    cols_numericas = [
        "aportes_hasta_2024", "monto_hasta_2024", "anios_activos_hasta_2024",
        "aportes_en_2024", "monto_en_2024", "personas_en_telefono", "paga_domicilio",
    ]
    cols_booleanas = ["flag_aporte_familiar_amigos", "flag_whatsapp"]
    cols_categoricas = ["municipio_simple"]

    X = df[cols_numericas + cols_booleanas + cols_categoricas].copy()
    for b in cols_booleanas:
        X[b] = X[b].astype(int)

    preprocesador = ColumnTransformer([
        ("num", Pipeline([("imputar", SimpleImputer(strategy="median")), ("escalar", StandardScaler())]), cols_numericas + cols_booleanas),
        ("cat", OneHotEncoder(handle_unknown="ignore"), cols_categoricas),
    ])

    objetivos = {
        "a. Donación directa": df["y_donacion_directa"],
        "b. Bono": df["y_bono"],
        "c. Rifa cantarrilla": df["y_rifa_cantarrilla"],
        "d. Evento": df["y_evento"],
        "g. Banquete navideño": df["y_banquete"],
    }

    tabla_metricas = []
    modelos = {}

    for nombre_recurso, y in objetivos.items():
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=42)

        modelo_azar = Pipeline([("prep", preprocesador), ("clf", DummyClassifier(strategy="most_frequent"))])
        modelo_lineal = Pipeline([("prep", preprocesador), ("clf", LogisticRegression(max_iter=500, class_weight="balanced", random_state=42))])
        modelo_bosque = Pipeline([
            ("prep", preprocesador),
            ("clf", RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced", random_state=42)),
        ])

        modelo_azar.fit(X_train, y_train)
        modelo_lineal.fit(X_train, y_train)
        modelo_bosque.fit(X_train, y_train)

        pred_test = modelo_bosque.predict(X_test)
        prob_test = modelo_bosque.predict_proba(X_test)[:, 1]
        prob_lineal = modelo_lineal.predict_proba(X_test)[:, 1]
        cv_auc = cross_val_score(modelo_bosque, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=42), scoring="roc_auc").mean()

        tabla_metricas.append({
            "Recurso": nombre_recurso,
            "Accuracy": round(accuracy_score(y_test, pred_test), 3),
            "Precision": round(precision_score(y_test, pred_test, zero_division=0), 3),
            "Recall": round(recall_score(y_test, pred_test, zero_division=0), 3),
            "F1_Score": round(f1_score(y_test, pred_test, zero_division=0), 3),
            "ROC_AUC_RandomForest": round(roc_auc_score(y_test, prob_test), 3),
            "ROC_AUC_Logistica": round(roc_auc_score(y_test, prob_lineal), 3),
            "ROC_AUC_5Fold_CV": round(cv_auc, 3),
        })
        modelos[nombre_recurso] = (modelo_bosque, X_test, y_test, pred_test, prob_test)

    return {"df": df, "metricas": pd.DataFrame(tabla_metricas), "modelos": modelos}
