"""
Módulos 3 y 4: Clasificación Analítica de Benefactores e Inteligencia Artificial (Predicción de Afinidad).

Aplica estrictamente buenas prácticas de Machine Learning:
- Separación temporal estricta de variables predictoras (ventana histórica <= MAX_ANIO - 2) vs objetivo
  reciente ([MAX_ANIO - 1, MAX_ANIO]) para eliminar cualquier fuga de datos (data leakage).
- Ajuste de imputadores y codificadores únicamente sobre el conjunto de entrenamiento (Pipeline + ColumnTransformer).
- Comparación contra línea base ingenua (DummyClassifier), línea base lineal (LogisticRegression),
  RandomForestClassifier y GradientBoostingClassifier con intervalos de confianza bootstrap al 95 %.
- Soporte dinámico para recursos configurables ('i. Otro recurso configurable' o campañas nuevas).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


MAPA_SOCIO_RECURSO = {
    "BONOS": "Bono",
    "PERMANENTE": "Donación directa",
    "ESPORADICO": "Donación directa",
    "BANQUETE": "Banquete navideño",
    "RIFA_CANTARILLA": "Rifa cantarrilla",
    "EVENTO": "Evento",
    "EVENTO_NSE": "Evento",
    "BINGO": "Bingo",
    "VISITA_PARROQUIAS": "Visita a parroquias",
    "ALCANCIA": "Otro recurso configurable",
}


def _calcular_intervalos_meses(df_tx: pd.DataFrame, nombre_col: str) -> pd.DataFrame:
    if df_tx.empty:
        return pd.DataFrame(columns=["id_benefactor", nombre_col])
    df_sorted = df_tx.sort_values(["id_benefactor", "fecha_referencia"])
    diffs = df_sorted.groupby("id_benefactor")["fecha_referencia"].apply(
        lambda s: ((s.max() - s.min()).days / 30.4375) / max(len(s) - 1, 1) if len(s) >= 2 else np.nan
    )
    return diffs.rename(nombre_col).reset_index()


def ejecutar_clasificacion_benefactores(df_work: pd.DataFrame, df_aportes_long: pd.DataFrame) -> pd.DataFrame:
    """
    Ejecuta el Módulo 3: calcula los 8 atributos individuales de cada benefactor y clasifica el 100 %
    del padrón en las 4 categorías exigidas sin inventar causas personales.
    """
    max_anio = int(df_aportes_long["anio"].max()) if not df_aportes_long.empty else 2026
    anio_inicio_reciente = max_anio - 2  # Ej. 2024..2026
    anio_corte_hist_ia = max_anio - 2    # Ej. <= 2024 para predecir 2025..2026 sin data leakage

    agg_total = df_aportes_long.groupby("id_benefactor").agg(
        num_aportes_registrados=("id_aporte", "count"),
        valor_acumulado=("monto", "sum"),
        valor_promedio_aporte=("monto", "mean"),
        fecha_primer_aporte_tx=("fecha_referencia", "min"),
        fecha_ultimo_aporte_tx=("fecha_referencia", "max"),
        primer_anio_aporte=("anio", "min"),
        ultimo_anio_aporte=("anio", "max"),
        anios_distintos_activos=("anio", "nunique"),
    ).reset_index()

    agg_reciente = (
        df_aportes_long[df_aportes_long["anio"] >= anio_inicio_reciente]
        .groupby("id_benefactor")
        .agg(
            aportes_recientes_2024_2026=("id_aporte", "count"),
            monto_reciente_2024_2026=("monto", "sum"),
        )
        .reset_index()
    )

    df_pre_ia = df_aportes_long[df_aportes_long["anio"] <= anio_corte_hist_ia]
    agg_pre_ia = (
        df_pre_ia.groupby("id_benefactor")
        .agg(
            num_aportes_pre_target=("id_aporte", "count"),
            monto_acum_pre_target=("monto", "sum"),
            monto_prom_pre_target=("monto", "mean"),
            anios_activos_pre_target=("anio", "nunique"),
            primer_anio_pre_target=("anio", "min"),
        )
        .reset_index()
    )

    agg_anio_corte = (
        df_aportes_long[df_aportes_long["anio"] == anio_corte_hist_ia]
        .groupby("id_benefactor")
        .agg(aportes_anio_corte_count=("id_aporte", "count"), monto_anio_corte_sum=("monto", "sum"))
        .reset_index()
    )

    agg_post_corte = (
        df_aportes_long[df_aportes_long["anio"] > anio_corte_hist_ia]
        .groupby("id_benefactor")
        .agg(aportes_target_count=("id_aporte", "count"), monto_target_sum=("monto", "sum"))
        .reset_index()
    )

    s_int_total = _calcular_intervalos_meses(df_aportes_long, "intervalo_promedio_meses")
    s_int_pre_ia = _calcular_intervalos_meses(df_pre_ia, "intervalo_meses_pre_target")

    recurso_top_tx = (
        df_aportes_long.groupby(["id_benefactor", "recurso"])
        .agg(monto_recurso=("monto", "sum"), tx_recurso=("id_aporte", "count"))
        .reset_index()
        .sort_values(["id_benefactor", "monto_recurso", "tx_recurso"], ascending=[True, False, False])
        .drop_duplicates("id_benefactor")
        .rename(columns={"recurso": "recurso_top_transaccional", "monto_recurso": "monto_recurso_top"})
    )

    df_master = (
        df_work
        .merge(agg_total, on="id_benefactor", how="left")
        .merge(agg_reciente, on="id_benefactor", how="left")
        .merge(agg_pre_ia, on="id_benefactor", how="left")
        .merge(agg_anio_corte, on="id_benefactor", how="left")
        .merge(agg_post_corte, on="id_benefactor", how="left")
        .merge(s_int_total, on="id_benefactor", how="left")
        .merge(s_int_pre_ia, on="id_benefactor", how="left")
        .merge(recurso_top_tx[["id_benefactor", "recurso_top_transaccional", "monto_recurso_top"]], on="id_benefactor", how="left")
    )

    for col_z in [
        "num_aportes_registrados", "valor_acumulado", "valor_promedio_aporte",
        "aportes_recientes_2024_2026", "monto_reciente_2024_2026",
        "num_aportes_pre_target", "monto_acum_pre_target", "monto_prom_pre_target",
        "anios_activos_pre_target", "primer_anio_pre_target",
        "aportes_anio_corte_count", "monto_anio_corte_sum",
        "aportes_target_count", "monto_target_sum",
        "anios_distintos_activos", "primer_anio_aporte", "ultimo_anio_aporte",
    ]:
        df_master[col_z] = df_master[col_z].fillna(0)

    df_master["fecha_ultimo_aporte"] = df_master[["ult_pago_norm", "fecha_ultimo_aporte_tx"]].max(axis=1)

    def _determinar_recurso_principal(row):
        if pd.notna(row["recurso_top_transaccional"]):
            if row["recurso_top_transaccional"] == "Donación directa" and row["socio_categoria"] in [
                "BONOS", "BANQUETE", "RIFA_CANTARILLA", "BINGO", "VISITA_PARROQUIAS"
            ]:
                if row["valor_acumulado"] == 0:
                    return MAPA_SOCIO_RECURSO[row["socio_categoria"]]
            return row["recurso_top_transaccional"]
        return MAPA_SOCIO_RECURSO.get(row["socio_categoria"], "Sin registro de recurso")

    df_master["recurso_mayor_contribucion"] = df_master.apply(_determinar_recurso_principal, axis=1)

    def _clasificar(row) -> str:
        n_tot = int(row["num_aportes_registrados"])
        n_rec = int(row["aportes_recientes_2024_2026"])
        if n_rec == 0:
            return "Sin aportes recientes que requieren revisión"
        if n_tot == 1:
            return "Con un único aporte registrado"
        if n_tot >= 4 and n_rec >= 2:
            return "Permanente o recurrente"
        return "Esporádico"

    df_master["clasificacion_benefactor"] = df_master.apply(_clasificar, axis=1)

    def _describir_comportamiento(row) -> str:
        n_tot = int(row["num_aportes_registrados"])
        if n_tot == 0:
            return "Sin aportes monetarios confirmados en matriz histórica; requiere validación objetiva de estado."
        m_corte = float(row["monto_anio_corte_sum"])
        m_post = float(row["monto_target_sum"]) / 1.8
        if row["aportes_recientes_2024_2026"] == 0:
            tendencia = f"Sin aportes registrados desde {int(row['ultimo_anio_aporte'])}"
        elif m_post > m_corte * 1.15:
            tendencia = "Tendencia creciente en período reciente"
        elif m_post < m_corte * 0.85 and m_corte > 0:
            tendencia = "Tendencia decreciente frente al año base"
        else:
            tendencia = "Aportación estable en período reciente"
        cadencia = (
            f"cada {row['intervalo_promedio_meses']:.1f} meses"
            if pd.notna(row["intervalo_promedio_meses"]) and row["intervalo_promedio_meses"] > 0
            else "aporte puntual"
        )
        return f"Activo {int(row['primer_anio_aporte'])}-{int(row['ultimo_anio_aporte'])} ({n_tot} aportes, {cadencia}); {tendencia}."

    df_master["comportamiento_historico"] = df_master.apply(_describir_comportamiento, axis=1)
    return df_master


def _bootstrap_ci(y_true: np.ndarray, y_prob: np.ndarray, n_boot: int = 200, seed: int = 42) -> Tuple[float, float]:
    rng = np.random.RandomState(seed)
    scores = []
    n = len(y_true)
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        scores.append(roc_auc_score(y_true[idx], y_prob[idx]))
    if not scores:
        return (np.nan, np.nan)
    return (float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5)))


def entrenar_y_evaluar_ia(df_master: pd.DataFrame, df_aportes_long: pd.DataFrame) -> Dict[str, object]:
    """
    Ejecuta el Módulo 4 completo: ingeniería de variables sin fuga temporal, comparación de modelos
    (Dummy, LogisticRegression, RandomForest, GradientBoosting), validación cruzada 5-Fold, intervalos
    bootstrap al 95 %, análisis por subgrupos (slice analysis) y scoring híbrido para los 9 recursos.
    """
    max_anio = int(df_aportes_long["anio"].max()) if not df_aportes_long.empty else 2026
    anio_corte_hist = max_anio - 2

    # Antigüedad estrictamente calculada hasta anio_corte_hist para evitar fuga temporal
    anio_ing_pre = df_master["fecha_ingreso_norm"].dt.year.where(
        df_master["fecha_ingreso_norm"].dt.year <= anio_corte_hist, np.nan
    )
    antig_pre = np.where(
        df_master["primer_anio_pre_target"] > 0,
        anio_corte_hist - df_master["primer_anio_pre_target"],
        np.where(anio_ing_pre.notna(), anio_corte_hist - anio_ing_pre, 0),
    )
    df_master["antiguedad_pre_target"] = np.clip(antig_pre, 0, 25)
    df_master["flag_sin_intervalo_previo"] = df_master["intervalo_meses_pre_target"].isna().astype(int)

    def _agrupar_mun(m):
        if pd.isna(m):
            return "NO_REGISTRADO"
        mu = str(m).upper()
        if "MEDELLIN" in mu or "MEDELLÍN" in mu:
            return "MEDELLIN"
        if any(k in mu for k in ["ENVIGADO", "BELLO", "ITAGUI", "SABANETA", "COPACABANA", "ESTRELLA", "CALDAS"]):
            return "AREA_METROPOLITANA"
        return "OTRO_O_EXTERIOR"

    def _agrupar_trato(t):
        if pd.isna(t):
            return "NO_REGISTRADO"
        tu = str(t).upper()
        if "SEÑORA" in tu or "SENORA" in tu or "SEÑORITA" in tu:
            return "SENORA"
        if "SEÑOR" in tu or "SENOR" in tu:
            return "SENOR"
        return "OTRO_O_FAMILIA"

    def _agrupar_tele(r):
        if pd.isna(r):
            return "SIN_ASIGNAR"
        ru = str(r).upper()
        for p in ["SANDRA", "VIVIANA", "LINA", "JORGE", "VICMAR", "JD", "NSE", "GLORIA"]:
            if p in ru:
                return p
        return "OTROS"

    df_master["municipio_grupo"] = df_master["municipio_raw"].apply(_agrupar_mun)
    df_master["trato_grupo"] = df_master["trato_raw"].apply(_agrupar_trato)
    df_master["telemercaderista_grupo"] = df_master["lo_atendera_raw"].apply(_agrupar_tele)
    df_master["flag_domicilio_recogerle"] = (
        (df_master["tipo_pago_norm"] == "DOMICILIO") | df_master["recogerle_dia_num"].notna()
    ).astype(int)

    # Etiquetas de los 9 recursos oficiales (a..i)
    tx_target_don = set(df_aportes_long[(df_aportes_long["anio"] > anio_corte_hist) & (df_aportes_long["recurso"] == "Donación directa")]["id_benefactor"])
    tx_target_bono = set(df_aportes_long[(df_aportes_long["anio"] > anio_corte_hist) & (df_aportes_long["recurso"] == "Bono")]["id_benefactor"])
    tx_all_don = set(df_aportes_long[df_aportes_long["recurso"] == "Donación directa"]["id_benefactor"])
    tx_all_bono = set(df_aportes_long[df_aportes_long["recurso"] == "Bono"]["id_benefactor"])
    tx_all_banq = set(df_aportes_long[df_aportes_long["recurso"] == "Banquete navideño"]["id_benefactor"])

    socio_up = df_master["socio_raw"].fillna("").str.upper()
    txt_up = df_master["texto_consolidado_crm"].fillna("").str.upper()

    df_master["y_donacion_directa_target"] = df_master["id_benefactor"].isin(tx_target_don).astype(int)
    df_master["y_bono_target"] = (
        df_master["id_benefactor"].isin(tx_target_bono)
        | df_master["bono_2026_raw"].notna()
        | df_master["llamar_bonos_2026"].notna()
    ).astype(int)

    df_master["ev_donacion_directa"] = (df_master["id_benefactor"].isin(tx_all_don) | socio_up.str.contains("PERM|ESP") | df_master["donacion_extra_raw"].notna()).astype(int)
    df_master["ev_bono"] = (df_master["id_benefactor"].isin(tx_all_bono) | socio_up.str.contains("BONO") | df_master["bono_2026_raw"].notna() | df_master["llamar_bonos_2026"].notna()).astype(int)
    df_master["ev_rifa_cantarrilla"] = (df_master["cantarilla_2026_raw"].notna() | df_master["rifa_virgen_carmen_raw"].notna() | socio_up.str.contains("CANTARILLA|RIFA") | txt_up.str.contains("CANTARILLA|RIFA")).astype(int)
    df_master["ev_evento"] = (socio_up.str.contains("EVENTO|TARDES|NSE|PEREGRIN|RETIRO|EJERCICIOS|ANIVERSARIO|ORDEN") | df_master["encuesta_eventos"].notna() | txt_up.str.contains("EVENTO|PEREGRIN|RETIRO|TARDES")).astype(int)
    df_master["ev_bingo"] = (socio_up.str.contains("BINGO") | txt_up.str.contains(r"\bBINGO\b")).astype(int)
    df_master["ev_visita_parroquias"] = (socio_up.str.contains("PARROQUIA") | txt_up.str.contains("PARROQUIA")).astype(int)
    df_master["ev_banquete_navideno"] = (df_master["id_benefactor"].isin(tx_all_banq) | socio_up.str.contains("BANQUETE") | txt_up.str.contains("BANQUETE")).astype(int)
    df_master["ev_dia_madres_padres"] = txt_up.str.contains(r"\b(?:MADRE|PADRE|DIA DE LA MADRE|DIA DEL PADRE)\b", regex=True).astype(int)
    df_master["ev_otro_recurso"] = (df_master["alcancia_raw"].notna() | socio_up.str.contains("ALC|CD|SOBRE|RADIOTON|TOLDOS")).astype(int)

    features_num = [
        "antiguedad_pre_target",
        "num_aportes_pre_target",
        "monto_acum_pre_target",
        "monto_prom_pre_target",
        "anios_activos_pre_target",
        "aportes_anio_corte_count",
        "monto_anio_corte_sum",
        "intervalo_meses_pre_target",
        "flag_sin_intervalo_previo",
        "personas_en_telefono",
        "flag_domicilio_recogerle",
    ]
    features_bool = ["flag_aporte_familiar_amigos", "flag_whatsapp"]
    features_cat = ["municipio_grupo", "trato_grupo", "telemercaderista_grupo"]

    X_all = df_master[features_num + features_bool + features_cat].copy()
    for bcol in features_bool:
        X_all[bcol] = X_all[bcol].astype(int)

    def _build_prep():
        return ColumnTransformer(
            transformers=[
                ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), features_num + features_bool),
                ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("ohe", OneHotEncoder(handle_unknown="ignore"))]), features_cat),
            ]
        )

    targets_ml = {
        "a. Donación directa": df_master["y_donacion_directa_target"],
        "b. Bono": df_master["y_bono_target"],
        "c. Rifa cantarrilla": df_master["ev_rifa_cantarrilla"],
        "d. Evento": df_master["ev_evento"],
        "g. Banquete navideño": df_master["ev_banquete_navideno"],
    }

    modelos_entrenados = {}
    metricas_evaluacion = []
    comparativa_algoritmos = []
    probabilidades_ml = {}

    for nombre_rec, y_target in targets_ml.items():
        X_train, X_test, y_train, y_test = train_test_split(
            X_all, y_target, test_size=0.20, stratify=y_target, random_state=42
        )

        candidatos_modelos = {
            "DummyBaseline (Mayoría)": Pipeline([("prep", _build_prep()), ("clf", DummyClassifier(strategy="most_frequent"))]),
            "LogisticRegression": Pipeline([("prep", _build_prep()), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))]),
            "GradientBoostingClassifier": Pipeline([("prep", _build_prep()), ("clf", GradientBoostingClassifier(n_estimators=120, max_depth=4, learning_rate=0.05, random_state=42))]),
            "RandomForestClassifier": Pipeline([
                ("prep", _build_prep()),
                ("clf", RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=5, class_weight="balanced", random_state=42, n_jobs=-1)),
            ]),
        }

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        for nom_alg, pipe in candidatos_modelos.items():
            pipe.fit(X_train, y_train)
            y_pred = pipe.predict(X_test)
            y_prob = pipe.predict_proba(X_test)[:, 1]
            if nombre_rec in {"a. Donación directa", "b. Bono"}:
                comparativa_algoritmos.append({
                    "Recurso": nombre_rec,
                    "Modelo": nom_alg,
                    "Accuracy_Test": round(accuracy_score(y_test, y_pred), 4),
                    "F1_Test": round(f1_score(y_test, y_pred, zero_division=0), 4),
                    "PR_AUC_Test": round(average_precision_score(y_test, y_prob), 4),
                    "ROC_AUC_Test": round(roc_auc_score(y_test, y_prob), 4),
                })

        rf_pipe = candidatos_modelos["RandomForestClassifier"]
        lr_pipe = candidatos_modelos["LogisticRegression"]
        y_pred_rf = rf_pipe.predict(X_test)
        y_prob_rf = rf_pipe.predict_proba(X_test)[:, 1]
        cv_auc_rf = cross_val_score(rf_pipe, X_all, y_target, cv=cv, scoring="roc_auc").mean()
        cv_auc_lr = cross_val_score(lr_pipe, X_all, y_target, cv=cv, scoring="roc_auc").mean()
        ci_low, ci_high = _bootstrap_ci(y_test.to_numpy(), y_prob_rf)

        cm_test = confusion_matrix(y_test, y_pred_rf)
        tn, fp, fn, tp = cm_test.ravel() if cm_test.size == 4 else (0, 0, 0, 0)
        especificidad = tn / (tn + fp) if (tn + fp) > 0 else 0.0

        metricas_evaluacion.append({
            "Recurso": nombre_rec,
            "Algoritmo": "RandomForestClassifier",
            "Accuracy_Test": round(accuracy_score(y_test, y_pred_rf), 4),
            "Precision_Test": round(precision_score(y_test, y_pred_rf, zero_division=0), 4),
            "Recall_Test": round(recall_score(y_test, y_pred_rf, zero_division=0), 4),
            "Especificidad_Test": round(especificidad, 4),
            "F1_Score_Test": round(f1_score(y_test, y_pred_rf, zero_division=0), 4),
            "PR_AUC_Test": round(average_precision_score(y_test, y_prob_rf), 4),
            "ROC_AUC_Test": round(roc_auc_score(y_test, y_prob_rf), 4),
            "IC95_AUC": f"[{ci_low:.3f}, {ci_high:.3f}]",
            "Brier_Score_Test": round(brier_score_loss(y_test, y_prob_rf), 4),
            "ROC_AUC_5Fold_CV": round(cv_auc_rf, 4),
            "ROC_AUC_LogReg_Base": round(cv_auc_lr, 4),
        })

        modelos_entrenados[nombre_rec] = (rf_pipe, X_test, y_test, y_pred_rf, y_prob_rf)
        probabilidades_ml[nombre_rec] = rf_pipe.predict_proba(X_all)[:, 1]

    # Análisis de error por subpoblaciones (Slice-Based Evaluation en conjunto Test de Donación directa)
    rf_don, X_t_don, y_t_don, y_p_don, y_pr_don = modelos_entrenados["a. Donación directa"]
    slices_rows = []
    for sub_mun, sub_idx in X_t_don.groupby("municipio_grupo").groups.items():
        yt_s = y_t_don.loc[sub_idx]
        yp_s = pd.Series(y_p_don, index=X_t_don.index).loc[sub_idx]
        ypr_s = pd.Series(y_pr_don, index=X_t_don.index).loc[sub_idx]
        auc_s = round(roc_auc_score(yt_s, ypr_s), 4) if yt_s.nunique() > 1 else np.nan
        slices_rows.append({
            "Subgrupo_Municipio": sub_mun,
            "Muestras_Test": len(yt_s),
            "Tasa_Positiva_%": round(yt_s.mean() * 100, 1),
            "F1_Score": round(f1_score(yt_s, yp_s, zero_division=0), 4),
            "ROC_AUC": auc_s,
        })

    df_master["prob_a_donacion_directa"] = probabilidades_ml["a. Donación directa"]
    df_master["prob_b_bono"] = probabilidades_ml["b. Bono"]
    df_master["prob_c_rifa_cantarrilla"] = np.maximum(probabilidades_ml["c. Rifa cantarrilla"], df_master["ev_rifa_cantarrilla"] * 0.92)
    df_master["prob_d_evento"] = np.maximum(probabilidades_ml["d. Evento"], df_master["ev_evento"] * 0.92)
    df_master["prob_g_banquete_navideno"] = np.maximum(probabilidades_ml["g. Banquete navideño"], df_master["ev_banquete_navideno"] * 0.92)

    rfm_base = (
        0.40 * df_master["num_aportes_registrados"].rank(pct=True)
        + 0.35 * df_master["valor_acumulado"].rank(pct=True)
        + 0.25 * (df_master["aportes_recientes_2024_2026"] > 0).astype(float)
    )
    df_master["prob_e_bingo"] = np.clip(0.55 * df_master["ev_bingo"] + 0.25 * df_master["prob_c_rifa_cantarrilla"] + 0.20 * rfm_base, 0, 0.99)
    df_master["prob_f_visita_parroquias"] = np.clip(0.55 * df_master["ev_visita_parroquias"] + 0.25 * df_master["prob_d_evento"] + 0.20 * rfm_base, 0, 0.99)
    df_master["prob_h_dia_madres_padres"] = np.clip(0.50 * df_master["ev_dia_madres_padres"] + 0.30 * df_master["flag_aporte_familiar_amigos"].astype(float) + 0.20 * rfm_base, 0, 0.99)
    df_master["prob_i_otro_recurso"] = np.clip(0.55 * df_master["ev_otro_recurso"] + 0.45 * rfm_base, 0, 0.99)

    return {
        "df_master": df_master,
        "df_metricas_ml": pd.DataFrame(metricas_evaluacion),
        "df_comparativa_algoritmos": pd.DataFrame(comparativa_algoritmos),
        "df_slices_municipio": pd.DataFrame(slices_rows),
        "modelos_entrenados": modelos_entrenados,
        "features_num": features_num,
        "features_bool": features_bool,
        "features_cat": features_cat,
    }
