"""
Módulo 5 (Versión ultra clara):
Coordinación de Llamadas entre TELEMERCADERISTAS (empleadas que llaman)
y BENEFACTORES (donantes externos que reciben la llamada).

Evita por completo confundir quién es la Telemercaderista y quién es el Benefactor,
y resuelve el caso obligatorio de los 4 hermanos (Juan, Felipe, Jesús y Daniel).
"""

from datetime import datetime, timedelta
import pandas as pd


class CoordinadorLlamadasSinSaturacion:
    """
    Organiza las llamadas telefónicas cumpliendo dos reglas simples:
    1. Nunca fusiona a los benefactores aunque compartan el mismo teléfono de casa.
    2. Evita que dos telemercaderistas llamen el mismo día al mismo teléfono familiar.
    """

    def __init__(self, df_benefactores: pd.DataFrame, dias_descanso_familiar: int = 2):
        self.df_donantes = df_benefactores.copy()
        self.dias_descanso = dias_descanso_familiar
        # Empleadas de la Fundación que realizan las llamadas
        self.lista_telemercaderistas = [
            "Viviana", "Sandra", "Hna Lina", "Jorge", "Vicmar", "JD", "NSE", "Gloria Trujillo"
        ]
        self.agenda_llamadas = []

    def agregar_telemercaderista(self, nombre_empleada: str) -> None:
        """Registra una nueva empleada telemercaderista en el equipo de la Fundación."""
        nombre = nombre_empleada.strip()
        if nombre and nombre not in self.lista_telemercaderistas:
            self.lista_telemercaderistas.append(nombre)

    def agregar_benefactor_donante(
        self,
        id_benefactor: int,
        cod: int,
        nombre_donante: str,
        telefono_hogar: str,
        empleada_asignada: str,
        recurso_interes: str,
        canal_horario: str,
        restringido: bool = False,
    ) -> None:
        """Agrega un donante individual sin fusionarlo con sus familiares."""
        nuevo_donante = {
            "id_benefactor": id_benefactor,
            "cod": cod,
            "donante_benefactor": nombre_donante,
            "telefono_token": telefono_hogar,
            "empleada_telemercaderista": empleada_asignada,
            "recurso_mayor_contribucion": recurso_interes,
            "canal_preferido": canal_horario,
            "flag_restriccion_no_contacto": restringido,
            "fecha_ultimo_aporte": pd.Timestamp("2026-09-15"),
        }
        self.df_donantes = pd.concat([self.df_donantes, pd.DataFrame([nuevo_donante])], ignore_index=True)
        conteo = self.df_donantes["telefono_token"].value_counts(dropna=True)
        self.df_donantes["personas_en_telefono"] = self.df_donantes["telefono_token"].map(conteo).fillna(0).astype(int)
        self.df_donantes["flag_telefono_compartido"] = self.df_donantes["personas_en_telefono"] > 1

    def programar_llamada(
        self,
        id_benefactor: int,
        empleada_telemercaderista: str,
        fecha_deseada: str,
        recurso_ofrecer: str,
        canal_horario: str = None,
    ) -> dict:
        """Verifica restricciones y teléfonos ocupados antes de agendar una llamada."""
        donante = self.df_donantes[self.df_donantes["id_benefactor"] == id_benefactor].iloc[0]
        nombre_donante = str(donante["donante_benefactor"])
        telefono = str(donante["telefono_token"])
        preferencia = canal_horario or str(donante.get("canal_preferido", "Llamada / Mañana"))
        ult_aporte = str(donante.get("fecha_ultimo_aporte", "Sin dato"))[:10]

        # Regla 1: Respetar si el donante pidió NO ser llamado
        if bool(donante.get("flag_restriccion_no_contacto", False)):
            cita = {
                "id_cita": len(self.agenda_llamadas) + 1,
                "empleada_telemercaderista_que_llama": empleada_telemercaderista,
                "donante_benefactor_que_recibe": nombre_donante,
                "id_benefactor": id_benefactor,
                "telefono_del_hogar": telefono,
                "recurso_que_ofrece": recurso_ofrecer,
                "fecha_solicitada": fecha_deseada,
                "fecha_final_agendada": "NO_AGENDADA",
                "estado_llamada": "BLOQUEADO_NO_CONTACTO",
                "explicacion": "El benefactor tiene restricción activa de no contacto.",
                "canal_y_horario": preferencia,
                "ultimo_aporte": ult_aporte,
            }
            self.agenda_llamadas.append(cita)
            return cita

        # Regla 2: Revisar si ese teléfono ya está ocupado ese día por otra llamada
        fechas_ocupadas = {
            c["fecha_final_agendada"]: c
            for c in self.agenda_llamadas
            if c["telefono_del_hogar"] == telefono and c["estado_llamada"] == "PROGRAMADO"
        }

        if fecha_deseada not in fechas_ocupadas:
            fecha_final = fecha_deseada
            explicacion = "Teléfono libre en la fecha solicitada (aprobado)."
        else:
            cita_previa = fechas_ocupadas[fecha_deseada]
            fecha_cursor = datetime.strptime(fecha_deseada, "%Y-%m-%d")
            while fecha_cursor.strftime("%Y-%m-%d") in fechas_ocupadas:
                fecha_cursor += timedelta(days=self.dias_descanso)
            fecha_final = fecha_cursor.strftime("%Y-%m-%d")
            explicacion = (
                f"Reprogramado +{self.dias_descanso} días: el {fecha_deseada} ya llama "
                f"{cita_previa['empleada_telemercaderista_que_llama']} a su familiar "
                f"{cita_previa['donante_benefactor_que_recibe']}."
            )

        cita = {
            "id_cita": len(self.agenda_llamadas) + 1,
            "empleada_telemercaderista_que_llama": empleada_telemercaderista,
            "donante_benefactor_que_recibe": nombre_donante,
            "id_benefactor": id_benefactor,
            "telefono_del_hogar": telefono,
            "recurso_que_ofrece": recurso_ofrecer,
            "fecha_solicitada": fecha_deseada,
            "fecha_final_agendada": fecha_final,
            "estado_llamada": "PROGRAMADO",
            "explicacion": explicacion,
            "canal_y_horario": preferencia,
            "ultimo_aporte": ult_aporte,
        }
        self.agenda_llamadas.append(cita)
        return cita

    def ver_tabla_agenda(self) -> pd.DataFrame:
        return pd.DataFrame(self.agenda_llamadas)


# Alias de compatibilidad
GestorContactosTelemercadeo = CoordinadorLlamadasSinSaturacion
