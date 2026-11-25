"""
Módulos 1 y 2: Ingesta Inmutable, ETL Dinámico Adaptativo y Almacenamiento Lakehouse (Parquet + DuckDB).

Soporta re-ejecución transparente ante nuevas versiones del archivo Excel (nuevas filas, nuevas fechas
o nuevas columnas anuales/mensuales como 2027+) sin modificar manualmente el archivo fuente.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb
import numpy as np
import openpyxl
import pandas as pd


MESES_MAP_HEADER = {
    "ENE": 1, "ENERO": 1,
    "FEB": 2, "FEBRERO": 2,
    "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAYO": 5,
    "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10,
    "NOV": 11, "NOVIEMBRE": 11,
    "DIC": 12, "DICIEMBRE": 12,
}

MESES_CORTOS = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

REGEX_FAMILIA = re.compile(
    r"\b(esposo|esposa|esposos|familia|flia|mam[aá]|pap[aá]|hijo|hija|herman[oa]s?|"
    r"sobrin[oa]s?|t[ií][oa]s?|amig[oa]s?|compa[ñn][ií]a|junto con|dona con)\b",
    re.IGNORECASE,
)

REGEX_NO_CONTACTO = re.compile(
    r"\b(no llamar|no contactar|retirar|no sigue|no seg|falleci[oó]|muri[oó]|no felicitar|no molestar)\b",
    re.IGNORECASE,
)

VALID_TIPO_PAGO = {
    "DO": "DOMICILIO",
    "CO": "CONSIGNACION",
    "TR": "TRANSFERENCIA",
    "SE": "SEDE",
    "DE": "DEBITO",
}

MESES_VALIDOS_CUMP = {"ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"}


def sha256_file(path: Path) -> str:
    """Calcula el hash criptográfico SHA-256 de un archivo en bloques de 8 KB."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_accents(text: str) -> str:
    norm = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")


def mapear_esquema_dinamico(raw_columns: List[str]) -> Tuple[List[str], List[str], List[dict], List[str]]:
    """
    Resuelve dinámicamente los encabezados del Excel de la Fundación 1380.
    Permite procesar tanto el Excel actual (130 columnas, 2008-2026) como futuras versiones
    con más beneficiarios o nuevos bloques mensuales/anuales (ej. 2027, 2028) sin editar código.

    Retorna:
      - nombres_limpios: lista de nombres únicos asignados a cada columna.
      - cols_anuales_hist: columnas anuales consolidadas (ej. total_2008..total_2023).
      - meta_mensuales: metadatos [{col, anio, mes, recurso, tipo_registro}] de columnas de detalle.
      - cols_totales_resumen: columnas de subtotales anuales (ej. total_2024, total_2025, total_2026).
    """
    n_cols = len(raw_columns)
    cleaned_headers = []
    for c in raw_columns:
        base = re.sub(r"\.\d+$", "", str(c).strip())
        base = re.sub(r"\s+", " ", _strip_accents(base)).upper().strip()
        cleaned_headers.append(base)

    # Identificar dónde inicia la matriz financiera histórica (primera columna '2008' o año 20XX)
    idx_inicio_fin = 44
    for i, h in enumerate(cleaned_headers):
        if re.fullmatch(r"20\d{2}", h) and int(h) <= 2015:
            idx_inicio_fin = i
            break

    # Mapeo semántico adaptable para el bloque maestro/CRM (columnas previas a la matriz financiera)
    PATRONES_CRM = [
        ("COD", "cod"),
        ("FECHA", "fecha_ingreso_raw"),
        ("SOCIO", "socio_raw"),
        ("TRATO", "trato_raw"),
        ("NOMBRES APELLIDOS", "nombre_completo_token"),
        ("NOMBRES", "nombres_token"),
        ("APELLIDOS", "apellidos_token"),
        ("CEDULA", "cedula_token"),
        ("TELEFONO", "telefono_token"),
        ("DIRECCION", "direccion_token"),
        ("BARRIO", "barrio_token"),
        ("MUNICIPIO", "municipio_raw"),
        ("DIA CUMP", "dia_cump_raw"),
        ("MES CUMP", "mes_cump_raw"),
        ("ANO", "anio_nac_raw"),
        ("LO ATENDERA", "lo_atendera_raw"),
        ("MENSAJES DE CUMPLEANOS", "mensajes_cumpleanos"),
        ("DETALLE CUMPLEANOS", "detalle_cumpleanos"),
        ("WA", "whatsapp_flag"),
        ("VECES EN EL ANO", "veces_en_anio_raw"),
        ("ENE- MAR", "trim_ene_mar"),
        ("ABR-JUN", "trim_abr_jun"),
        ("JUL A SEP", "trim_jul_sep"),
        ("OCT- DIC", "trim_oct_dic"),
        ("ENCUESTA EVENTOS", "encuesta_eventos"),
        ("EMAIL", "email_token"),
        ("CERTIFICADO", "certificado_donacion_raw"),
        ("DONACION EXTRA", "donacion_extra_raw"),
        ("GESTION", "gestion_log"),
        ("LLAMAR PARA BONOS", "llamar_bonos_2026"),
        ("CALAMIDAD", "calamidad"),
        ("ENFERMO", "enfermo"),
        ("OBSERVACIONES", "observaciones_comentarios"),
        ("TIPO PAGO", "tipo_pago_raw"),
        ("RECOGERLE", "recogerle_dia"),
        ("FRECUENCIA", "frecuencia_raw"),
        ("ALCANCIA", "alcancia_raw"),
        ("BONO 20", "bono_2026_raw"),
        ("CANTARILLA", "cantarilla_2026_raw"),
        ("VIRGEN DEL CARME", "rifa_virgen_carmen_raw"),
        ("CUOTA", "cuota_raw"),
        ("ULT PAGO", "ult_pago_raw"),
    ]

    nombres_limpios: List[str] = [""] * n_cols
    usados = set()
    recibos_vistos = 0

    for i in range(idx_inicio_fin):
        h = cleaned_headers[i]
        raw_trim = str(raw_columns[i]).strip()
        if h == "RECIBOS":
            recibos_vistos += 1
            cand = "recibos_preferencia_raw" if (recibos_vistos == 1 and raw_trim != "RECIBOS") else "recibos_numeros"
            if cand in usados:
                cand = "recibos_numeros"
        else:
            cand = None
            for pat, target in PATRONES_CRM:
                if h == pat or h.startswith(pat):
                    if target not in usados:
                        cand = target
                        break
            if cand is None:
                cand = f"crm_extra_{i}_{re.sub(r'[^a-z0-9]+', '_', h.lower()).strip('_')}"
        usados.add(cand)
        nombres_limpios[i] = cand

    # Analizar bloque financiero (anuales puros + bloques detallados cerrados por TOTAL YYYY o YYYY)
    cols_anuales_hist: List[str] = []
    meta_mensuales: List[dict] = []
    cols_totales_resumen: List[str] = []

    buffer_detalle: List[Tuple[int, str]] = []
    for i in range(idx_inicio_fin, n_cols):
        h = cleaned_headers[i]
        if h == "ACUMULADO":
            nombres_limpios[i] = "acumulado_reportado"
            continue

        m_tot = re.fullmatch(r"(?:TOTAL\s*)?(20\d{2})", h)
        if m_tot:
            anio_val = int(m_tot.group(1))
            if not buffer_detalle:
                col_name = f"total_{anio_val}"
                nombres_limpios[i] = col_name
                cols_anuales_hist.append(col_name)
            else:
                # Asignar el bloque mensual acumulado a anio_val
                mes_actual = 1
                for idx_det, h_det in buffer_detalle:
                    es_bono = "BONO" in h_det
                    es_banquete = "BANQUETE" in h_det
                    mes_detectado = None
                    for token_mes, num_mes in MESES_MAP_HEADER.items():
                        if re.search(rf"\b{token_mes}\b", h_det):
                            mes_detectado = num_mes
                            break
                    if mes_detectado is not None:
                        mes_actual = mes_detectado
                    mes_final = 12 if es_banquete else mes_actual

                    if es_banquete:
                        base_det = f"{anio_val}_banquete"
                        recurso = "Banquete navideño"
                        tipo_reg = "BANQUETE"
                    elif es_bono:
                        base_det = f"{anio_val}_{mes_final:02d}_bonos"
                        recurso = "Bono"
                        tipo_reg = "MENSUAL_BONO"
                    else:
                        base_det = f"{anio_val}_{mes_final:02d}_{MESES_CORTOS[mes_final]}"
                        recurso = "Donación directa"
                        tipo_reg = "MENSUAL_REGULAR"

                    col_det = base_det
                    suf = 2
                    while col_det in usados:
                        col_det = f"{base_det}_{suf}"
                        suf += 1
                    usados.add(col_det)
                    nombres_limpios[idx_det] = col_det
                    meta_mensuales.append({
                        "col": col_det,
                        "anio": anio_val,
                        "mes": mes_final,
                        "recurso": recurso,
                        "tipo_registro": tipo_reg,
                    })

                buffer_detalle = []
                col_tot = f"total_{anio_val}"
                usados.add(col_tot)
                nombres_limpios[i] = col_tot
                cols_totales_resumen.append(col_tot)
        else:
            buffer_detalle.append((i, h))

    # Si quedaran columnas mensuales abiertas al final sin columna TOTAL YYYY (ej. nuevo año en curso)
    if buffer_detalle:
        ultimo_anio = max(
            [int(re.search(r"\d{4}", c).group(0)) for c in (cols_totales_resumen + cols_anuales_hist)] or [2026]
        ) + 1
        mes_actual = 1
        for idx_det, h_det in buffer_detalle:
            es_bono = "BONO" in h_det
            es_banquete = "BANQUETE" in h_det
            for token_mes, num_mes in MESES_MAP_HEADER.items():
                if re.search(rf"\b{token_mes}\b", h_det):
                    mes_actual = num_mes
                    break
            mes_final = 12 if es_banquete else mes_actual
            recurso = "Banquete navideño" if es_banquete else ("Bono" if es_bono else "Donación directa")
            tipo_reg = "BANQUETE" if es_banquete else ("MENSUAL_BONO" if es_bono else "MENSUAL_REGULAR")
            col_det = f"{ultimo_anio}_{mes_final:02d}_{'bonos' if es_bono else MESES_CORTOS[mes_final]}"
            while col_det in usados:
                col_det += "_x"
            usados.add(col_det)
            nombres_limpios[idx_det] = col_det
            meta_mensuales.append({
                "col": col_det,
                "anio": ultimo_anio,
                "mes": mes_final,
                "recurso": recurso,
                "tipo_registro": tipo_reg,
            })

    return nombres_limpios, cols_anuales_hist, meta_mensuales, cols_totales_resumen


def clean_str(val):
    if pd.isna(val):
        return np.nan
    s = re.sub(r"\s+", " ", str(val)).strip()
    return s if s != "" else np.nan


def normalizar_socio(val) -> str:
    if pd.isna(val):
        return "SIN_CLASIFICAR"
    v = str(val).upper()
    if "RETIR" in v or "NO SIGUE" in v or "NO SEG" in v:
        return "RETIRADO"
    if "PARROQUIA" in v:
        return "VISITA_PARROQUIAS"
    if "BONO" in v:
        return "BONOS"
    if "PERM" in v:
        return "PERMANENTE"
    if "ESP" in v:
        return "ESPORADICO"
    if "BANQUETE" in v:
        return "BANQUETE"
    if "CANTARILLA" in v or "RIFA" in v:
        return "RIFA_CANTARILLA"
    if "ALC" in v:
        return "ALCANCIA"
    if "BINGO" in v:
        return "BINGO"
    if "NSE" in v or "TARDES" in v or "OYENTE" in v:
        return "EVENTO_NSE"
    if "EVENTO" in v or "PEREGRIN" in v or "RETIRO" in v or "EJERCICIOS" in v:
        return "EVENTO"
    return "OTRO"


def parse_excel_or_text_date(val):
    if pd.isna(val):
        return pd.NaT
    if isinstance(val, (int, float, np.integer, np.floating)):
        if 20000 <= float(val) <= 60000:
            return pd.to_datetime(float(val), unit="D", origin="1899-12-30", errors="coerce")
        return pd.NaT
    if isinstance(val, (datetime, pd.Timestamp)):
        return pd.to_datetime(val)
    s = str(val).strip().replace("//", "/").replace("'", "")
    return pd.to_datetime(s, dayfirst=True, errors="coerce")


def ejecutar_ingesta_y_etl(origen_path: Path, base_dir: Path = Path("sibda_1380")) -> Dict[str, object]:
    """
    Ejecuta el Módulo 1 completo sobre una copia de trabajo en Data Lake /raw,
    preservando intacto el archivo Excel original (verificado con SHA-256).
    """
    origen_path = Path(origen_path)
    if not origen_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo Excel en: {origen_path}")

    dirs = {
        "raw": base_dir / "datalake" / "raw",
        "bronze": base_dir / "datalake" / "bronze",
        "silver": base_dir / "datalake" / "silver",
        "gold": base_dir / "datalake" / "gold",
        "warehouse": base_dir / "warehouse",
        "backups": base_dir / "backups",
        "reportes": base_dir / "reportes",
        "logs": base_dir / "logs",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    hash_inicio = sha256_file(origen_path)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"ETL_{run_timestamp}"
    copia_raw_path = dirs["raw"] / f"raw_{run_timestamp}_{origen_path.name}"
    shutil.copy2(origen_path, copia_raw_path)

    if sha256_file(copia_raw_path) != hash_inicio:
        raise RuntimeError("Fallo crítico de integridad al generar la copia en Data Lake /raw.")

    wb = openpyxl.load_workbook(copia_raw_path, read_only=True, data_only=False)
    hojas = wb.sheetnames
    sheet_name = hojas[0]
    wb.close()

    df_raw = pd.read_excel(copia_raw_path, sheet_name=sheet_name, dtype=object)
    df_work = df_raw.copy()

    nombres_limpios, cols_anuales_hist, meta_mensuales, cols_totales_resumen = mapear_esquema_dinamico(
        list(df_raw.columns)
    )
    df_work.columns = nombres_limpios
    df_work["id_benefactor"] = range(1, len(df_work) + 1)

    # Garantizar columnas esperadas incluso si una versión futura omite alguna opcional
    cols_requeridas_crm = [
        "cod", "fecha_ingreso_raw", "socio_raw", "trato_raw", "nombre_completo_token",
        "nombres_token", "apellidos_token", "cedula_token", "telefono_token",
        "direccion_token", "barrio_token", "municipio_raw", "dia_cump_raw",
        "mes_cump_raw", "anio_nac_raw", "lo_atendera_raw", "mensajes_cumpleanos",
        "detalle_cumpleanos", "whatsapp_flag", "veces_en_anio_raw", "encuesta_eventos",
        "email_token", "certificado_donacion_raw", "donacion_extra_raw", "gestion_log",
        "llamar_bonos_2026", "calamidad", "enfermo", "observaciones_comentarios",
        "tipo_pago_raw", "recogerle_dia", "frecuencia_raw", "recibos_preferencia_raw",
        "alcancia_raw", "bono_2026_raw", "cantarilla_2026_raw", "rifa_virgen_carmen_raw",
        "cuota_raw", "ult_pago_raw", "recibos_numeros",
    ]
    for req_col in cols_requeridas_crm:
        if req_col not in df_work.columns:
            df_work[req_col] = np.nan

    df_work["cod"] = pd.to_numeric(df_work["cod"], errors="coerce").astype("Int64")

    text_cols = [
        c for c in cols_requeridas_crm
        if c not in {"cod", "fecha_ingreso_raw", "dia_cump_raw", "anio_nac_raw", "cuota_raw", "ult_pago_raw"}
    ]
    for c in text_cols:
        df_work[c] = df_work[c].apply(clean_str)

    df_work["socio_categoria"] = df_work["socio_raw"].apply(normalizar_socio)
    df_work["tipo_pago_norm"] = df_work["tipo_pago_raw"].map(
        lambda x: VALID_TIPO_PAGO.get(str(x).upper(), "OTRO_O_INVALIDO") if pd.notna(x) else "NO_ESPECIFICADO"
    )
    df_work["mes_cump_norm"] = df_work["mes_cump_raw"].map(
        lambda x: x.upper() if pd.notna(x) and x.upper() in MESES_VALIDOS_CUMP else np.nan
    )

    df_work["fecha_ingreso_norm"] = df_work["fecha_ingreso_raw"].apply(parse_excel_or_text_date)
    df_work["ult_pago_norm"] = df_work["ult_pago_raw"].apply(parse_excel_or_text_date)
    df_work["flag_fecha_ingreso_invalida"] = df_work["fecha_ingreso_raw"].notna() & df_work["fecha_ingreso_norm"].isna()
    df_work["flag_ult_pago_invalido"] = df_work["ult_pago_raw"].notna() & df_work["ult_pago_norm"].isna()

    df_work["cuota_valor_num"] = pd.to_numeric(df_work["cuota_raw"], errors="coerce")
    df_work["bono_2026_valor_num"] = pd.to_numeric(df_work["bono_2026_raw"], errors="coerce")
    df_work["recogerle_dia_num"] = pd.to_numeric(df_work["recogerle_dia"], errors="coerce").astype("Int64")

    cols_texto_integrado = [
        "socio_raw", "trato_raw", "mensajes_cumpleanos", "detalle_cumpleanos",
        "encuesta_eventos", "donacion_extra_raw", "gestion_log", "llamar_bonos_2026",
        "calamidad", "enfermo", "observaciones_comentarios", "recibos_preferencia_raw",
        "alcancia_raw", "bono_2026_raw", "cantarilla_2026_raw", "rifa_virgen_carmen_raw",
    ]
    df_work["texto_consolidado_crm"] = df_work.apply(
        lambda row: " | ".join(str(row[c]) for c in cols_texto_integrado if pd.notna(row[c])),
        axis=1,
    )

    def _detectar_familia(row):
        txt = row["texto_consolidado_crm"]
        trato = str(row["trato_raw"]) if pd.notna(row["trato_raw"]) else ""
        matches = REGEX_FAMILIA.findall(txt)
        if not matches and re.search(r"(esposos|se[ñn]ores|familia|flia)", trato, re.IGNORECASE):
            matches = ["pareja/familia"]
        if matches:
            return True, ", ".join(sorted(set(m.lower() for m in matches)))
        return False, "No documentado"

    fam_res = df_work.apply(_detectar_familia, axis=1)
    df_work["flag_aporte_familiar_amigos"] = [r[0] for r in fam_res]
    df_work["detalle_vinculo_familiar"] = [r[1] for r in fam_res]

    def _detectar_restriccion(row):
        matches = REGEX_NO_CONTACTO.findall(row["texto_consolidado_crm"])
        if matches:
            return True, ", ".join(sorted(set(m.upper() for m in matches)))
        return False, "NINGUNA"

    rest_res = df_work.apply(_detectar_restriccion, axis=1)
    df_work["flag_restriccion_no_contacto"] = [r[0] for r in rest_res]
    df_work["motivo_restriccion_contacto"] = [r[1] for r in rest_res]

    df_work["flag_whatsapp"] = (
        df_work["whatsapp_flag"].fillna("").str.upper().str.contains("SI")
        | df_work["mensajes_cumpleanos"].fillna("").str.upper().str.contains("WHATSAPP")
    )
    df_work["canal_preferido"] = np.where(df_work["flag_whatsapp"], "WhatsApp / Telefónico", "Llamada Telefónica")
    df_work["flag_nota_sensible_pastoral"] = df_work["enfermo"].notna() | df_work["calamidad"].notna()

    tel_freq = df_work["telefono_token"].value_counts(dropna=True)
    df_work["personas_en_telefono"] = df_work["telefono_token"].map(tel_freq).fillna(0).astype(int)
    df_work["flag_telefono_compartido"] = df_work["personas_en_telefono"] > 1

    ced_freq = df_work["cedula_token"].value_counts(dropna=True)
    df_work["flag_cedula_duplicada"] = df_work["cedula_token"].map(ced_freq).fillna(0).astype(int) > 1

    # Conversión numérica y unpivot dinámico
    cols_detalle = [m["col"] for m in meta_mensuales]
    cols_fin_todas = cols_anuales_hist + cols_detalle + cols_totales_resumen
    if "acumulado_reportado" in df_work.columns:
        cols_fin_todas.append("acumulado_reportado")
    for c in cols_fin_todas:
        df_work[c] = pd.to_numeric(df_work[c], errors="coerce")

    partes_long = []
    if cols_anuales_hist:
        df_h = df_work.melt(
            id_vars=["id_benefactor", "lo_atendera_raw"],
            value_vars=cols_anuales_hist,
            var_name="origen_col",
            value_name="monto",
        ).dropna(subset=["monto"])
        df_h = df_h[df_h["monto"] > 0].copy()
        df_h["anio"] = df_h["origen_col"].str.extract(r"(\d{4})").astype(int)
        df_h["mes"] = 12
        df_h["recurso"] = "Donación directa"
        df_h["tipo_registro"] = "ANUAL_HISTORICO"
        partes_long.append(df_h)

    if cols_detalle:
        meta_df = pd.DataFrame(meta_mensuales).rename(columns={"col": "origen_col"})
        df_m = df_work.melt(
            id_vars=["id_benefactor", "lo_atendera_raw"],
            value_vars=cols_detalle,
            var_name="origen_col",
            value_name="monto",
        ).dropna(subset=["monto"])
        df_m = df_m[df_m["monto"] > 0].merge(meta_df, on="origen_col", how="left")
        partes_long.append(df_m)

    df_aportes_long = pd.concat(partes_long, ignore_index=True)
    df_aportes_long["fecha_referencia"] = pd.to_datetime(
        df_aportes_long["anio"].astype(str) + "-" + df_aportes_long["mes"].astype(str).str.zfill(2) + "-15"
    )
    df_aportes_long = df_aportes_long.sort_values(["id_benefactor", "fecha_referencia"]).reset_index(drop=True)
    df_aportes_long["id_aporte"] = range(1, len(df_aportes_long) + 1)

    return {
        "run_id": run_id,
        "run_timestamp": run_timestamp,
        "origen_path": origen_path,
        "copia_raw_path": copia_raw_path,
        "hash_inicio": hash_inicio,
        "hojas_excel": hojas,
        "sheet_name": sheet_name,
        "dirs": dirs,
        "df_raw": df_raw,
        "df_work": df_work,
        "df_aportes_long": df_aportes_long,
        "cols_anuales_hist": cols_anuales_hist,
        "meta_mensuales": meta_mensuales,
        "cols_totales_resumen": cols_totales_resumen,
    }


def persistir_lakehouse_y_duckdb(
    contexto_etl: Dict[str, object],
    df_master: pd.DataFrame,
    df_agenda_resultado: pd.DataFrame,
    cols_silver_gold: List[str],
) -> Path:
    """
    Persiste las capas Bronze, Silver y Gold en Parquet (Data Lake) y construye el
    Data Warehouse dimensional en DuckDB (Módulo 2).
    """
    dirs = contexto_etl["dirs"]
    df_raw: pd.DataFrame = contexto_etl["df_raw"]
    df_aportes_long: pd.DataFrame = contexto_etl["df_aportes_long"]

    df_bronze = df_raw.astype(str).replace("nan", np.nan)
    df_bronze.to_parquet(dirs["bronze"] / "f1380_crudo.parquet", index=False)

    cols_presentes = [c for c in cols_silver_gold if c in df_master.columns]
    df_gold_benefactores = df_master[cols_presentes].copy()

    df_gold_benefactores.to_parquet(dirs["silver"] / "benefactores_limpio.parquet", index=False)
    df_aportes_long.to_parquet(dirs["silver"] / "aportes_normalizados.parquet", index=False)
    df_gold_benefactores.to_parquet(dirs["gold"] / "clasificacion_y_afinidad_benefactores.parquet", index=False)
    df_agenda_resultado.to_parquet(dirs["gold"] / "agenda_contactos_telemercadeo.parquet", index=False)

    dw_path = dirs["warehouse"] / "fundacion_1380_dw.duckdb"
    if dw_path.exists():
        dw_path.unlink()

    con = duckdb.connect(str(dw_path))
    con.execute("CREATE TABLE dim_benefactor AS SELECT * FROM df_gold_benefactores;")
    con.execute("""
        CREATE TABLE dim_telemercaderista AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY nombre_responsable) AS id_telemercaderista,
            nombre_responsable
        FROM (
            SELECT DISTINCT COALESCE(lo_atendera_raw, 'SIN_ASIGNAR') AS nombre_responsable
            FROM df_gold_benefactores
        );
    """)
    con.execute("""
        CREATE TABLE dim_recurso AS
        SELECT
            ROW_NUMBER() OVER (ORDER BY codigo_recurso) AS id_recurso,
            codigo_recurso,
            nombre_recurso
        FROM (
            VALUES
                ('a', 'Donación directa'),
                ('b', 'Bono'),
                ('c', 'Rifa cantarrilla'),
                ('d', 'Evento'),
                ('e', 'Bingo'),
                ('f', 'Visita a parroquias'),
                ('g', 'Banquete navideño'),
                ('h', 'Día de madres y padres'),
                ('i', 'Otro recurso configurable')
        ) AS t(codigo_recurso, nombre_recurso);
    """)
    con.execute("""
        CREATE TABLE dim_tiempo AS
        SELECT DISTINCT
            anio * 100 + mes AS id_tiempo,
            anio,
            mes,
            CAST(FLOOR((mes - 1) / 3.0) AS INTEGER) + 1 AS trimestre,
            fecha_referencia
        FROM df_aportes_long
        ORDER BY anio, mes;
    """)
    con.execute("""
        CREATE TABLE fact_aportes AS
        SELECT
            a.id_aporte,
            a.id_benefactor,
            t.id_telemercaderista,
            r.id_recurso,
            a.anio * 100 + a.mes AS id_tiempo,
            a.anio,
            a.mes,
            a.fecha_referencia,
            a.monto,
            a.tipo_registro,
            a.origen_col
        FROM df_aportes_long a
        LEFT JOIN dim_telemercaderista t
            ON COALESCE(a.lo_atendera_raw, 'SIN_ASIGNAR') = t.nombre_responsable
        LEFT JOIN dim_recurso r
            ON a.recurso = r.nombre_recurso;
    """)
    con.execute("CREATE TABLE fact_agenda_contactos AS SELECT * FROM df_agenda_resultado;")

    df_audit_log = pd.DataFrame([{
        "run_id": contexto_etl["run_id"],
        "timestamp_ejecucion": datetime.now().isoformat(),
        "archivo_origen": str(contexto_etl["origen_path"]),
        "sha256_origen": contexto_etl["hash_inicio"],
        "filas_excel_leidas": len(df_raw),
        "columnas_excel_leidas": df_raw.shape[1],
        "transacciones_normalizadas": len(df_aportes_long),
        "monto_total_verificado": float(df_aportes_long["monto"].sum()),
        "estado": "EXITOSO_INMUTABLE",
    }])
    con.execute("CREATE TABLE audit_log_etl AS SELECT * FROM df_audit_log;")
    con.close()
    return dw_path
