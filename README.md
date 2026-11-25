# SIBDA-1380: Plataforma de Big Data, Analítica e IA – Fundación 1380

Proyecto Final Integrador de la asignatura **ET0155 – Fundamentos de Big Data** (Tecnología en Desarrollo de Software, Institución Universitaria Pascual Bravo).

Solución integral de **Big Data, Analítica de Datos e Inteligencia Artificial** diseñada para la **Fundación 1380**, que transforma su operación histórica almacenada en hojas de cálculo (2008–2026) en una arquitectura **Medallion Lakehouse** reproducible y re-ejecutable ante nuevas versiones del Excel en **Python / Google Colab**, **Apache Parquet** y **DuckDB**, incorporando clasificación analítica de benefactores, predicción de afinidad con `scikit-learn` libre de fuga de datos, coordinación anti-saturación de teléfonos compartidos para telemercaderistas, tablero ejecutivo de 11 KPIs, **proceso batch diario para el mensajero** y gobierno de datos.

---

## Abrir Directamente en Google Colab (1 Clic)

| Entregable | Enlace Directo a Google Colab | Documento Técnico |
| :--- | :--- | :--- |
| **Entregable 3 (Entrega Definitiva – Módulos 1 al 8)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_3/Entrega_Definitiva_Fundacion_1380_Colab.ipynb) | [Documento_Tecnico_Entrega_Definitiva.md](./Entregable_3/Documento_Tecnico_Entrega_Definitiva.md) |
| **Entregable 2 (Avance 2)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb) | [Avance_2_Analitica_IA_y_Gestion.md](./Entregable_2/Avance_2_Analitica_IA_y_Gestion.md) |
| **Entregable 1 (Avance 1)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb) | [Avance_1_Formulacion_y_Arquitectura.md](./Entregable_1/Avance_1_Formulacion_y_Arquitectura.md) |

---

## Estructura del Repositorio

| Carpeta / Archivo | Descripción |
| :--- | :--- |
| **[Entregable_3/Entrega_Definitiva_Fundacion_1380_Colab.ipynb](./Entregable_3/Entrega_Definitiva_Fundacion_1380_Colab.ipynb)** | **Notebook Google Colab Definitivo (Entregable 3):** Integra Módulos 1 al 8, ETL dinámico compatible con nuevas versiones del Excel (`2027+`), comparación de 4 modelos ML con IC 95 % Bootstrap, caso de los 4 hermanos, 11 KPIs, proceso batch del mensajero, gobierno RBAC y autoverificación. |
| **[Entregable_3/Documento_Tecnico_Entrega_Definitiva.md](./Entregable_3/Documento_Tecnico_Entrega_Definitiva.md)** | **Documento Técnico Maestro:** Arquitectura Medallion Lakehouse, diagramas Mermaid, metodología de los 8 módulos, evidencias verificadas, conclusiones y recomendaciones estratégicas para la Fundación 1380. |
| **[Entregable_3/batch_mensajero.py](./Entregable_3/batch_mensajero.py)** | **Script Batch del Mensajero (Módulo 7):** Extracción CLI/programática de transacciones del día anterior, filtrado logístico, consolidación de paradas físicas y generación de reporte imprimible HTML/CSV/TXT con minimización de datos personales. |
| **[Entregable_3/src/](./Entregable_3/src/)** | **Código Fuente Modular y Documentado:** Módulos Python organizados (`etl_lakehouse.py`, `analitica_e_ia.py`, `gestor_telemercadeo.py`, `gobierno_seguridad.py`). |
| **[Entregable_3/evidencias/](./Entregable_3/evidencias/)** | **Evidencias Ejecutables y Reportes:** Tablero interactivo autónomo (`Tablero_Ejecutivo_Fundacion_1380.html`) y planilla imprimible real del mensajero (`Reporte_Mensajero_Corte_20261016.html` + `.csv`). |
| **[Entregable_2/](./Entregable_2/)** | Entregables del Avance 2 (`Avance_2_Fundacion_1380_Colab.ipynb` y `Avance_2_Analitica_IA_y_Gestion.md`). |
| **[Entregable_1/](./Entregable_1/)** | Entregables del Avance 1 (`Avance_1_Fundacion_1380_Colab.ipynb` y `Avance_1_Formulacion_y_Arquitectura.md`). |
| **[Recursos/](./Recursos/)** | Enunciado oficial (`TRABAJO FINAL INTEGRADOR BIG DATA PROF.pdf`) y base de datos seudonimizada (`BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx`). |
| **[Contexto/](./Contexto/)** | Material teórico de referencia del curso ET0155. |
| **[requirements.txt](./requirements.txt)** | Especificación de dependencias de Python para ejecución local en entorno virtual (`.venv`). |

---

## Principales Resultados Verificados sobre la Base Real (2.744 Benefactores)

- **Volumen e Inmutabilidad (Módulos 1 y 2):** **2.744 benefactores** y **130 columnas** desnormalizadas sin tocar el Excel fuente (`SHA-256` verificado al inicio y al cierre) hacia **20.804 transacciones confirmadas (`monto > 0`)** por **COP \$3.020.016.428** almacenadas en **Parquet** y **DuckDB** (7 tablas en estrella), con soporte automático ante nuevas versiones del Excel.
- **Clasificación Analítica (Módulo 3):** `940` permanentes/recurrentes (34,26 %), `678` sin aportes recientes en revisión (24,71 %), `601` con único aporte (21,90 %), `525` esporádicos (19,13 %) y `530` con aportes familiares/amigos documentados (19,31 %).
- **Inteligencia Artificial sin Fuga de Datos (Módulo 4):** Comparación rigurosa de `DummyClassifier`, `LogisticRegression`, `GradientBoostingClassifier` y `RandomForestClassifier` (entrenado con variables históricas `<= 2024` prediciendo `2025–2026`, IC 95 % Bootstrap y *Slice Analysis*), más motor híbrido y registro dinámico de recursos configurables (`a`–`i`).
- **Control de Teléfonos Compartidos (Módulo 5):** Detección de **156 grupos de teléfonos compartidos** y validación del **caso obligatorio de los 4 hermanos (Juan, Felipe, Jesús y Daniel)**, evitando saturación familiar sin fusionar personas y bloqueando las **45 restricciones de no contacto**.
- **Proceso Batch del Mensajero (Módulo 7):** En el corte operativo real `2026-10-16` (día anterior `2026-10-15`), identifica **29 transacciones**, filtra **19 operaciones logísticas** y las optimiza en **18 paradas físicas** por **COP \$655.000** en planilla lista para imprimir sin datos personales innecesarios.
- **Gobierno y Seguridad (Módulo 8):** Índice de calidad `IGCD`, control de acceso por rol (`RBAC`), tokenización `HMAC-SHA256`, aislamiento de datos sensibles (`ENFERMO` / `CALAMIDAD`), copias de seguridad `.duckdb` y bitácora `audit_log_etl`.

---

## Ejecución Rápida

### Opción 1: Google Colab (Recomendada)
1. Haz clic en el botón **Open in Colab** de **Entregable 3 (Entrega Definitiva)** en la tabla superior.
2. En el menú superior selecciona **Entorno de ejecución → Ejecutar todas**.
3. Cuando la celda de ingesta lo solicite, sube `Recursos/BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx` (o monta Google Drive con el archivo en `Mi unidad/Fundacion1380/`).

### Opción 2: Ejecución del Script Batch del Mensajero por Consola (Entorno Virtual Local)
```bash
python -m venv .venv
# En Windows: .venv\Scripts\pip install -r requirements.txt
# En Linux/Mac: .venv/bin/pip install -r requirements.txt
python Entregable_3/batch_mensajero.py --fecha-corte 2026-10-16
```
