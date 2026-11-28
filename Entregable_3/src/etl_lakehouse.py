"""
Módulos 1 y 2 (Versión clara y sencilla):
Ingesta sin tocar el Excel original, limpieza de datos (ETL) y guardado en Parquet + DuckDB.

Nota clave de nombres para no confundir roles:
- donante_benefactor       -> Persona externa que dona dinero (ej. Juan, Felipe, PER_...).
- empleada_telemercaderista -> Empleada de la Fundación que hace la llamada (ej. Sandra, Viviana, Hna Lina).
"""

import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import openpyxl
import pandas as pd


MESES_ENCABEZADO = {
    "ENE": 1, "ENERO": 1, "FEB": 2, "FEBRERO": 2, "MAR": 3, "MARZO": 3,
    "ABR": 4, "ABRIL": 4, "MAY": 5, "MAYO": 5, "JUN": 6, "JUNIO": 6,
    "JUL": 7, "JULIO": 7, "AGO": 8, "AGOSTO": 8, "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OCTUBRE": 10, "NOV": 11, "NOVIEMBRE": 11, "DIC": 12, "DICIEMBRE": 12,
}

MESES_CORTOS = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

TABLA_SIN_TILDES = str.maketrans("ÁÉÍÓÚÑáéíóúñ", "AEIOUNaeioun")


def sha256_file(ruta_archivo: Path) -> str:
    """Calcula la huella digital SHA-256 de un archivo para comprobar que no fue modificado."""
    hasher = hashlib.sha256()
    with open(ruta_archivo, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(8192), b""):
            hasher.update(bloque)
    return hasher.hexdigest()


def limpiar_titulo_columna(texto) -> str:
    """Quita tildes, sufijos (.1, .2) y espacios repetidos de un título de columna."""
    sin_sufijo = re.sub(r"\.\d+$", "", str(texto).strip())
    sin_tildes = sin_sufijo.translate(TABLA_SIN_TILDES).upper()
    return re.sub(r"\s+", " ", sin_tildes).strip()


def mapear_esquema_dinamico(columnas_crudas: list):
    """
    Lee los títulos del Excel de izquierda a derecha y les pone nombres claros.
    Funciona tanto con las 130 columnas actuales como con nuevos años futuros (ej. 2027).
    """
    titulos = [limpiar_titulo_columna(c) for c in columnas_crudas]

    # Buscar en qué columna empiezan los años de aportes (2008)
    inicio_aportes = 44
    for i, t in enumerate(titulos):
        if t.isdigit() and len(t) == 4 and int(t) <= 2015:
            inicio_aportes = i
            break

    reglas_nombres_datos = [
        ("COD", "cod"),
        ("FECHA", "fecha_ingreso_raw"),
        ("SOCIO", "socio_raw"),
        ("TRATO", "trato_raw"),
        ("NOMBRES APELLIDOS", "donante_benefactor"),
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
        ("LO ATENDERA", "empleada_telemercaderista"),
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
        ("RIFA DE VIRGEN", "rifa_virgen_carmen_raw"),
        ("VIRGEN DEL CARME", "rifa_virgen_carmen_raw"),
        ("CUOTA", "cuota_raw"),
        ("ULT PAGO", "ult_pago_raw"),
    ]

    nombres_limpios = [""] * len(columnas_crudas)
    usados = set()
    recibos_vistos = 0

    # 1. Bautizar las columnas de datos del donante y de telemercadeo
    for i in range(inicio_aportes):
        t = titulos[i]
        original = str(columnas_crudas[i]).strip()
        if t == "RECIBOS":
            recibos_vistos += 1
            nombre = "recibos_preferencia_raw" if (recibos_vistos == 1 and original != "RECIBOS") else "recibos_numeros"
        else:
            nombre = f"columna_extra_{i}"
            for prefijo, destino in reglas_nombres_datos:
                if (t == prefijo or t.startswith(prefijo)) and destino not in usados:
                    nombre = destino
                    break
        usados.add(nombre)
        nombres_limpios[i] = nombre

    # 2. Bautizar las columnas financieras (años 2008..2023 y meses 2024..2026+)
    cols_anuales = []
    meta_mensuales = []
    cols_totales_resumen = []
    meses_pendientes = []

    for i in range(inicio_aportes, len(columnas_crudas)):
        t = titulos[i]
        if t == "ACUMULADO":
            nombres_limpios[i] = "acumulado_reportado"
            continue

        coincidencia_total = re.fullmatch(r"(?:TOTAL\s*)?(20\d{2})", t)
        if coincidencia_total:
            anio = int(coincidencia_total.group(1))
            if not meses_pendientes:
                nombre_col = f"total_{anio}"
                nombres_limpios[i] = nombre_col
                cols_anuales.append(nombre_col)
            else:
                mes_actual = 1
                for idx_mes, titulo_mes in meses_pendientes:
                    for palabra_mes, numero_mes in MESES_ENCABEZADO.items():
                        if re.search(rf"\b{palabra_mes}\b", titulo_mes):
                            mes_actual = numero_mes
                            break
                    es_banquete = "BANQUETE" in titulo_mes
                    es_bono = "BONO" in titulo_mes
                    mes_final = 12 if es_banquete else mes_actual

                    if es_banquete:
                        base, recurso = f"{anio}_banquete", "Banquete navideño"
                    elif es_bono:
                        base, recurso = f"{anio}_{mes_final:02d}_bonos", "Bono"
                    else:
                        base, recurso = f"{anio}_{mes_final:02d}_{MESES_CORTOS[mes_final]}", "Donación directa"

                    nombre_det = base
                    contador = 2
                    while nombre_det in usados:
                        nombre_det = f"{base}_{contador}"
                        contador += 1
                    usados.add(nombre_det)
                    nombres_limpios[idx_mes] = nombre_det
                    meta_mensuales.append({"col": nombre_det, "anio": anio, "mes": mes_final, "recurso": recurso})

                meses_pendientes = []
                nombre_tot = f"total_{anio}"
                usados.add(nombre_tot)
                nombres_limpios[i] = nombre_tot
                cols_totales_resumen.append(nombre_tot)
        else:
            meses_pendientes.append((i, t))

    return nombres_limpios, cols_anuales, meta_mensuales, cols_totales_resumen


def limpiar_texto(valor):
    if pd.isna(valor):
        return np.nan
    limpio = re.sub(r"\s+", " ", str(valor)).strip()
    return limpio if limpio != "" else np.nan


def convertir_fecha_excel(valor):
    """Convierte tanto fechas seriales de Excel (ej. 46310) como textos DD/MM/AAAA."""
    if pd.isna(valor):
        return pd.NaT
    if isinstance(valor, (int, float, np.integer, np.floating)):
        if 20000 <= float(valor) <= 60000:
            return pd.to_datetime(float(valor), unit="D", origin="1899-12-30", errors="coerce")
        return pd.NaT
    if isinstance(valor, (datetime, pd.Timestamp)):
        return pd.to_datetime(valor)
    texto = str(valor).strip().replace("//", "/").replace("'", "")
    return pd.to_datetime(texto, dayfirst=True, errors="coerce")


def normalizar_categoria_socio(valor) -> str:
    if pd.isna(valor):
        return "SIN_CLASIFICAR"
    v = str(valor).upper()
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


def ejecutar_ingesta_y_etl(origen_path: Path, base_dir: Path = Path("sibda_1380")) -> dict:
    """Paso completo de extracción segura (sin tocar el Excel original) y limpieza ETL."""
    origen_path = Path(origen_path)
    carpetas = {
        "raw": base_dir / "datalake" / "raw",
        "bronze": base_dir / "datalake" / "bronze",
        "silver": base_dir / "datalake" / "silver",
        "gold": base_dir / "datalake" / "gold",
        "warehouse": base_dir / "warehouse",
        "backups": base_dir / "backups",
        "reportes": base_dir / "reportes",
    }
    for carpeta in carpetas.values():
        carpeta.mkdir(parents=True, exist_ok=True)

    # 1. Huella digital del original y copia a /raw
    hash_inicio = sha256_file(origen_path)
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    copia_raw = carpetas["raw"] / f"raw_{marca_tiempo}_{origen_path.name}"
    shutil.copy2(origen_path, copia_raw)
    assert sha256_file(copia_raw) == hash_inicio, "La copia en /raw no coincide con el original."

    libro = openpyxl.load_workbook(copia_raw, read_only=True, data_only=False)
    nombre_hoja = libro.sheetnames[0]
    libro.close()

    df_raw = pd.read_excel(copia_raw, sheet_name=nombre_hoja, dtype=object)
    df = df_raw.copy()

    nombres_limpios, cols_anuales, meta_mensuales, cols_resumen = mapear_esquema_dinamico(list(df.columns))
    df.columns = nombres_limpios
    df["id_benefactor"] = range(1, len(df) + 1)
    df["cod"] = pd.to_numeric(df["cod"], errors="coerce").astype("Int64")

    # Alias de compatibilidad para cualquier consulta
    df["nombre_completo_token"] = df["donante_benefactor"]
    df["lo_atendera_raw"] = df["empleada_telemercaderista"]

    columnas_texto = [
        "socio_raw", "trato_raw", "donante_benefactor", "empleada_telemercaderista",
        "cedula_token", "telefono_token", "direccion_token", "barrio_token",
        "municipio_raw", "mes_cump_raw", "mensajes_cumpleanos", "detalle_cumpleanos",
        "whatsapp_flag", "encuesta_eventos", "email_token", "donacion_extra_raw",
        "gestion_log", "llamar_bonos_2026", "calamidad", "enfermo",
        "observaciones_comentarios", "tipo_pago_raw", "recogerle_dia", "frecuencia_raw",
        "recibos_preferencia_raw", "recibos_numeros", "alcancia_raw", "bono_2026_raw",
        "cantarilla_2026_raw", "rifa_virgen_carmen_raw",
    ]
    for col in columnas_texto:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_texto)

    df["socio_categoria"] = df["socio_raw"].apply(normalizar_categoria_socio)
    mapa_pagos = {"DO": "DOMICILIO", "CO": "CONSIGNACION", "TR": "TRANSFERENCIA", "SE": "SEDE", "DE": "DEBITO"}
    df["tipo_pago_norm"] = df["tipo_pago_raw"].map(
        lambda x: mapa_pagos.get(str(x).upper(), "OTRO_O_INVALIDO") if pd.notna(x) else "NO_ESPECIFICADO"
    )

    df["fecha_ingreso_norm"] = df["fecha_ingreso_raw"].apply(convertir_fecha_excel)
    df["ult_pago_norm"] = df["ult_pago_raw"].apply(convertir_fecha_excel)
    df["flag_fecha_ingreso_invalida"] = df["fecha_ingreso_raw"].notna() & df["fecha_ingreso_norm"].isna()
    df["flag_ult_pago_invalido"] = df["ult_pago_raw"].notna() & df["ult_pago_norm"].isna()

    df["cuota_valor_num"] = pd.to_numeric(df["cuota_raw"], errors="coerce")
    df["bono_2026_valor_num"] = pd.to_numeric(df["bono_2026_raw"], errors="coerce")
    df["recogerle_dia_num"] = pd.to_numeric(df["recogerle_dia"], errors="coerce").astype("Int64")

    # Unir notas en texto libre para detectar familia y solicitudes de no llamar
    cols_notas = [
        "socio_raw", "trato_raw", "mensajes_cumpleanos", "detalle_cumpleanos",
        "encuesta_eventos", "donacion_extra_raw", "gestion_log", "llamar_bonos_2026",
        "calamidad", "enfermo", "observaciones_comentarios", "recibos_preferencia_raw",
        "alcancia_raw", "bono_2026_raw", "cantarilla_2026_raw", "rifa_virgen_carmen_raw",
    ]
    df["texto_notas_unido"] = df[cols_notas].fillna("").agg(" | ".join, axis=1)

    patron_familia = r"\b(esposo|esposa|esposos|familia|flia|mam[aá]|pap[aá]|hijo|hija|herman[oa]s?|sobrin[oa]s?|t[ií][oa]s?|amig[oa]s?|dona con)\b"
    patron_no_llamar = r"\b(no llamar|no contactar|retirar|no sigue|no seg|falleci[oó]|muri[oó]|no felicitar|no molestar)\b"

    df["flag_aporte_familiar_amigos"] = (
        df["texto_notas_unido"].str.contains(patron_familia, case=False, regex=True)
        | df["trato_raw"].fillna("").str.contains(r"esposos|se[ñn]ores|familia|flia", case=False, regex=True)
    )
    df["flag_restriccion_no_contacto"] = df["texto_notas_unido"].str.contains(patron_no_llamar, case=False, regex=True)
    df["flag_whatsapp"] = (
        df["whatsapp_flag"].fillna("").str.upper().str.contains("SI")
        | df["mensajes_cumpleanos"].fillna("").str.upper().str.contains("WHATSAPP")
    )
    df["canal_preferido"] = np.where(df["flag_whatsapp"], "WhatsApp / Llamada", "Llamada Telefónica")
    df["flag_nota_sensible_pastoral"] = df["enfermo"].notna() | df["calamidad"].notna()

    # Contar cuántas personas comparten el mismo número de teléfono
    conteo_tel = df["telefono_token"].value_counts(dropna=True)
    df["personas_en_telefono"] = df["telefono_token"].map(conteo_tel).fillna(0).astype(int)
    df["flag_telefono_compartido"] = df["personas_en_telefono"] > 1

    # Girar (unpivot) las columnas de años y meses hacia una tabla vertical de aportes
    cols_detalle = [m["col"] for m in meta_mensuales]
    for c in cols_anuales + cols_detalle + cols_resumen:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df_anual = df.melt(
        id_vars=["id_benefactor", "empleada_telemercaderista"],
        value_vars=cols_anuales,
        var_name="origen_col",
        value_name="monto",
    ).dropna(subset=["monto"])
    df_anual = df_anual[df_anual["monto"] > 0].copy()
    df_anual["anio"] = df_anual["origen_col"].str.extract(r"(\d{4})").astype(int)
    df_anual["mes"] = 12
    df_anual["recurso"] = "Donación directa"

    df_meta = pd.DataFrame(meta_mensuales).rename(columns={"col": "origen_col"})
    df_mensual = df.melt(
        id_vars=["id_benefactor", "empleada_telemercaderista"],
        value_vars=cols_detalle,
        var_name="origen_col",
        value_name="monto",
    ).dropna(subset=["monto"])
    df_mensual = df_mensual[df_mensual["monto"] > 0].merge(df_meta, on="origen_col", how="left")

    df_aportes = pd.concat([df_anual, df_mensual], ignore_index=True)
    df_aportes["fecha_referencia"] = pd.to_datetime(
        df_aportes["anio"].astype(str) + "-" + df_aportes["mes"].astype(str).str.zfill(2) + "-15"
    )
    df_aportes = df_aportes.sort_values(["id_benefactor", "fecha_referencia"]).reset_index(drop=True)
    df_aportes["id_aporte"] = range(1, len(df_aportes) + 1)

    return {
        "run_id": f"ETL_{marca_tiempo}",
        "run_timestamp": marca_tiempo,
        "origen_path": origen_path,
        "hash_inicio": hash_inicio,
        "dirs": carpetas,
        "df_raw": df_raw,
        "df_work": df,
        "df_aportes_long": df_aportes,
    }
