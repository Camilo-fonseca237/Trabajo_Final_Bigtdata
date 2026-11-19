from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
from collections import defaultdict
from typing import Any


def phone_group_token(phone: str, secret: bytes) -> str:
    if not secret:
        raise ValueError("Se requiere una clave secreta no vacía para agrupar teléfonos.")
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        raise ValueError("El número no tiene suficientes dígitos para compararlo.")
    return hmac.new(secret, digits.encode("utf-8"), hashlib.sha256).hexdigest()


def schedule_contacts(
    contacts: list[dict[str, Any]],
    start_date: dt.date,
    max_per_shared_phone_per_day: int = 1,
) -> list[dict[str, Any]]:
    if max_per_shared_phone_per_day < 1:
        raise ValueError("El límite diario debe ser al menos 1.")

    planned: dict[tuple[str, dt.date], int] = defaultdict(int)
    output: list[dict[str, Any]] = []
    for original in contacts:
        contact = dict(original)
        if str(contact.get("do_not_contact", "")).strip().lower() in {
            "1", "true", "sí", "si", "yes"
        }:
            contact["status"] = "excluded_do_not_contact"
            output.append(contact)
            continue
        beneficiary_ref = str(contact.get("beneficiary_ref", "")).strip()
        if not beneficiary_ref:
            raise ValueError("Cada persona requiere su propio beneficiary_ref.")
        group_token = str(contact.get("shared_phone_group_token", "")).strip()
        coordination_key = group_token or f"beneficiary:{beneficiary_ref}"
        requested = contact.get("scheduled_date")
        if requested:
            try:
                candidate = dt.date.fromisoformat(str(requested))
            except ValueError as error:
                raise ValueError("scheduled_date debe tener formato YYYY-MM-DD.") from error
            candidate = max(candidate, start_date)
        else:
            candidate = start_date
        while planned[(coordination_key, candidate)] >= max_per_shared_phone_per_day:
            candidate += dt.timedelta(days=1)
        planned[(coordination_key, candidate)] += 1
        contact["scheduled_date"] = candidate.isoformat()
        contact["status"] = "scheduled"
        output.append(contact)
    return output
