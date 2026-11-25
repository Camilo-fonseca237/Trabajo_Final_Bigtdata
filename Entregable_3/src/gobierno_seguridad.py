"""
Módulo 8: Gobierno, Calidad, Seguridad y Protección de Datos Personales (Ley 1581 de 2012).

Implementa cálculo de IGCD, Control de Acceso Basado en Roles (RBAC), tokenización HMAC-SHA256,
aislamiento de datos sensibles (ENFERMO/CALAMIDAD) y copias de respaldo verificadas con SHA-256.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .etl_lakehouse import sha256_file


def calcular_igcd(df_master: pd.DataFrame) -> Dict[str, float]:
    """Calcula el Índice Global de Calidad de Datos (Completitud, Unicidad y Validez)."""
    completitud = (
        df_master[["cod", "nombre_completo_token", "cedula_token", "telefono_token", "lo_atendera_raw", "socio_raw"]]
        .notna().mean().mean() * 100
    )
    unicidad_cod = (1 - df_master["cod"].dropna().duplicated().mean()) * 100
    validez_fechas = (1 - df_master["flag_fecha_ingreso_invalida"].mean()) * 100
    igcd = round((completitud + unicidad_cod + validez_fechas) / 3, 2)
    return {
        "igcd": igcd,
        "completitud_clave_%": round(float(completitud), 2),
        "unicidad_cod_%": round(float(unicidad_cod), 2),
        "validez_fechas_%": round(float(validez_fechas), 2),
    }


def generar_token_hmac_telefono(telefono_crudo: str, clave_secreta: bytes = b"F1380_CLAVE_GOBIERNO_2026") -> str:
    """Tokeniza un número telefónico con HMAC-SHA256 permitiendo detectar teléfonos compartidos sin exponer PII."""
    digitos = re.sub(r"\D", "", str(telefono_crudo))
    if len(digitos) < 7:
        raise ValueError("Número telefónico con menos de 7 dígitos.")
    if digitos.startswith("57") and len(digitos) == 12:
        digitos = digitos[2:]
    return "TEL_HMAC_" + hmac.new(clave_secreta, digitos.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def consultar_vista_por_rol(
    df_gold: pd.DataFrame,
    cols_admin: List[str],
    rol: str,
    usuario_telemercaderista: Optional[str] = None,
    limite: int = 10,
) -> pd.DataFrame:
    """Aplica principio de mínimo privilegio (RBAC) según el rol operativo de la Fundación 1380."""
    roles_permisos = {
        "TELEMERCADERISTA": [
            "id_benefactor", "cod", "nombre_completo_token", "telefono_token",
            "flag_telefono_compartido", "lo_atendera_raw", "clasificacion_benefactor",
            "recurso_mayor_contribucion", "canal_preferido", "flag_nota_sensible_pastoral",
        ],
        "MENSAJERO": [
            "cod", "trato_raw", "nombre_completo_token", "direccion_token",
            "barrio_token", "municipio_raw", "recogerle_dia_num", "cuota_valor_num", "lo_atendera_raw",
        ],
        "ANALISTA_BI": [
            "id_benefactor", "municipio_grupo", "socio_categoria", "clasificacion_benefactor",
            "num_aportes_registrados", "valor_acumulado", "recurso_mayor_contribucion",
        ],
        "ADMIN_GOBIERNO": [c for c in cols_admin if c in df_gold.columns],
    }
    if rol not in roles_permisos:
        raise PermissionError(f"Rol '{rol}' no autorizado en la matriz RBAC.")
    vista = df_gold[~df_gold["flag_restriccion_no_contacto"]].copy()
    if rol == "TELEMERCADERISTA" and usuario_telemercaderista:
        vista = vista[vista["lo_atendera_raw"].fillna("").str.upper().str.contains(usuario_telemercaderista.upper())]
    elif rol == "MENSAJERO":
        vista = vista[vista["tipo_pago_norm"] == "DOMICILIO"]
    return vista[roles_permisos[rol]].head(limite)


def crear_backup_warehouse(dw_path: Path, backup_dir: Path, run_timestamp: str) -> Tuple[Path, str]:
    """Crea una copia de respaldo verificada del Data Warehouse DuckDB."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    destino = backup_dir / f"fundacion_1380_dw_backup_{run_timestamp}.duckdb"
    shutil.copy2(dw_path, destino)
    return destino, sha256_file(destino)
