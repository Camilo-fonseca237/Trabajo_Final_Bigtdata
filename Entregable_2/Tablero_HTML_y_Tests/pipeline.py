from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import re
import sqlite3
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
YEARS = list(range(2008, 2027))
MONTHS_2026 = [
    "ENERO",
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
    "JUNIO",
    "JULIO",
    "AGOSTO",
    "SEPTIEMBRE",
    "OCTUBRE",
    "NOVIEMBRE",
    "DICIEMBRE",
]
RESOURCE_HEADERS = [
    ("Bono 2026", "BONO 2026"),
    ("Cantarilla 2026", "CANTARILLA 2026"),
    ("Rifa Virgen del Carmen", "RIFA DE VIRGEN DEL CARMEM"),
    ("Banquete", "BANQUETE"),
]
EXCEL_DATE_EPOCH = dt.date(1899, 12, 30)
MIN_VALID_PAYMENT_DATE = dt.date(2000, 1, 1)


def normalize_header(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref)
    if not letters:
        raise ValueError(f"Referencia de celda inválida: {cell_ref}")
    result = 0
    for char in letters.group(0):
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(f".//{{{NS_MAIN}}}t"))
        for item in root.findall(f"{{{NS_MAIN}}}si")
    ]


def _read_worksheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in relationships.findall(f"{{{NS_PACKAGE_REL}}}Relationship")
    }
    sheets = workbook.findall(f".//{{{NS_MAIN}}}sheet")
    if not sheets:
        raise ValueError("El libro no contiene hojas de cálculo.")
    relation_id = sheets[0].attrib[f"{{{NS_REL}}}id"]
    target = targets.get(relation_id)
    if not target:
        raise ValueError("No se pudo resolver la primera hoja del libro.")
    if target.startswith("/"):
        return target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def read_xlsx(path: str | Path) -> tuple[list[str], list[dict[str, Any]]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo de entrada: {source}")
    if source.suffix.lower() != ".xlsx":
        raise ValueError("El archivo de entrada debe ser .xlsx.")

    with zipfile.ZipFile(source) as archive:
        strings = _read_shared_strings(archive)
        worksheet_path = _read_worksheet_path(archive)
        root = ET.fromstring(archive.read(worksheet_path))
        xml_rows = root.findall(f".//{{{NS_MAIN}}}sheetData/{{{NS_MAIN}}}row")
        if not xml_rows:
            raise ValueError("La primera hoja del libro está vacía.")

        matrix: list[dict[int, Any]] = []
        for xml_row in xml_rows:
            row: dict[int, Any] = {}
            for cell in xml_row.findall(f"{{{NS_MAIN}}}c"):
                kind = cell.attrib.get("t", "")
                if kind == "inlineStr":
                    value: Any = "".join(
                        node.text or ""
                        for node in cell.findall(f".//{{{NS_MAIN}}}t")
                    )
                else:
                    value_node = cell.find(f"{{{NS_MAIN}}}v")
                    raw = value_node.text if value_node is not None else ""
                    if kind == "s" and raw:
                        value = strings[int(raw)]
                    elif kind == "b" and raw:
                        value = raw == "1"
                    else:
                        value = raw
                row[column_index(cell.attrib["r"])] = value
            matrix.append(row)

    header_row = matrix[0]
    last_column = max(header_row, default=-1)
    headers = [
        str(header_row.get(index, "") or "").strip()
        for index in range(last_column + 1)
    ]
    if not any(headers):
        raise ValueError("No se encontraron encabezados en la primera fila.")

    records: list[dict[str, Any]] = []
    for row in matrix[1:]:
        record = {
            headers[index]: row.get(index, "")
            for index in range(len(headers))
            if headers[index]
        }
        if any(str(value).strip() for value in record.values()):
            records.append(record)
    return headers, records


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("$", "").replace(" ", "")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        tail = text.rsplit(",", 1)[-1]
        text = text.replace(",", ".") if len(tail) <= 2 else text.replace(",", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _get(record: dict[str, Any], key: str) -> Any:
    normalized_key = normalize_header(key)
    for header, value in record.items():
        if normalize_header(header) == normalized_key:
            return value
    return None


def _year_value(record: dict[str, Any], year: int) -> float | None:
    if year < 2024:
        return number(_get(record, str(year)))
    if year == 2024:
        return number(_get(record, "2024"))
    return number(_get(record, f"TOTAL {year}"))


def _date_value(value: Any) -> dt.date | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value

    numeric = number(value)
    if numeric is not None:
        if numeric < 1:
            return None
        try:
            return EXCEL_DATE_EPOCH + dt.timedelta(days=int(numeric))
        except OverflowError:
            return None

    text = str(value).strip()
    if not text:
        return None
    for date_format in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ):
        try:
            return dt.datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def _frequency_category(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    if not text:
        return ""
    standard = {
        "MENSUAL": "Mensual",
        "BIMESTRAL": "Bimestral",
        "TRIMESTRAL": "Trimestral",
        "CUATRIMESTRAL": "Cuatrimestral",
        "SEMESTRAL": "Semestral",
        "ANUAL": "Anual",
    }
    if text in standard:
        return standard[text]
    match = re.fullmatch(r"(\d{1,2})\s*MESES?", text)
    if match:
        return f"{int(match.group(1))} meses"
    return "No estandarizada"


def _activity_summary(
    records: list[dict[str, Any]],
    year_values_by_profile: list[dict[int, float | None]],
    as_of_date: dt.date,
) -> dict[str, Any]:
    year_range = range(2008, 2026)
    frequency_groups = [
        ("0 años", 0, 0),
        ("1 año", 1, 1),
        ("2–4 años", 2, 4),
        ("5–9 años", 5, 9),
        ("10 o más años", 10, len(year_range)),
    ]
    frequency_counts = {label: 0 for label, _, _ in frequency_groups}
    observed_year_values = 0
    positive_year_values = 0
    valid_payment_dates: list[dt.date] = []
    nonempty_payment_dates = 0
    invalid_payment_dates = 0
    future_payment_dates = 0
    pre_2000_payment_dates = 0
    reported_frequency_values: Counter[str] = Counter()

    for record, year_values in zip(records, year_values_by_profile):
        observed_values = [
            year_values[year] for year in year_range if year_values.get(year) is not None
        ]
        active_years = sum(value > 0 for value in observed_values)
        observed_year_values += len(observed_values)
        positive_year_values += active_years
        for label, lower, upper in frequency_groups:
            if lower <= active_years <= upper:
                frequency_counts[label] += 1
                break

        raw_date = _get(record, "ULT PAGO")
        parsed_date = _date_value(raw_date)
        if raw_date is not None and str(raw_date).strip():
            nonempty_payment_dates += 1
            if parsed_date is None:
                invalid_payment_dates += 1
            elif parsed_date < MIN_VALID_PAYMENT_DATE:
                pre_2000_payment_dates += 1
            elif parsed_date > as_of_date:
                future_payment_dates += 1
            else:
                valid_payment_dates.append(parsed_date)

        raw_frequency = _get(record, "Frecuencia")
        if raw_frequency is not None and str(raw_frequency).strip():
            category = _frequency_category(raw_frequency)
            reported_frequency_values[category] += 1

    recency_labels = [
        ("0–30 días", 0, 30),
        ("31–90 días", 31, 90),
        ("91–180 días", 91, 180),
        ("181–365 días", 181, 365),
        ("Más de 365 días", 366, None),
    ]
    recency_counts = {label: 0 for label, _, _ in recency_labels}
    for payment_date in valid_payment_dates:
        days_since = (as_of_date - payment_date).days
        for label, lower, upper in recency_labels:
            if days_since >= lower and (upper is None or days_since <= upper):
                recency_counts[label] += 1
                break

    valid_count = len(valid_payment_dates)
    return {
        "as_of_date": as_of_date.isoformat(),
        "frequency_basis": "Años con aporte positivo entre 2008 y 2025; celdas vacías no se imputan.",
        "frequency_distribution": [
            {"category": label, "beneficiaries": frequency_counts[label]}
            for label, _, _ in frequency_groups
        ],
        "observed_annual_cells": observed_year_values,
        "positive_annual_cells": positive_year_values,
        "annual_activity_rate": (
            positive_year_values / observed_year_values if observed_year_values else 0.0
        ),
        "reported_frequency_values": [
            {"category": label, "records": count}
            for label, count in sorted(
                reported_frequency_values.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "last_payment_date": {
            "field": "ULT PAGO",
            "valid_dates": valid_count,
            "records_with_value": nonempty_payment_dates,
            "coverage": valid_count / len(records) if records else 0.0,
            "recency_distribution": [
                {"category": label, "beneficiaries": recency_counts[label]}
                for label, _, _ in recency_labels
            ],
            "invalid_dates": invalid_payment_dates,
            "dates_before_2000": pre_2000_payment_dates,
            "dates_after_as_of": future_payment_dates,
        },
    }


def _segment(year_values: dict[int, float | None]) -> str:
    observed_positive = [year for year, amount in year_values.items() if amount and amount > 0]
    recent_positive = sum(
        1 for year in (2023, 2024, 2025, 2026)
        if year_values.get(year) is not None and year_values[year] > 0
    )
    if len(observed_positive) == 1:
        return "Aporte único registrado"
    if observed_positive and not any(
        year_values.get(year) is not None and year_values[year] > 0
        for year in (2024, 2025, 2026)
    ):
        return "Sin aportes recientes"
    if recent_positive >= 3:
        return "Recurrente"
    if observed_positive:
        return "Esporádico"
    return "Sin aportes registrados"


FEATURE_NAMES = [
    "log_aporte_acumulado_2008_2025",
    "anios_con_aporte_2008_2025",
    "log_aporte_2023",
    "log_aporte_2024",
    "log_aporte_2025",
    "anios_activos_2023_2025",
    "ultimo_anio_con_aporte_hasta_2025",
]


def _features(year_values: dict[int, float | None]) -> list[float]:
    past = {year: (year_values.get(year) or 0.0) for year in YEARS if year <= 2025}
    active_years = [year for year, amount in past.items() if amount > 0]
    return [
        math.log1p(sum(past.values())),
        float(len(active_years)),
        math.log1p(past.get(2023, 0.0)),
        math.log1p(past.get(2024, 0.0)),
        math.log1p(past.get(2025, 0.0)),
        float(sum(past.get(year, 0.0) > 0 for year in (2023, 2024, 2025))),
        float(max(active_years, default=2007)),
    ]


def _sigmoid(value: float) -> float:
    value = max(-35.0, min(35.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def _stratified_split(
    examples: list[tuple[list[float], int]],
    seed: int = 1380,
) -> tuple[list[tuple[list[float], int]], list[tuple[list[float], int]]]:
    import random

    rng = random.Random(seed)
    by_class: dict[int, list[tuple[list[float], int]]] = defaultdict(list)
    for example in examples:
        by_class[example[1]].append(example)
    train: list[tuple[list[float], int]] = []
    test: list[tuple[list[float], int]] = []
    for label in sorted(by_class):
        group = by_class[label]
        rng.shuffle(group)
        test_size = max(1, round(len(group) * 0.2))
        test.extend(group[:test_size])
        train.extend(group[test_size:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def _train_logistic(
    train: list[tuple[list[float], int]],
) -> tuple[list[float], float, list[float], list[float]]:
    if not train or len({label for _, label in train}) != 2:
        raise ValueError("Se requieren ejemplos de las dos clases para entrenar.")
    width = len(train[0][0])
    means = [statistics.mean(row[index] for row, _ in train) for index in range(width)]
    scales = [
        statistics.pstdev(row[index] for row, _ in train) or 1.0
        for index in range(width)
    ]
    standardized = [
        ([(value - means[index]) / scales[index] for index, value in enumerate(row)], label)
        for row, label in train
    ]
    weights = [0.0] * width
    bias = 0.0
    learning_rate = 0.12
    regularization = 0.03
    for _ in range(2500):
        grad_weights = [0.0] * width
        grad_bias = 0.0
        for row, label in standardized:
            error = _sigmoid(bias + sum(w * value for w, value in zip(weights, row))) - label
            grad_bias += error
            for index, value in enumerate(row):
                grad_weights[index] += error * value
        inverse_n = 1.0 / len(standardized)
        bias -= learning_rate * grad_bias * inverse_n
        for index in range(width):
            gradient = grad_weights[index] * inverse_n + regularization * weights[index]
            weights[index] -= learning_rate * gradient
    return weights, bias, means, scales


def _predict_probability(
    row: list[float],
    weights: list[float],
    bias: float,
    means: list[float],
    scales: list[float],
) -> float:
    standardized = [(value - means[i]) / scales[i] for i, value in enumerate(row)]
    return _sigmoid(bias + sum(w * value for w, value in zip(weights, standardized)))


def _auc(labels: list[int], probabilities: list[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(zip(probabilities, labels), key=lambda item: item[0])
    positive_rank_sum = 0.0
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        positive_rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _evaluate(labels: list[int], probabilities: list[float]) -> dict[str, Any]:
    predictions = [int(score >= 0.5) for score in probabilities]
    tp = sum(actual == 1 and predicted == 1 for actual, predicted in zip(labels, predictions))
    tn = sum(actual == 0 and predicted == 0 for actual, predicted in zip(labels, predictions))
    fp = sum(actual == 0 and predicted == 1 for actual, predicted in zip(labels, predictions))
    fn = sum(actual == 1 and predicted == 0 for actual, predicted in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    prevalence = sum(labels) / len(labels) if labels else 0.0
    return {
        "holdout_records": len(labels),
        "threshold": 0.5,
        "accuracy": (tp + tn) / len(labels) if labels else 0.0,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "roc_auc": _auc(labels, probabilities),
        "brier_score": (
            sum((score - label) ** 2 for label, score in zip(labels, probabilities)) / len(labels)
            if labels else 0.0
        ),
        "positive_prevalence": prevalence,
        "confusion_matrix": {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn},
    }


def _summarize(
    headers: list[str],
    records: list[dict[str, Any]],
    as_of_date: dt.date | None = None,
) -> tuple[dict[str, Any], list[str]]:
    if not records:
        raise ValueError("No se encontraron registros de beneficiarios.")
    normalized_headers = {normalize_header(header) for header in headers}
    required_year_headers = [str(year) for year in range(2008, 2024)] + ["2024", "TOTAL 2025", "TOTAL 2026"]
    missing_year_headers = [header for header in required_year_headers if normalize_header(header) not in normalized_headers]
    if missing_year_headers:
        raise ValueError("Faltan columnas históricas necesarias: " + ", ".join(missing_year_headers))

    code_values = [str(_get(record, "COD") or "").strip() for record in records]
    nonempty_codes = [value for value in code_values if value]
    duplicate_codes = sum(count - 1 for count in Counter(nonempty_codes).values() if count > 1)
    source_id_missing = sum(not value for value in code_values)
    missing_counts: dict[str, int] = {}
    for column in ("FECHA (DD-MM-AAA)", "COD", "ULT PAGO", "TOTAL 2025", "TOTAL 2026", "ACUMULADO"):
        missing_counts[column] = sum(
            _get(record, column) is None or str(_get(record, column)).strip() == ""
            for record in records
        )

    profiles: list[dict[str, Any]] = []
    year_values_by_profile: list[dict[int, float | None]] = []
    for record in records:
        year_values = {year: _year_value(record, year) for year in YEARS}
        year_values_by_profile.append(year_values)
        profiles.append(
            {
                "segment": _segment(year_values),
                "features": _features(year_values),
                "target": year_values[2026],
            }
        )

    segment_counts = Counter(profile["segment"] for profile in profiles)
    segment_order = [
        "Recurrente",
        "Esporádico",
        "Aporte único registrado",
        "Sin aportes recientes",
        "Sin aportes registrados",
    ]
    segments = [
        {
            "segment": segment,
            "beneficiaries": segment_counts.get(segment, 0),
            "share": segment_counts.get(segment, 0) / len(records),
        }
        for segment in segment_order
    ]

    year_summary: list[dict[str, Any]] = []
    for year in YEARS:
        period = {
            "year": year,
            "total_amount": 0.0,
            "contributors": 0,
            "records_with_value": 0,
            "by_segment": {},
        }
        for profile, values in zip(profiles, year_values_by_profile):
            amount = values[year]
            if amount is not None:
                period["records_with_value"] += 1
                period["total_amount"] += amount
            if amount is not None and amount > 0:
                period["contributors"] += 1
                segment = profile["segment"]
                cell = period["by_segment"].setdefault(segment, {"contributors": 0, "total_amount": 0.0})
                cell["contributors"] += 1
                cell["total_amount"] += amount
        period["total_amount"] = round(period["total_amount"], 2)
        for cell in period["by_segment"].values():
            cell["total_amount"] = round(cell["total_amount"], 2)
        year_summary.append(period)

    resources: list[dict[str, Any]] = []
    for label, source_header in RESOURCE_HEADERS:
        amounts = [number(_get(record, source_header)) for record in records]
        resources.append(
            {
                "resource": label,
                "source_column": source_header,
                "contributors": sum(value is not None and value > 0 for value in amounts),
                "total_amount": round(sum(value for value in amounts if value is not None), 2),
                "records_with_value": sum(value is not None for value in amounts),
            }
        )
    resource_appearances = sum(resource["contributors"] for resource in resources)
    for resource in resources:
        resource["share_of_resource_records"] = (
            resource["contributors"] / resource_appearances if resource_appearances else 0.0
        )
    resources.sort(key=lambda resource: (-resource["contributors"], resource["resource"]))
    for rank, resource in enumerate(resources, start=1):
        resource["rank"] = rank

    activity = _activity_summary(
        records,
        year_values_by_profile,
        as_of_date or dt.date.today(),
    )

    examples: list[tuple[list[float], int]] = []
    for profile in profiles:
        target = profile["target"]
        if target is not None:
            examples.append((profile["features"], int(target > 0)))
    if len({label for _, label in examples}) == 2 and len(examples) >= 30:
        train, test = _stratified_split(examples)
        weights, bias, means, scales = _train_logistic(train)
        test_labels = [label for _, label in test]
        test_scores = [
            _predict_probability(row, weights, bias, means, scales)
            for row, _ in test
        ]
        model = {
            "status": "evaluado",
            "target": "Registro de aporte positivo en TOTAL 2026",
            "feature_names": FEATURE_NAMES,
            "train_records": len(train),
            "metrics": _evaluate(test_labels, test_scores),
            "seed": 1380,
            "method": "Regresión logística L2; holdout estratificado aleatorio 80/20",
        }
    else:
        model = {
            "status": "no_disponible",
            "target": "Registro de aporte positivo en TOTAL 2026",
            "reason": "La etiqueta disponible no contiene ambas clases o tiene menos de 30 registros.",
        }

    negative_amounts = 0
    for record in records:
        for year in YEARS:
            value = _year_value(record, year)
            negative_amounts += value is not None and value < 0
    quality = {
        "source_rows": len(records),
        "source_columns": len(headers),
        "missing_source_code": source_id_missing,
        "duplicate_nonempty_source_codes": duplicate_codes,
        "missing_values": missing_counts,
        "negative_annual_amounts": negative_amounts,
        "notes": [
            "Las columnas personales (nombres, cédula, teléfono, dirección, correo, salud y comentarios) se excluyeron del análisis y de las salidas.",
            "Los campos anuales son agregados y no equivalen a transacciones individuales.",
            "Las celdas vacías se consideran ausencia de aporte registrado; no prueban que no haya ocurrido un aporte.",
            "El libro no declara fecha de corte verificable; 2026 se trata como periodo posiblemente incompleto.",
            "Los totales anuales y ACUMULADO se conservan como medidas fuente independientes; no se suman entre sí.",
        ],
    }
    summary = {
        "title": "Analítica de benefactores y aportes — Fundación 1380",
        "source_rows": len(records),
        "source_columns": len(headers),
        "segments": segments,
        "years": year_summary,
        "resources": resources,
        "activity": activity,
        "model": model,
        "quality": quality,
        "protection": {
            "individual_records_exported": False,
            "personal_fields_exported": False,
            "model_uses_sensitive_fields": False,
        },
    }
    return summary, segment_order


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_warehouse(output_dir: Path, summary: dict[str, Any]) -> Path:
    db_path = output_dir / "warehouse.sqlite"
    if db_path.exists():
        db_path.unlink()
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE dim_segment (
                segment TEXT PRIMARY KEY,
                beneficiary_count INTEGER NOT NULL,
                share REAL NOT NULL
            );
            CREATE TABLE fact_annual (
                year INTEGER NOT NULL,
                segment TEXT NOT NULL,
                contributor_count INTEGER NOT NULL,
                reported_amount REAL NOT NULL,
                PRIMARY KEY (year, segment),
                FOREIGN KEY (segment) REFERENCES dim_segment(segment)
            );
            CREATE TABLE fact_resource (
                resource TEXT PRIMARY KEY,
                rank INTEGER NOT NULL,
                contributor_count INTEGER NOT NULL,
                reported_amount REAL NOT NULL,
                records_with_value INTEGER NOT NULL,
                share_of_resource_records REAL NOT NULL
            );
            CREATE TABLE fact_activity (
                category_type TEXT NOT NULL,
                category TEXT NOT NULL,
                beneficiary_count INTEGER NOT NULL,
                PRIMARY KEY (category_type, category)
            );
            CREATE TABLE data_quality (
                metric TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE model_evaluation (
                metric TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO dim_segment VALUES (?, ?, ?)",
            [(row["segment"], row["beneficiaries"], row["share"]) for row in summary["segments"]],
        )
        annual_rows = []
        for period in summary["years"]:
            for segment in summary["segments"]:
                values = period["by_segment"].get(segment["segment"], {})
                annual_rows.append(
                    (
                        period["year"],
                        segment["segment"],
                        values.get("contributors", 0),
                        values.get("total_amount", 0.0),
                    )
                )
        connection.executemany("INSERT INTO fact_annual VALUES (?, ?, ?, ?)", annual_rows)
        connection.executemany(
            "INSERT INTO fact_resource VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    row["resource"],
                    row["rank"],
                    row["contributors"],
                    row["total_amount"],
                    row["records_with_value"],
                    row["share_of_resource_records"],
                )
                for row in summary["resources"]
            ],
        )
        activity_rows = [
            ("frequency", row["category"], row["beneficiaries"])
            for row in summary["activity"]["frequency_distribution"]
        ] + [
            ("payment_recency", row["category"], row["beneficiaries"])
            for row in summary["activity"]["last_payment_date"]["recency_distribution"]
        ]
        connection.executemany(
            "INSERT INTO fact_activity VALUES (?, ?, ?)",
            activity_rows,
        )
        connection.executemany(
            "INSERT INTO data_quality VALUES (?, ?)",
            [
                (key, json.dumps(value, ensure_ascii=False))
                for key, value in summary["quality"].items()
            ],
        )
        connection.executemany(
            "INSERT INTO model_evaluation VALUES (?, ?)",
            [
                (key, json.dumps(value, ensure_ascii=False))
                for key, value in summary["model"].items()
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return db_path


def _html_page(title: str, body: str, extra_head: str = "") -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--ink:#14213d;--muted:#526079;--blue:#2457a7;--teal:#138a8a;--paper:#f4f7fb;--card:#fff;--line:#dbe3ee}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Segoe UI,Arial,sans-serif}}
header{{background:linear-gradient(120deg,#153a70,#167f8b);color:white;padding:28px max(22px,calc((100vw - 1180px)/2))}}
header h1{{margin:0;font-size:26px}}header p{{margin:8px 0 0;color:#e3f2f6}}
main{{max-width:1180px;margin:24px auto;padding:0 20px 36px}}h2{{margin:28px 0 12px;font-size:20px}}h3{{font-size:16px;margin:0 0 8px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.card,.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:0 3px 12px #2030470b}}
.metric{{font-size:24px;font-weight:700;color:var(--blue)}}.muted,small{{color:var(--muted)}}.layout{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#eef3f8}}
label{{font-weight:600;margin-right:8px}}select{{padding:8px;border:1px solid #aebbd0;border-radius:6px;background:white}}
.notice{{border-left:4px solid #d89219;padding:10px 14px;background:#fff8e9;margin:12px 0}}
.good{{border-left:4px solid #138a8a;padding:10px 14px;background:#edfafa;margin:12px 0}}
pre{{white-space:pre-wrap;background:#f3f5f8;padding:12px;border-radius:8px;overflow:auto}}
svg{{width:100%;height:auto;display:block}}footer{{border-top:1px solid var(--line);padding-top:12px;color:var(--muted);font-size:13px}}
@media(max-width:760px){{.layout{{grid-template-columns:1fr}}header h1{{font-size:22px}}}}
{extra_head}
</style>
</head>
<body>{body}</body>
</html>"""


def render_dashboard(summary: dict[str, Any]) -> str:
    data = json.dumps(summary, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = f"""
<header><h1>Fundación 1380 · Analítica de benefactores y aportes</h1>
<p>Prototipo local · Información agregada · Sin datos personales en el tablero</p></header>
<main>
<div class="notice"><strong>Uso responsable:</strong> las cifras 2026 pueden estar incompletas; este tablero orienta análisis y no autoriza contactos ni decisiones automáticas.</div>
<div class="cards" id="cards"></div>
<section class="panel" style="margin-top:16px">
<label for="segment">Segmento:</label><select id="segment"></select>
<label for="year">Año:</label><select id="year"></select>
<p class="muted">El filtro anual presenta aportes positivos registrados y montos tal como aparecen en la hoja.</p>
<div class="layout"><div><h2>Benefactores con aporte por año</h2><div id="contributors-chart"></div></div>
<div><h2>Montos reportados por año</h2><div id="amount-chart"></div></div></div>
</section>
<div class="layout">
<section class="panel"><h2>Clasificación histórica</h2><div id="segment-table"></div></section>
<section class="panel"><h2>Recursos con columna identificable</h2><div id="resource-table"></div>
<p class="muted">La base no identifica de forma completa donación directa, bingo, eventos ni visitas; no se les atribuyen intereses.</p></section>
</div>
<section class="panel" style="margin-top:14px"><h2>Frecuencia y último aporte registrado</h2>
<p class="muted">La frecuencia se calcula sobre años con valor positivo 2008–2025. La fecha se interpreta desde ULT PAGO; se excluyen fechas anteriores a 2000, posteriores a la fecha de análisis y valores no interpretables.</p>
<div class="layout"><div><h3>Años con aporte positivo</h3><div id="frequency-table"></div></div>
<div><h3>Antigüedad de ULT PAGO</h3><div id="recency-table"></div><p id="date-coverage" class="muted"></p></div></div></section>
<section class="panel" style="margin-top:14px"><h2>Modelo exploratorio</h2><div id="model"></div>
<p class="muted">Probabilidad histórica de aporte positivo en la etiqueta TOTAL 2026. No es causal, no garantiza respuesta y no debe usarse sin validación temporal ni revisión humana.</p></section>
<section class="panel" style="margin-top:14px"><h2>Prototipo de programación de gestiones</h2>
<p class="muted">Prototipo local: usa solo las gestiones añadidas en esta sesión; no consulta pendientes previos ni los guarda. Ingrese un identificador de beneficiario no sensible y, si existe, el token HMAC de teléfono compartido. Nunca escriba el teléfono aquí.</p>
<div class="layout">
<div><label for="telemarketer">Telemercaderista</label><select id="telemarketer"><option>Viviana</option><option>Sandra</option><option>Lina</option><option value="other">Otra persona</option></select>
<input id="other-telemarketer" aria-label="Nombre o alias de otra persona" placeholder="Nombre o alias" hidden></div>
<div><label for="contact-date">Fecha</label><input id="contact-date" type="date" required></div>
<div><label for="contact-resource">Recurso</label><select id="contact-resource"></select></div>
<div><label for="beneficiary-ref">Referencia individual</label><input id="beneficiary-ref" maxlength="80" autocomplete="off"></div>
<div><label for="phone-group">Token HMAC compartido (opcional)</label><input id="phone-group" maxlength="128" autocomplete="off"></div>
<div><label><input id="do-not-contact" type="checkbox"> No contactar</label></div>
</div>
<button id="schedule-contact" type="button" style="margin-top:12px;padding:9px 16px">Agregar gestión</button>
<p id="planner-status" role="status" aria-live="polite"></p><div id="contact-plan"></div>
</section>
<section class="panel" style="margin-top:14px"><h2>Calidad y cobertura</h2><div id="quality"></div></section>
<footer style="margin-top:22px">Generado a partir de una copia de lectura del Excel. Las salidas analíticas no contienen identificadores, contactos ni filas individuales. La planificación solo permanece en memoria del navegador durante esta sesión.</footer>
</main>
<script>
const D={data};
const fmtInt=n=>new Intl.NumberFormat('es-CO',{{maximumFractionDigits:0}}).format(n);
const fmtMoney=n=>new Intl.NumberFormat('es-CO',{{maximumFractionDigits:0}}).format(n);
function drawBars(rows,field,target,color){{
 const max=Math.max(1,...rows.map(r=>r[field]||0)), w=660, h=220, pad=32, barW=Math.max(8,(w-2*pad)/rows.length*.62), step=(w-2*pad)/rows.length;
 let s=`<svg viewBox="0 0 ${{w}} ${{h}}" role="img"><line x1="${{pad}}" y1="${{h-pad}}" x2="${{w-pad}}" y2="${{h-pad}}" stroke="#9eabc0"/>`;
 rows.forEach((r,i)=>{{const v=r[field]||0,bh=(h-2*pad)*v/max,x=pad+i*step+(step-barW)/2,y=h-pad-bh;s+=`<rect x="${{x}}" y="${{y}}" width="${{barW}}" height="${{bh}}" rx="3" fill="${{color}}"><title>${{r.year}}: ${{fmtInt(v)}}</title></rect><text x="${{x+barW/2}}" y="${{h-10}}" font-size="10" text-anchor="middle" fill="#526079">${{String(r.year).slice(2)}}</text>`;}});
 return s+'</svg>';
}}
const segmentSelect=document.getElementById('segment'),yearSelect=document.getElementById('year');
segmentSelect.innerHTML='<option value="">Todos</option>'+D.segments.map(x=>`<option>${{x.segment}}</option>`).join('');
yearSelect.innerHTML='<option value="">Todos</option>'+D.years.map(x=>`<option value="${{x.year}}">${{x.year}}</option>`).join('');
const resourceSelect=document.getElementById('contact-resource');
resourceSelect.innerHTML=D.resources.map(x=>`<option>${{x.resource}}</option>`).join('');
function selectedYears(){{
 const segment=segmentSelect.value, year=yearSelect.value;
 let rows=D.years.filter(x=>!year||String(x.year)===year);
 if(segment) rows=rows.map(x=>({{...x,contributors:x.by_segment[segment]?.contributors||0,total_amount:x.by_segment[segment]?.total_amount||0}}));
 return rows;
}}
function render(){{
 const year=yearSelect.value?D.years.find(x=>String(x.year)===yearSelect.value):D.years[D.years.length-1];
 const active2026=year.contributors;
 document.getElementById('cards').innerHTML=[
 ['Registros analizados',fmtInt(D.source_rows)],
 ['Aporte positivo · '+year.year,fmtInt(active2026)],
 ['Monto anual reportado',fmtMoney(year.total_amount)],
 ['Códigos fuente faltantes',fmtInt(D.quality.missing_source_code)]
 ].map(([label,value])=>`<div class="card"><small>${{label}}</small><div class="metric">${{value}}</div></div>`).join('');
 const rows=selectedYears();
 document.getElementById('contributors-chart').innerHTML=drawBars(rows,'contributors','', '#2457a7');
 document.getElementById('amount-chart').innerHTML=drawBars(rows,'total_amount','', '#138a8a');
 document.getElementById('segment-table').innerHTML='<table><thead><tr><th>Grupo</th><th>Registros</th><th>%</th></tr></thead><tbody>'+D.segments.map(x=>`<tr><td>${{x.segment}}</td><td>${{fmtInt(x.beneficiaries)}}</td><td>${{(100*x.share).toFixed(1)}}%</td></tr>`).join('')+'</tbody></table>';
 document.getElementById('resource-table').innerHTML='<table><thead><tr><th>#</th><th>Columna fuente</th><th>Aportes &gt; 0</th><th>% de registros recurso</th><th>Monto reportado</th></tr></thead><tbody>'+D.resources.map(x=>`<tr><td>${{x.rank}}</td><td>${{x.resource}}</td><td>${{fmtInt(x.contributors)}}</td><td>${{(100*x.share_of_resource_records).toFixed(1)}}%</td><td>${{fmtMoney(x.total_amount)}}</td></tr>`).join('')+'</tbody></table>';
 document.getElementById('frequency-table').innerHTML='<table><thead><tr><th>Años registrados positivos</th><th>Benefactores</th></tr></thead><tbody>'+D.activity.frequency_distribution.map(x=>`<tr><td>${{x.category}}</td><td>${{fmtInt(x.beneficiaries)}}</td></tr>`).join('')+'</tbody></table><p class="muted">Tasa de actividad entre celdas anuales observadas: ${{(100*D.activity.annual_activity_rate).toFixed(1)}}%.</p>';
 const last=D.activity.last_payment_date;
 document.getElementById('recency-table').innerHTML='<table><thead><tr><th>Antigüedad</th><th>Benefactores</th></tr></thead><tbody>'+last.recency_distribution.map(x=>`<tr><td>${{x.category}}</td><td>${{fmtInt(x.beneficiaries)}}</td></tr>`).join('')+'</tbody></table>';
 document.getElementById('date-coverage').textContent=`Fechas interpretables: ${{fmtInt(last.valid_dates)}} de ${{fmtInt(D.source_rows)}} · corte de análisis: ${{D.activity.as_of_date}}.`;
 const m=D.model;
 document.getElementById('model').innerHTML=m.status==='evaluado'?`<p>Entrenamiento: ${{fmtInt(m.train_records)}} registros · prueba: ${{fmtInt(m.metrics.holdout_records)}} · separación estratificada 80/20.</p><table><tbody><tr><th>Exactitud</th><td>${{(m.metrics.accuracy*100).toFixed(1)}}%</td><th>ROC-AUC</th><td>${{m.metrics.roc_auc.toFixed(3)}}</td></tr><tr><th>Precisión</th><td>${{(m.metrics.precision*100).toFixed(1)}}%</td><th>Recall</th><td>${{(m.metrics.recall*100).toFixed(1)}}%</td></tr><tr><th>F1</th><td>${{m.metrics.f1.toFixed(3)}}</td><th>Brier</th><td>${{m.metrics.brier_score.toFixed(3)}}</td></tr></tbody></table>`:`<p>Modelo no disponible: ${{m.reason}}</p>`;
 document.getElementById('quality').innerHTML=`<p>Hoja: ${{D.source_rows}} registros · ${{D.source_columns}} columnas. Duplicados de código no vacío: ${{fmtInt(D.quality.duplicate_nonempty_source_codes)}}. Registros con TOTAL 2026: ${{fmtInt(year.records_with_value)}}.</p><ul>${{D.quality.notes.map(x=>`<li>${{x}}</li>`).join('')}}</ul>`;
}}
segmentSelect.addEventListener('change',render);yearSelect.addEventListener('change',render);render();
const planItems=[];
const dateInput=document.getElementById('contact-date');
const today=new Date(),todayLocal=new Date(today.getTime()-today.getTimezoneOffset()*60000).toISOString().slice(0,10);
dateInput.min=todayLocal;dateInput.value=todayLocal;
const telemarketerSelect=document.getElementById('telemarketer');
const otherTelemarketer=document.getElementById('other-telemarketer');
telemarketerSelect.addEventListener('change',()=>{{otherTelemarketer.hidden=telemarketerSelect.value!=='other';}});
function renderPlan(){{
 const target=document.getElementById('contact-plan');
 target.replaceChildren();
 if(!planItems.length)return;
 const table=document.createElement('table');
 const head=document.createElement('thead'),headRow=document.createElement('tr');
 ['Beneficiario (referencia)','Telemercaderista','Fecha asignada','Recurso','Estado'].forEach(label=>{{const th=document.createElement('th');th.textContent=label;headRow.appendChild(th);}});
 head.appendChild(headRow);table.appendChild(head);
 const body=document.createElement('tbody');
 planItems.forEach(item=>{{
  const row=document.createElement('tr');
  [item.reference,item.telemarketer,item.date,item.resource,item.status].forEach(value=>{{const cell=document.createElement('td');cell.textContent=value;row.appendChild(cell);}});
  body.appendChild(row);
 }});
 table.appendChild(body);target.appendChild(table);
}}
document.getElementById('schedule-contact').addEventListener('click',()=>{{
 const status=document.getElementById('planner-status');
 const reference=document.getElementById('beneficiary-ref').value.trim();
 const token=document.getElementById('phone-group').value.trim();
 const requestedDate=dateInput.value;
 let telemarketer=telemarketerSelect.value;
 if(telemarketer==='other')telemarketer=otherTelemarketer.value.trim();
 if(document.getElementById('do-not-contact').checked){{status.textContent='Gestión bloqueada: la persona indicó no contactar.';return;}}
 if(!reference||!requestedDate||!telemarketer){{status.textContent='Complete la referencia individual, responsable y fecha.';return;}}
 if(requestedDate<todayLocal){{status.textContent='Seleccione una fecha igual o posterior a hoy.';return;}}
 let assignedDate=requestedDate;
 const occupied=date=>planItems.some(item=>item.date===date&&(item.reference===reference||(token&&item.phoneGroup===token)));
 while(occupied(assignedDate)){{
  const [year,month,day]=assignedDate.split('-').map(Number);
  const next=new Date(year,month-1,day+1);
  assignedDate=[next.getFullYear(),String(next.getMonth()+1).padStart(2,'0'),String(next.getDate()).padStart(2,'0')].join('-');
 }}
 planItems.push({{reference,phoneGroup:token,telemarketer,date:assignedDate,resource:resourceSelect.value,status:'Programada'}});
 status.textContent=assignedDate===requestedDate?'Gestión agregada.':'Conflicto de persona o teléfono compartido; se asignó '+assignedDate+'.';
 document.getElementById('do-not-contact').checked=false;
 renderPlan();
}});
</script>"""
    return _html_page("Tablero — Fundación 1380", body)


def render_report(summary: dict[str, Any]) -> str:
    years = summary["years"]
    segments = summary["segments"]
    resources = summary["resources"]
    model = summary["model"]
    quality = summary["quality"]
    annual_rows = "".join(
        f"<tr><td>{item['year']}</td><td>{item['contributors']:,}</td>"
        f"<td>{item['records_with_value']:,}</td><td>{item['total_amount']:,.0f}</td></tr>"
        for item in years
    )
    segment_rows = "".join(
        f"<tr><td>{html.escape(item['segment'])}</td><td>{item['beneficiaries']:,}</td>"
        f"<td>{item['share']:.1%}</td></tr>"
        for item in segments
    )
    resource_rows = "".join(
        f"<tr><td>{html.escape(item['resource'])}</td><td>{item['contributors']:,}</td>"
        f"<td>{item['total_amount']:,.0f}</td></tr>"
        for item in resources
    )
    if model["status"] == "evaluado":
        metrics = model["metrics"]
        model_html = f"""
<p>Se ajustó una regresión logística L2 para estimar la etiqueta «aporte positivo en TOTAL 2026», utilizando únicamente aportes hasta 2025. Datos etiquetados: {metrics['holdout_records']:,} en el holdout y {model['train_records']:,} en entrenamiento; partición estratificada aleatoria 80/20.</p>
<table><thead><tr><th>Métrica</th><th>Resultado</th></tr></thead><tbody>
<tr><td>Exactitud</td><td>{metrics['accuracy']:.3f}</td></tr>
<tr><td>Precisión</td><td>{metrics['precision']:.3f}</td></tr>
<tr><td>Recall</td><td>{metrics['recall']:.3f}</td></tr>
<tr><td>Especificidad</td><td>{metrics['specificity']:.3f}</td></tr>
<tr><td>F1</td><td>{metrics['f1']:.3f}</td></tr>
<tr><td>ROC-AUC</td><td>{metrics['roc_auc']:.3f}</td></tr>
<tr><td>Brier</td><td>{metrics['brier_score']:.3f}</td></tr>
</tbody></table>
<p>Matriz de confusión a umbral 0,5: VP={metrics['confusion_matrix']['true_positive']}, VN={metrics['confusion_matrix']['true_negative']}, FP={metrics['confusion_matrix']['false_positive']}, FN={metrics['confusion_matrix']['false_negative']}.</p>"""
    else:
        model_html = f"<p>El modelo no pudo evaluarse: {html.escape(model['reason'])}</p>"

    body = f"""
<header><h1>Trabajo final integrador · Big Data</h1>
<p>Proyecto de analítica de benefactores y aportes · Fundación 1380</p></header>
<main>
<p><strong>Entregable técnico y analítico</strong> generado a partir de la hoja Excel suministrada. El archivo fuente no se modifica.</p>
<h2>1. Resumen ejecutivo</h2>
<p>Se preparó un prototipo local de ETL, almacenamiento analítico, clasificación histórica, modelo exploratorio, tablero y plantillas operativas. Se procesaron <strong>{summary['source_rows']:,} registros</strong> y {summary['source_columns']} columnas. No se exportan datos personales ni filas individuales.</p>
<div class="good">La base es una tabla de benefactores con aportes agregados por año/mes. No contiene un registro transaccional completo ni un historial estructurado de contactos; los resultados se limitan a lo observable.</div>
<h2>2. Objetivo y alcance</h2>
<p>Integrar y resumir el historial disponible para orientar la captación y las acciones de contacto, conservando el Excel original y aplicando minimización de datos.</p>
<ul><li>ETL de lectura y normalización de encabezados; montos convertidos a formato numérico cuando es posible.</li>
<li>Clasificación en recurrente, esporádico, aporte único registrado, sin aportes recientes y sin aportes registrados.</li>
<li>Estimación exploratoria de aporte positivo en 2026 con variables históricas hasta 2025.</li>
<li>Agregados por periodo y por recursos que sí tienen una columna identificable.</li>
<li>Plantillas separadas para gestiones de contacto y transacciones del batch diario.</li></ul>
<h2>3. Arquitectura y gobierno</h2>
<div class="panel"><pre>Excel fuente (solo lectura)
       │
       ▼
Extracción XLSX → validaciones → normalización en memoria
       │
       ├──► clasificación y modelo exploratorio
       ├──► agregados CSV / JSON
       ├──► Data Warehouse SQLite (tablas agregadas, sin PII)
       └──► tablero HTML local y reporte técnico

Transacciones operativas autorizadas (plantilla separada)
       └──► batch diario por fecha de corte → reporte logístico agregado</pre></div>
<p>El Data Lake corresponde al Excel original custodiado por la Fundación, en modo de solo lectura y con permisos restringidos; no se duplica en esta entrega. El Warehouse incluido contiene solo datos agregados. Deben definirse responsables, retención, respaldos cifrados, registro de ejecuciones y control de acceso antes de producción.</p>
<h2>4. Diagnóstico de calidad</h2>
<table><tbody>
<tr><th>Registros y columnas</th><td>{quality['source_rows']:,} · {quality['source_columns']}</td></tr>
<tr><th>Código fuente faltante</th><td>{quality['missing_source_code']:,}</td></tr>
<tr><th>Códigos no vacíos duplicados</th><td>{quality['duplicate_nonempty_source_codes']:,}</td></tr>
<tr><th>Montos anuales negativos</th><td>{quality['negative_annual_amounts']:,}</td></tr>
<tr><th>Fecha fuente faltante</th><td>{quality['missing_values']['FECHA (DD-MM-AAA)']:,}</td></tr>
<tr><th>Último pago faltante</th><td>{quality['missing_values']['ULT PAGO']:,}</td></tr>
<tr><th>Total 2025 faltante</th><td>{quality['missing_values']['TOTAL 2025']:,}</td></tr>
<tr><th>Total 2026 faltante</th><td>{quality['missing_values']['TOTAL 2026']:,}</td></tr>
</tbody></table>
<p>Una celda vacía se interpreta únicamente como «sin aporte registrado». No se corrigen ni completan registros automáticamente. La fecha de corte no está declarada en el libro.</p>
<h2>5. Clasificación histórica</h2>
<p>Reglas aplicadas al historial anual con monto positivo: «recurrente» = aporte positivo en al menos 3 de los años 2023–2026; «aporte único registrado» = un solo año positivo en todo el historial; «sin aportes recientes» = historial positivo sin registro positivo entre 2024–2026; «esporádico» = demás historiales positivos; «sin aportes registrados» = ningún año positivo.</p>
<table><thead><tr><th>Segmento</th><th>Benefactores</th><th>Participación</th></tr></thead><tbody>{segment_rows}</tbody></table>
<h2>6. Tendencia anual registrada</h2>
<table><thead><tr><th>Año</th><th>Registros con monto &gt; 0</th><th>Registros con valor informado</th><th>Monto reportado</th></tr></thead><tbody>{annual_rows}</tbody></table>
<p>Los montos se presentan en las unidades de la fuente; moneda y reglas contables deben confirmarse con la Fundación. Los totales de columnas anual, ACUMULADO y recursos no se suman entre sí porque podrían solaparse. 2026 se considera incompleto hasta que el dueño de datos confirme el corte.</p>
<h2>7. Modelo de afinidad y evaluación</h2>
{model_html}
<p>Predictores: logaritmo del monto acumulado 2008–2025, número de años activos, aportes 2023–2025 y último año con aporte hasta 2025. Se excluyeron identificadores, contacto, edad, ubicación, salud y comentarios. La clasificación es exploratoria: el objetivo refleja lo registrado en 2026 y puede estar censurado por un corte parcial; el holdout aleatorio no sustituye validación temporal, calibración ni monitoreo. No automatizar solicitudes a beneficiarios con esta puntuación.</p>
<h2>8. Recursos capturados explícitamente</h2>
<table><thead><tr><th>Columna disponible</th><th>Registros &gt; 0</th><th>Monto reportado</th></tr></thead><tbody>{resource_rows}</tbody></table>
<p>La base no registra de manera completa los intereses o conversiones de donación directa, bingo, eventos y visitas. La app muestra únicamente las columnas con evidencia y marca los demás recursos como brecha de datos, no como afinidad inferida.</p>
<h2>9. Gestión de contacto y caso de teléfonos compartidos</h2>
<p>No se crean campañas ni se envían mensajes. La plantilla operativa requiere autorización, canal y franja horaria, resultado, próxima acción y responsable. Cada persona conserva su propio identificador de beneficiario; un token local de grupo telefónico sirve solo para coordinar el calendario y nunca para fusionar personas. Antes de programar, el módulo comprueba restricciones de no contacto y gestiones pendientes; limita a una gestión por grupo telefónico y día y desplaza las demás a días posteriores.</p>
<p>La fuente no contiene preferencias y restricciones estructuradas suficientes. Deben confirmarse con la persona antes de usarlas. No se publica ni se exporta ningún teléfono.</p>
<h2>10. Batch, uso y limitaciones</h2>
<p>El batch opera sobre la plantilla transaccional futura porque las columnas actuales son agregados y no identifican operaciones del día anterior. Al recibir un CSV autorizado con fecha, recurso, monto y alias operativo, el comando filtra el día anterior a la fecha de corte y produce un reporte de logística agregado, sin teléfono ni cédula.</p>
<ol><li>Instalar Python 3.10+ (sin librerías externas).</li><li>Ejecutar <code>python pipeline.py --input "ruta\\BD_F1380.xlsx"</code>.</li><li>Abrir <code>resultados\\dashboard.html</code> y <code>resultados\\informe_tecnico.html</code>.</li><li>Para el batch: <code>python pipeline.py --batch "resultados\\transacciones_template.csv" --cutoff YYYY-MM-DD</code>.</li></ol>
<p>Limitaciones: no hay transacciones de detalle, corte verificable, consentimiento, resultado de llamadas, catálogo completo de recursos, moneda confirmada ni datos suficientes para probar coordinación contra llamadas históricas. El prototipo no sustituye el sistema productivo ni la revisión jurídica y de seguridad.</p>
<h2>11. Recomendaciones</h2>
<ol><li>Definir un identificador de persona aleatorio y persistente separado del teléfono; conservar una relación identificadora solo en el sistema protegido.</li><li>Capturar transacciones normalizadas (fecha, beneficiario, recurso, monto, estado, fuente) y mantener moneda y fecha de corte explícitas.</li><li>Levantar consentimiento, restricciones, preferencias, canal y contacto pendiente con control de acceso.</li><li>Validar montos, duplicados y códigos faltantes con el dueño de datos antes de corregir.</li><li>Evaluar el modelo en periodos posteriores y por subgrupos antes de usarlo para priorización.</li><li>Configurar respaldo cifrado, bitácora de ETL y retención; limitar accesos al Excel de origen.</li></ol>
<footer>Documento generado automáticamente por el proyecto local Fundación 1380. No contiene registros individuales.</footer>
</main>"""
    return _html_page("Informe técnico — Fundación 1380", body)


def build(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    headers, records = read_xlsx(input_path)
    summary, _ = _summarize(headers, records)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with (destination / "aggregate_summary.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
    _write_csv(
        destination / "segment_summary.csv",
        summary["segments"],
        ["segment", "beneficiaries", "share"],
    )
    annual_rows = []
    for period in summary["years"]:
        for segment in summary["segments"]:
            values = period["by_segment"].get(segment["segment"], {})
            annual_rows.append(
                {
                    "year": period["year"],
                    "segment": segment["segment"],
                    "contributors": values.get("contributors", 0),
                    "reported_amount": values.get("total_amount", 0.0),
                }
            )
    _write_csv(
        destination / "annual_by_segment.csv",
        annual_rows,
        ["year", "segment", "contributors", "reported_amount"],
    )
    _write_csv(
        destination / "resource_summary.csv",
        summary["resources"],
        [
            "rank",
            "resource",
            "contributors",
            "share_of_resource_records",
            "total_amount",
            "records_with_value",
        ],
    )
    _write_csv(
        destination / "frequency_summary.csv",
        summary["activity"]["frequency_distribution"],
        ["category", "beneficiaries"],
    )
    _write_csv(
        destination / "payment_recency_summary.csv",
        summary["activity"]["last_payment_date"]["recency_distribution"],
        ["category", "beneficiaries"],
    )
    _write_csv(
        destination / "contact_management_template.csv",
        [],
        [
            "management_id",
            "beneficiary_ref",
            "assigned_telemarketer",
            "scheduled_date",
            "resource",
            "last_contact_date",
            "last_result",
            "next_action",
            "authorized_channel",
            "authorized_time_window",
            "do_not_contact",
            "shared_phone_group_token",
        ],
    )
    _write_csv(
        destination / "transactions_template.csv",
        [],
        [
            "transaction_date",
            "beneficiary_ref",
            "resource",
            "amount",
            "telemarketer_alias",
            "shared_phone_group_token",
            "authorized_channel",
            "preferred_time_window",
            "do_not_contact",
        ],
    )
    with (destination / "dashboard.html").open("w", encoding="utf-8") as file:
        file.write(render_dashboard(summary))
    report_path = destination / "informe_tecnico.html"
    with report_path.open("w", encoding="utf-8") as file:
        file.write(render_report(summary))
    database_path = _write_warehouse(destination, summary)
    return {
        "summary": summary,
        "output_dir": str(destination.resolve()),
        "dashboard": str((destination / "dashboard.html").resolve()),
        "report": str(report_path.resolve()),
        "warehouse": str(database_path.resolve()),
    }


def _batch(input_csv: str | Path, output_html: str | Path, cutoff: str) -> dict[str, Any]:
    cutoff_date = dt.date.fromisoformat(cutoff)
    target_date = cutoff_date - dt.timedelta(days=1)
    source = Path(input_csv)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo transaccional: {source}")
    required = {
        "transaction_date",
        "beneficiary_ref",
        "resource",
        "amount",
        "telemarketer_alias",
        "do_not_contact",
    }
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"records": 0, "amount": 0.0, "excluded_no_contact": 0}
    )
    encountered = 0
    with source.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Faltan columnas requeridas en el CSV: " + ", ".join(sorted(missing)))
        for row in reader:
            encountered += 1
            try:
                transaction_date = dt.date.fromisoformat(row["transaction_date"].strip())
            except ValueError as error:
                raise ValueError(
                    f"Fecha transaccional inválida en el registro {encountered}."
                ) from error
            if transaction_date != target_date:
                continue
            if row["do_not_contact"].strip().lower() in {"1", "true", "sí", "si", "yes"}:
                continue
            resource = row["resource"].strip() or "Sin recurso informado"
            assignee = row["telemarketer_alias"].strip() or "Sin asignar"
            amount = number(row["amount"])
            if amount is None:
                raise ValueError(f"Monto inválido en el registro {encountered}.")
            grouped[(assignee, resource)]["records"] += 1
            grouped[(assignee, resource)]["amount"] += amount

    result_rows = [
        {
            "responsable": assignee,
            "recurso": resource,
            "registros": values["records"],
            "monto": round(values["amount"], 2),
        }
        for (assignee, resource), values in sorted(grouped.items())
    ]
    row_html = "".join(
        f"<tr><td>{html.escape(row['responsable'])}</td><td>{html.escape(row['recurso'])}</td>"
        f"<td>{row['registros']}</td><td>{row['monto']:,.0f}</td></tr>"
        for row in result_rows
    ) or '<tr><td colspan="4">No hay gestiones elegibles para la fecha solicitada.</td></tr>'
    body = f"""<header><h1>Reporte logístico diario</h1><p>Fecha de corte: {cutoff_date.isoformat()} · Periodo: {target_date.isoformat()}</p></header>
<main><div class="notice">Reporte agregado. No se muestran beneficiarios, teléfonos ni identificadores personales. Confirme consentimiento y restricciones antes del contacto.</div>
<p>Filas examinadas: {encountered:,} · Grupos logísticos: {len(result_rows):,}</p>
<table><thead><tr><th>Responsable</th><th>Recurso</th><th>Registros</th><th>Monto</th></tr></thead><tbody>{row_html}</tbody></table></main>"""
    output = Path(output_html)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_html_page("Batch logístico diario", body), encoding="utf-8")
    return {
        "cutoff_date": cutoff_date.isoformat(),
        "target_date": target_date.isoformat(),
        "records_examined": encountered,
        "logistic_groups": len(result_rows),
        "report": str(output.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL y analítica local de la Fundación 1380.")
    parser.add_argument("--input", help="Ruta del Excel fuente .xlsx")
    parser.add_argument("--output", default="resultados", help="Directorio de salidas del ETL")
    parser.add_argument("--batch", help="CSV transaccional autorizado para el batch diario")
    parser.add_argument("--cutoff", help="Fecha de corte del batch, formato YYYY-MM-DD")
    args = parser.parse_args()

    if args.batch:
        if not args.cutoff:
            parser.error("--cutoff es obligatorio cuando se usa --batch.")
        result = _batch(args.batch, Path(args.output) / "batch_reporte.html", args.cutoff)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if not args.input:
        parser.error("--input es obligatorio para construir el proyecto.")
    result = build(args.input, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "summary"}, ensure_ascii=False, indent=2))
    print("Registros:", result["summary"]["source_rows"])
    print("Modelo:", result["summary"]["model"]["status"])
    if result["summary"]["model"]["status"] == "evaluado":
        metrics = result["summary"]["model"]["metrics"]
        print("ROC-AUC:", round(metrics["roc_auc"], 4))


if __name__ == "__main__":
    main()
