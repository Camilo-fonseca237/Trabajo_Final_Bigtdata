"""
Módulo 5: Gestión de Telemercaderistas y Control Anti-Saturación de Teléfonos Compartidos.

Conserva a cada benefactor como persona independiente, permite incorporar nuevos usuarios
telemercaderistas, respeta las restricciones de no contacto y coordina automáticamente
las llamadas a números compartidos (incluyendo el caso obligatorio de Juan, Felipe, Jesús y Daniel).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


class GestorContactosTelemercadeo:
    """Motor operativo de programación de contactos y prevención de saturación telefónica familiar."""

    def __init__(self, df_benefactores: pd.DataFrame, dias_enfriamiento_familiar: int = 2):
        self.df_padron = df_benefactores.copy()
        self.dias_enfriamiento = dias_enfriamiento_familiar
        self.telemercaderistas = sorted(
            set(["Viviana", "Sandra", "Hna Lina", "Jorge", "Vicmar", "JD", "NSE", "Gloria Trujillo"])
        )
        self.agenda = []

    def registrar_telemercaderista(self, nuevo_usuario: str) -> None:
        nombre = nuevo_usuario.strip()
        if nombre and nombre not in self.telemercaderistas:
            self.telemercaderistas.append(nombre)

    def registrar_benefactor_en_padron(
        self,
        id_benefactor: int,
        cod: int,
        nombre: str,
        telefono: str,
        responsable: str,
        recurso_interes: str,
        horario_canal: str,
        restriccion: str = "NINGUNA",
    ) -> None:
        nuevo = {
            "id_benefactor": id_benefactor,
            "cod": cod,
            "nombre_completo_token": nombre,
            "telefono_token": telefono,
            "lo_atendera_raw": responsable,
            "recurso_mayor_contribucion": recurso_interes,
            "canal_preferido": horario_canal,
            "flag_restriccion_no_contacto": restriccion != "NINGUNA",
            "motivo_restriccion_contacto": restriccion,
            "fecha_ultimo_aporte": pd.Timestamp("2026-09-15"),
        }
        self.df_padron = pd.concat([self.df_padron, pd.DataFrame([nuevo])], ignore_index=True)
        freq = self.df_padron["telefono_token"].value_counts(dropna=True)
        self.df_padron["personas_en_telefono"] = self.df_padron["telefono_token"].map(freq).fillna(0).astype(int)
        self.df_padron["flag_telefono_compartido"] = self.df_padron["personas_en_telefono"] > 1

    def programar_contacto(
        self,
        id_benefactor: int,
        responsable: str,
        fecha_programada: str,
        recurso_gestionar: str,
        preferencias_horario_canal: Optional[str] = None,
        auto_reprogramar_si_colision: bool = True,
    ) -> dict:
        fila = self.df_padron[self.df_padron["id_benefactor"] == id_benefactor]
        if fila.empty:
            raise ValueError(f"No existe id_benefactor={id_benefactor}")
        b = fila.iloc[0]
        tel = str(b["telefono_token"])
        nombre = str(b["nombre_completo_token"])
        pref = preferencias_horario_canal or str(b.get("canal_preferido", "Llamada / Mañana"))
        ult_contacto = str(b.get("fecha_ultimo_aporte", "Sin contacto previo"))[:10]

        if bool(b.get("flag_restriccion_no_contacto", False)):
            reg = {
                "id_gestion": len(self.agenda) + 1,
                "responsable_gestion": responsable,
                "fecha_programada": fecha_programada,
                "recurso_que_se_desea_gestionar": recurso_gestionar,
                "id_benefactor": id_benefactor,
                "benefactor_asignado": nombre,
                "telefono_token": tel,
                "telefono_compartido": bool(b.get("flag_telefono_compartido", False)),
                "personas_en_telefono": int(b.get("personas_en_telefono", 1)),
                "ultimo_contacto_realizado": ult_contacto,
                "resultado_gestion": "BLOQUEADO_POR_RESTRICCION",
                "proxima_accion": "No contactar (Respetar solicitud de exclusión)",
                "preferencias_horario_canal": pref,
                "restricciones_contacto": str(b.get("motivo_restriccion_contacto", "NO_LLAMAR")),
            }
            self.agenda.append(reg)
            return reg

        contactos_mismo_tel = [
            g for g in self.agenda
            if g["telefono_token"] == tel and g["resultado_gestion"] in ["PROGRAMADO", "PENDIENTE"]
        ]
        fechas_ocupadas = {g["fecha_programada"]: g for g in contactos_mismo_tel}

        if fecha_programada not in fechas_ocupadas:
            estado = "PROGRAMADO"
            prox_accion = f"Realizar contacto el {fecha_programada} ({pref})"
            fecha_final = fecha_programada
        else:
            colision = fechas_ocupadas[fecha_programada]
            if auto_reprogramar_si_colision:
                dt_base = datetime.strptime(fecha_programada, "%Y-%m-%d")
                while dt_base.strftime("%Y-%m-%d") in fechas_ocupadas:
                    dt_base += timedelta(days=self.dias_enfriamiento)
                fecha_final = dt_base.strftime("%Y-%m-%d")
                estado = "PROGRAMADO"
                prox_accion = (
                    f"REPROGRAMADO ANTI-SATURACIÓN (de {fecha_programada} a {fecha_final}): "
                    f"teléfono ya reservado el {fecha_programada} por {colision['responsable_gestion']} "
                    f"para {colision['benefactor_asignado']} ({colision['recurso_que_se_desea_gestionar']})."
                )
            else:
                fecha_final = fecha_programada
                estado = "BLOQUEADO_SATURACION_FAMILIAR"
                prox_accion = (
                    f"Colisión con gestión de {colision['responsable_gestion']} "
                    f"para {colision['benefactor_asignado']} en la misma fecha."
                )

        reg = {
            "id_gestion": len(self.agenda) + 1,
            "responsable_gestion": responsable,
            "fecha_programada": fecha_final,
            "recurso_que_se_desea_gestionar": recurso_gestionar,
            "id_benefactor": id_benefactor,
            "benefactor_asignado": nombre,
            "telefono_token": tel,
            "telefono_compartido": bool(b.get("flag_telefono_compartido", False)),
            "personas_en_telefono": int(b.get("personas_en_telefono", 1)),
            "ultimo_contacto_realizado": ult_contacto,
            "resultado_gestion": estado,
            "proxima_accion": prox_accion,
            "preferencias_horario_canal": pref,
            "restricciones_contacto": "NINGUNA",
        }
        self.agenda.append(reg)
        return reg

    def obtener_agenda_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.agenda)
