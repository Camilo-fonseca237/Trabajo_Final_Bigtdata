#!/usr/bin/env python3
"""
Módulo 7: Script Batch para el Mensajero – Fundación 1380 (SIBDA-1380).

Ejecuta el proceso de extracción por lotes (batch) de las transacciones registradas durante
el día anterior a la fecha de corte, filtra exclusivamente aquellas que requieren gestión
logística física, organiza la hoja de ruta por Municipio -> Barrio -> Dirección y genera
reportes en formato imprimible (HTML listo para impresión/PDF + CSV + TXT operativo)
aplicando estricta minimización de datos personales (Ley 1581 de 2012).

Uso por línea de comandos:
    python Entregable_3/batch_mensajero.py --fecha-corte 2026-10-16
    python Entregable_3/batch_mensajero.py --auto-ultima-fecha
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

# Permitir importación tanto desde la raíz del repositorio como desde Entregable_3/
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Entregable_3.src.etl_lakehouse import ejecutar_ingesta_y_etl, sha256_file  # noqa: E402


COLUMNAS_PERMITIDAS_MENSAJERO = [
    "orden_ruta",
    "parada_fisica",
    "cod",
    "trato",
    "benefactor_token",
    "municipio",
    "barrio_token",
    "direccion_token",
    "telefono_contacto_token",
    "tipo_gestion_logistica",
    "dia_ventana_recogida",
    "recibo_referencia",
    "valor_recaudo_cop",
    "responsable_telemercadeo",
    "firma_y_estado_entrega",
]

COLUMNAS_PROHIBIDAS_PRIVACIDAD = {
    "cedula_token",
    "email_token",
    "enfermo",
    "calamidad",
    "observaciones_comentarios",
    "valor_acumulado",
    "clasificacion_benefactor",
    "anio_nac_raw",
    "dia_cump_raw",
    "mes_cump_raw",
}


def _estimar_monto_operacion_reciente(row: pd.Series, fecha_tx: pd.Timestamp) -> float:
    """Obtiene el monto asociado a la operación reciente o la cuota acordada de domicilio."""
    anio_tx = fecha_tx.year
    mes_tx = fecha_tx.month
    prefijo_mes = f"{anio_tx}_{mes_tx:02d}_"
    suma_mes = 0.0
    for col in row.index:
        if str(col).startswith(prefijo_mes):
            val = pd.to_numeric(row[col], errors="coerce")
            if pd.notna(val) and float(val) > 0:
                suma_mes += float(val)
    if suma_mes > 0:
        return suma_mes
    cuota = pd.to_numeric(row.get("cuota_valor_num", np.nan), errors="coerce")
    if pd.notna(cuota) and float(cuota) > 0:
        return float(cuota)
    bono = pd.to_numeric(row.get("bono_2026_valor_num", np.nan), errors="coerce")
    if pd.notna(bono) and float(bono) > 0:
        return float(bono)
    return 0.0


def _extraer_ultimo_recibo(recibos_str) -> str:
    if pd.isna(recibos_str) or str(recibos_str).strip() == "":
        return "POR_EMITIR"
    partes = [p for p in re.split(r"[-,\s]+", str(recibos_str).strip()) if p]
    return partes[-1] if partes else "POR_EMITIR"


def generar_html_imprimible_mensajero(resumen: Dict[str, object], df_ruta: pd.DataFrame) -> str:
    """Genera un documento HTML con diseño A4/Carta (@media print) listo para imprimir o guardar en PDF."""
    filas_html = []
    for _, r in df_ruta.iterrows():
        monto_fmt = f"$ {r['valor_recaudo_cop']:,.0f}" if r["valor_recaudo_cop"] > 0 else "Por confirmar"
        filas_html.append(
            f"<tr>"
            f"<td class='c'>{int(r['orden_ruta'])}</td>"
            f"<td class='c'><strong>P-{int(r['parada_fisica']):02d}</strong></td>"
            f"<td class='c'>{r['cod']}</td>"
            f"<td>{r['trato']} {r['benefactor_token']}</td>"
            f"<td>{r['municipio']}</td>"
            f"<td>{r['barrio_token']}</td>"
            f"<td>{r['direccion_token']}</td>"
            f"<td>{r['telefono_contacto_token']}</td>"
            f"<td>{r['tipo_gestion_logistica']}</td>"
            f"<td class='c'>{r['dia_ventana_recogida']}</td>"
            f"<td class='c'>{r['recibo_referencia']}</td>"
            f"<td class='r'>{monto_fmt}</td>"
            f"<td>{r['responsable_telemercadeo']}</td>"
            f"<td class='firma'></td>"
            f"</tr>"
        )
    tabla_body = "\n".join(filas_html) if filas_html else (
        "<tr><td colspan='14' class='c'>No se registraron operaciones con requerimiento logístico en el día anterior.</td></tr>"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Planilla Logística Batch Mensajero – Fundación 1380 ({resumen['fecha_corte']})</title>
  <style>
    :root {{ --azul: #015583; --oscuro: #072A42; --turquesa: #01B3C2; --gris: #F2F2F2; }}
    * {{ box-sizing: border-box; font-family: 'Segoe UI', Calibri, Arial, sans-serif; }}
    body {{ margin: 20px; color: #1e293b; background: #ffffff; font-size: 12px; }}
    .no-print {{ margin-bottom: 14px; display: flex; gap: 10px; align-items: center; }}
    .btn {{ background: var(--azul); color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
    .header {{ border-bottom: 3px solid var(--azul); padding-bottom: 10px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: flex-start; }}
    .header h1 {{ margin: 0; font-size: 18px; color: var(--oscuro); }}
    .header p {{ margin: 3px 0 0; color: #475569; font-size: 11px; }}
    .meta-box {{ background: var(--gris); border-left: 4px solid var(--turquesa); padding: 8px 12px; font-size: 11px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }}
    .kpi {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; background: #f8fafc; }}
    .kpi .lbl {{ font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: 700; }}
    .kpi .val {{ font-size: 16px; font-weight: 800; color: var(--oscuro); margin-top: 2px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10.5px; }}
    th {{ background: var(--oscuro); color: #fff; padding: 6px 5px; text-align: left; font-weight: 600; }}
    td {{ border: 1px solid #cbd5e1; padding: 5px; vertical-align: middle; }}
    tr:nth-child(even) td {{ background: #f8fafc; }}
    .c {{ text-align: center; }}
    .r {{ text-align: right; white-space: nowrap; font-weight: 600; }}
    .firma {{ width: 95px; height: 24px; }}
    .footer {{ margin-top: 18px; display: flex; justify-content: space-between; font-size: 10.5px; color: #475569; gap: 20px; }}
    .sig-line {{ margin-top: 28px; border-top: 1px solid #334155; padding-top: 4px; width: 220px; text-align: center; }}
    .privacy {{ margin-top: 12px; padding: 8px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; font-size: 10px; color: #1e3a8a; }}
    @media print {{
      .no-print {{ display: none !important; }}
      body {{ margin: 6mm; }}
      @page {{ size: landscape; margin: 8mm; }}
    }}
  </style>
</head>
<body>
  <div class="no-print">
    <button class="btn" onclick="window.print()">Imprimir / Guardar como PDF</button>
    <span>Vista optimizada en formato horizontal (Carta / A4) con principio de minimización de datos (Módulo 7 y Módulo 8).</span>
  </div>

  <div class="header">
    <div>
      <h1>FUNDACIÓN 1380 – PLANILLA DIARIA DE DESPACHO Y RECAUDO (PROCESO BATCH MENSAJERO)</h1>
      <p>Sistema Integrado SIBDA-1380 | Extracción automática de transacciones del día anterior que requieren gestión logística</p>
    </div>
    <div class="meta-box">
      <div><strong>Fecha de corte:</strong> {resumen['fecha_corte']}</div>
      <div><strong>Día anterior consultado:</strong> {resumen['fecha_dia_anterior']}</div>
      <div><strong>Ejecución Batch ID:</strong> {resumen['batch_id']}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi">
      <div class="lbl">1. Transacciones Día Anterior</div>
      <div class="val">{resumen['total_transacciones_dia_anterior']} registros</div>
    </div>
    <div class="kpi">
      <div class="lbl">2. Registros Logísticos Filtrados</div>
      <div class="val">{resumen['total_registros_logisticos']} envíos/recaudos</div>
    </div>
    <div class="kpi">
      <div class="lbl">3. Paradas Físicas Optimizadas</div>
      <div class="val">{resumen['paradas_fisicas_unicas']} direcciones</div>
    </div>
    <div class="kpi">
      <div class="lbl">4. Valor Estimado a Recaudar</div>
      <div class="val">COP $ {resumen['valor_total_recaudo_cop']:,.0f}</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th class="c">#</th>
        <th class="c">Parada</th>
        <th class="c">COD</th>
        <th>Benefactor (Token)</th>
        <th>Municipio</th>
        <th>Barrio</th>
        <th>Dirección Logística</th>
        <th>Teléfono Contacto</th>
        <th>Gestión Logística</th>
        <th class="c">Día Ruta</th>
        <th class="c">Recibo Ref.</th>
        <th class="r">Valor Operación</th>
        <th>Responsable</th>
        <th class="c">Firma / Novedad</th>
      </tr>
    </thead>
    <tbody>
      {tabla_body}
    </tbody>
  </table>

  <div class="privacy">
    <strong>Aviso de Gobierno y Protección de Datos (Ley 1581 de 2012):</strong> Este reporte contiene exclusivamente los atributos operativos mínimos para la ruta logística del mensajero. Se han suprimido automáticamente número de cédula, correo electrónico, historial patrimonial acumulado, clasificación analítica y notas sensibles de salud o calamidad (<code>ENFERMO</code> / <code>CALAMIDAD</code>). Prohibida su reproducción o uso fuera de la operación autorizada.
  </div>

  <div class="footer">
    <div class="sig-line">Firma Coordinación Telemercadeo / Despacho</div>
    <div class="sig-line">Firma Mensajero Asignado (Recibido de Ruta)</div>
    <div class="sig-line">Firma Tesorería (Arqueo y Entrega de Recibos)</div>
  </div>
</body>
</html>
"""


def ejecutar_batch_mensajero(
    df_work: pd.DataFrame,
    reportes_dir: Path,
    fecha_corte: Optional[str] = None,
    auto_ultima_fecha: bool = False,
) -> Dict[str, object]:
    """
    Ejecuta los 6 pasos obligatorios del Módulo 7:
      1. Identificar la fecha de corte.
      2. Consultar las transacciones registradas durante el día anterior.
      3. Filtrar los registros que requieran gestión logística.
      4. Organizar la información necesaria para el mensajero (Municipio -> Barrio -> Dirección -> COD).
      5. Generar reporte en formato imprimible (HTML imprimible + CSV + TXT).
      6. Mostrar y retornar el total de registros encontrados.
    """
    reportes_dir = Path(reportes_dir)
    reportes_dir.mkdir(parents=True, exist_ok=True)

    # Paso 1: Identificar la fecha de corte
    fechas_validas = df_work["ult_pago_norm"].dropna()
    fechas_validas = fechas_validas[(fechas_validas >= pd.Timestamp("2000-01-01")) & (fechas_validas <= pd.Timestamp.now() + pd.Timedelta(days=5))]

    if fecha_corte:
        dt_corte = pd.Timestamp(fecha_corte).normalize()
    elif auto_ultima_fecha and not fechas_validas.empty:
        # Toma el día siguiente a la última jornada con múltiples transacciones operativas en el Excel
        conteo_fechas = fechas_validas.dt.normalize().value_counts()
        fechas_activas = conteo_fechas[conteo_fechas >= 5].index
        ultima_jornada = fechas_activas.max() if len(fechas_activas) > 0 else fechas_validas.max().normalize()
        dt_corte = ultima_jornada + pd.Timedelta(days=1)
    else:
        dt_corte = pd.Timestamp(datetime.now().date())

    dt_dia_anterior = dt_corte - pd.Timedelta(days=1)
    str_corte = dt_corte.strftime("%Y-%m-%d")
    str_ayer = dt_dia_anterior.strftime("%Y-%m-%d")

    # Paso 2: Consultar transacciones registradas durante el día anterior
    mask_ayer = df_work["ult_pago_norm"].dt.normalize() == dt_dia_anterior
    df_tx_ayer = df_work[mask_ayer].copy()
    total_tx_ayer = len(df_tx_ayer)

    # Paso 3: Filtrar registros que requieran gestión logística (excluyendo restricciones de no contacto)
    if not df_tx_ayer.empty:
        mask_recibo_fisico = df_tx_ayer["recibos_preferencia_raw"].fillna("").str.contains(
            r"\b(?:SI|SÍ|DOMICILIO|ENVIAR|FISICO|FÍSICO|CASA)\b", case=False, regex=True
        )
        mask_logistica = (
            ~df_tx_ayer["flag_restriccion_no_contacto"].astype(bool)
            & (
                (df_tx_ayer["tipo_pago_norm"] == "DOMICILIO")
                | df_tx_ayer["recogerle_dia"].notna()
                | df_tx_ayer["alcancia_raw"].notna()
                | mask_recibo_fisico
            )
        )
        df_log = df_tx_ayer[mask_logistica].copy()
    else:
        df_log = df_tx_ayer.copy()

    # Paso 4: Organizar únicamente la información necesaria para el mensajero (minimización PII)
    # Nota clara de roles:
    # - donante_benefactor       -> Persona externa a visitar en ruta (benefactor_token)
    # - empleada_telemercaderista -> Empleada de la Fundación que gestionó la llamada (responsable_telemercadeo)
    registros_salida = []
    for _, row in df_log.iterrows():
        tp = str(row.get("tipo_pago_norm", ""))
        if tp == "DOMICILIO" or pd.notna(row.get("recogerle_dia")):
            tipo_gest = "Recaudo a domicilio"
        elif pd.notna(row.get("alcancia_raw")):
            tipo_gest = "Recogida de alcancía"
        else:
            tipo_gest = "Entrega física de recibo"

        donante_val = row.get("donante_benefactor", row.get("nombre_completo_token"))
        telemercaderista_val = row.get("empleada_telemercaderista", row.get("lo_atendera_raw"))
        dia_rec = str(row["recogerle_dia"]) if pd.notna(row.get("recogerle_dia")) else "Ruta diaria"
        registros_salida.append({
            "cod": str(row["cod"]) if pd.notna(row["cod"]) else str(row["id_benefactor"]),
            "trato": str(row["trato_raw"]) if pd.notna(row["trato_raw"]) else "Benefactor(a)",
            "benefactor_token": str(donante_val) if pd.notna(donante_val) else "SIN_TOKEN",
            "municipio": str(row["municipio_raw"]) if pd.notna(row["municipio_raw"]) else "Por confirmar",
            "barrio_token": str(row["barrio_token"]) if pd.notna(row["barrio_token"]) else "SIN_BARRIO",
            "direccion_token": str(row["direccion_token"]) if pd.notna(row["direccion_token"]) else "POR_CONFIRMAR_DIR",
            "telefono_contacto_token": str(row["telefono_token"]) if pd.notna(row["telefono_token"]) else "SIN_TEL",
            "tipo_gestion_logistica": tipo_gest,
            "dia_ventana_recogida": dia_rec,
            "recibo_referencia": _extraer_ultimo_recibo(row.get("recibos_numeros", np.nan)),
            "valor_recaudo_cop": _estimar_monto_operacion_reciente(row, dt_dia_anterior),
            "responsable_telemercadeo": str(telemercaderista_val) if pd.notna(telemercaderista_val) else "SIN_ASIGNAR",
            "firma_y_estado_entrega": "______________________",
        })

    df_ruta = pd.DataFrame(registros_salida)
    if not df_ruta.empty:
        df_ruta["_cod_num"] = pd.to_numeric(df_ruta["cod"], errors="coerce").fillna(999999)
        df_ruta = df_ruta.sort_values(["municipio", "barrio_token", "direccion_token", "_cod_num"]).drop(columns=["_cod_num"]).reset_index(drop=True)
        df_ruta["orden_ruta"] = range(1, len(df_ruta) + 1)
        # Consolidar paradas físicas cuando dos miembros del mismo hogar comparten dirección exacta
        claves_parada = df_ruta["municipio"] + "|" + df_ruta["direccion_token"]
        mapa_paradas = {k: i + 1 for i, k in enumerate(dict.fromkeys(claves_parada))}
        df_ruta["parada_fisica"] = claves_parada.map(mapa_paradas)
        df_ruta = df_ruta[COLUMNAS_PERMITIDAS_MENSAJERO]
    else:
        df_ruta = pd.DataFrame(columns=COLUMNAS_PERMITIDAS_MENSAJERO)

    # Verificación estricta de privacidad (ninguna columna prohibida puede existir en el reporte)
    assert COLUMNAS_PROHIBIDAS_PRIVACIDAD.isdisjoint(set(df_ruta.columns)), "Violación de minimización de datos en reporte batch."

    paradas_unicas = int(df_ruta["parada_fisica"].nunique()) if not df_ruta.empty else 0
    valor_total = float(df_ruta["valor_recaudo_cop"].sum()) if not df_ruta.empty else 0.0
    batch_id = f"BATCH_MSG_{str_corte.replace('-', '')}"

    resumen = {
        "batch_id": batch_id,
        "fecha_corte": str_corte,
        "fecha_dia_anterior": str_ayer,
        "total_transacciones_dia_anterior": total_tx_ayer,
        "total_registros_logisticos": len(df_ruta),
        "paradas_fisicas_unicas": paradas_unicas,
        "valor_total_recaudo_cop": valor_total,
    }

    # Paso 5: Generar reportes imprimibles (HTML + CSV + TXT)
    sufijo = str_corte.replace("-", "")
    ruta_html = reportes_dir / f"reporte_mensajero_{sufijo}.html"
    ruta_csv = reportes_dir / f"reporte_mensajero_{sufijo}.csv"
    ruta_txt = reportes_dir / f"reporte_mensajero_{sufijo}.txt"

    html_str = generar_html_imprimible_mensajero(resumen, df_ruta)
    ruta_html.write_text(html_str, encoding="utf-8")
    df_ruta.to_csv(ruta_csv, index=False, encoding="utf-8-sig")

    lineas_txt = [
        "=" * 96,
        "FUNDACIÓN 1380 - REPORTE IMPRIMIBLE DE OPERACIÓN LOGÍSTICA (PROCESO BATCH MENSAJERO)",
        "=" * 96,
        f"Fecha de corte             : {str_corte}",
        f"Día anterior consultado    : {str_ayer}",
        f"Total transacciones ayer   : {total_tx_ayer}",
        f"Total registros logísticos : {len(df_ruta)} (en {paradas_unicas} paradas físicas)",
        f"Valor estimado de ruta     : COP ${valor_total:,.0f}",
        "-" * 96,
        df_ruta.drop(columns=["firma_y_estado_entrega"]).to_string(index=False) if not df_ruta.empty else "Sin registros logísticos para la fecha.",
        "=" * 96,
        "NOTA DE PRIVACIDAD: Solo incluye datos logísticos mínimos (sin cédula, email ni notas sensibles).",
    ]
    ruta_txt.write_text("\n".join(lineas_txt), encoding="utf-8")

    # Paso 6: Mostrar en consola el total de registros encontrados
    print(f"[BATCH MENSAJERO] Fecha de corte: {str_corte} | Día anterior consultado: {str_ayer}")
    print(f"[BATCH MENSAJERO] Total transacciones día anterior: {total_tx_ayer} | Registros logísticos encontrados: {len(df_ruta)} ({paradas_unicas} paradas físicas)")
    print(f"[BATCH MENSAJERO] Reporte imprimible generado en: {ruta_html}")

    return {
        "resumen": resumen,
        "df_ruta": df_ruta,
        "ruta_html": ruta_html,
        "ruta_csv": ruta_csv,
        "ruta_txt": ruta_txt,
    }


def main():
    parser = argparse.ArgumentParser(description="Proceso Batch Diario para el Mensajero - Fundación 1380")
    parser.add_argument(
        "--excel",
        type=str,
        default=str(ROOT_DIR / "Recursos" / "BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx"),
        help="Ruta al archivo Excel fuente (se leerá de forma inmutable sin modificarlo).",
    )
    parser.add_argument(
        "--fecha-corte",
        type=str,
        default=None,
        help="Fecha de corte en formato YYYY-MM-DD (consulta transacciones de fecha_corte - 1 día).",
    )
    parser.add_argument(
        "--auto-ultima-fecha",
        action="store_true",
        help="Detecta automáticamente la última jornada activa del Excel como referencia operativa.",
    )
    parser.add_argument(
        "--salida-dir",
        type=str,
        default=str(ROOT_DIR / "sibda_1380" / "reportes"),
        help="Directorio donde se exportarán los reportes imprimibles.",
    )
    args = parser.parse_args()

    excel_path = Path(args.excel)
    hash_antes = sha256_file(excel_path)
    ctx = ejecutar_ingesta_y_etl(excel_path, base_dir=ROOT_DIR / "sibda_1380")
    ejecutar_batch_mensajero(
        df_work=ctx["df_work"],
        reportes_dir=Path(args.salida_dir),
        fecha_corte=args.fecha_corte,
        auto_ultima_fecha=args.auto_ultima_fecha,
    )
    hash_despues = sha256_file(excel_path)
    assert hash_antes == hash_despues, "Error crítico: el archivo Excel original fue modificado."


if __name__ == "__main__":
    main()
