# SIBDA-1380: Plataforma de Big Data, Analítica e IA – Fundación 1380

Proyecto Final Integrador de la asignatura **ET0155 – Fundamentos de Big Data** (Tecnología en Desarrollo de Software, Institución Universitaria Pascual Bravo).

Solución integral de **Big Data, Analítica de Datos e Inteligencia Artificial** diseñada para la **Fundación 1380**, que transforma su operación histórica almacenada en hojas de cálculo (2008–2026) en una arquitectura **Medallion Lakehouse** reproducible en **Python / Google Colab**, **Apache Parquet** y **DuckDB**, incorporando clasificación analítica de benefactores, predicción de afinidad con `scikit-learn`, coordinación anti-saturación de teléfonos compartidos para telemercaderistas, tablero de KPIs y gobierno de datos.

---

## Abrir Directamente en Google Colab (1 Clic)

| Entregable | Enlace Directo a Google Colab | Documento Técnico |
| :--- | :--- | :--- |
| **Entregable 1 (Avance 1)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb) | [Avance_1_Formulacion_y_Arquitectura.md](./Entregable_1/Avance_1_Formulacion_y_Arquitectura.md) |
| **Entregable 2 (Avance 2 Integrado)** | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb) | [Avance_2_Analitica_IA_y_Gestion.md](./Entregable_2/Avance_2_Analitica_IA_y_Gestion.md) |

---

## Estructura del Repositorio

| Carpeta / Archivo | Descripción |
| :--- | :--- |
| **[Entregable_1/Avance_1_Formulacion_y_Arquitectura.md](./Entregable_1/Avance_1_Formulacion_y_Arquitectura.md)** | **Documento Técnico Avance 1:** Formulación del proyecto, requerimientos funcionales, arquitectura Big Data, diagrama de flujo, inventario de 130 columnas y primer diagnóstico de calidad. |
| **[Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb](./Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb)** | **Notebook Google Colab Avance 1:** Ingesta inmutable con verificación SHA-256, inspección de hojas/columnas, diagnóstico automatizado de calidad, primer ETL y carga inicial en Parquet + DuckDB. |
| **[Entregable_2/Avance_2_Analitica_IA_y_Gestion.md](./Entregable_2/Avance_2_Analitica_IA_y_Gestion.md)** | **Documento Técnico Avance 2:** ETL mejorado con NLP/Regex, modelo dimensional en DuckDB, clasificación de benefactores, modelo de IA (`RandomForestClassifier` + motor híbrido), caso obligatorio de teléfonos compartidos (4 hermanos), 11 KPIs y gobierno de datos. |
| **[Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb](./Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb)** | **Notebook Google Colab Avance 2 (Integrado):** Pipeline completo ejecutable de principio a fin en Google Colab (Módulos 1, 2, 3, 4, 5, 6 y 8 + suite de autoverificación). |
| **[Recursos/](./Recursos/)** | Enunciado oficial del proyecto (`TRABAJO FINAL INTEGRADOR BIG DATA PROF.pdf`) y base de datos seudonimizada (`BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx`). |
| **[Contexto/](./Contexto/)** | Material teórico de referencia del curso ET0155 (Ciclo de vida del dato, ETL, Almacenamiento Data Lake/Warehouse, KPIs/CMI, Visualización, Preparación/Modelado, Data Storytelling y Gobierno de Datos). |

---

## Principales Resultados Verificados sobre la Base Real (2.744 Benefactores)

- **Volumen procesado:** **2.744 benefactores** y **130 columnas** desnormalizadas hacia **20.804 transacciones confirmadas (`monto > 0`)** entre 2008 y 2026 por un valor acumulado de **COP \$3.020.016.428**.
- **Clasificación Analítica (Módulo 3):**
  - **Permanentes o recurrentes:** `940` (34,26 %)
  - **Sin aportes recientes que requieren revisión:** `678` (24,71 %)
  - **Con un único aporte registrado:** `601` (21,90 %)
  - **Esporádicos:** `525` (19,13 %)
  - **Aportes documentados con familiares o amigos (Regex/NLP):** `530` benefactores (19,31 %).
- **Inteligencia Artificial (Módulo 4):** Clasificadores supervisados `RandomForestClassifier` comparados frente a `LogisticRegression` con validación cruzada estratificada (`5-Fold CV`) y conjunto de prueba (`20 %`) sin fuga de datos, complementados con scoring híbrido RFM+NLP para cubrir los **9 recursos de captación (`a`–`i`)**.
- **Gestión de Telemercaderistas y Teléfonos Compartidos (Módulo 5):** Detección de **156 grupos de teléfonos compartidos** (hasta 7 personas en un mismo número) y validación del **caso obligatorio de los 4 hermanos (Juan, Felipe, Jesús y Daniel)**, evitando la saturación familiar sin fusionar identidades y respetando las **45 restricciones de no contacto**.
- **Gobierno y Seguridad (Módulo 8):** Verificación criptográfica **SHA-256** de no modificación del archivo Excel fuente, control de acceso por roles (**RBAC**), aislamiento de datos sensibles de salud (`ENFERMO` / `CALAMIDAD`), copias de seguridad automatizadas y bitácora `audit_log_etl`.

---

## Ejecución Rápida en Google Colab

1. Abre [Google Colab](https://colab.research.google.com/) mediante los botones **Open in Colab** de la tabla superior (o sube `Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb` / `Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb`).
2. Selecciona **Entorno de ejecución → Ejecutar todas**.
3. Cuando la celda de ingesta lo solicite, selecciona el archivo `Recursos/BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx`.

