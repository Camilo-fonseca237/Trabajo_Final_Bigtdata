# Guion de Sustentación – Avance 2 (SIBDA-1380)

**Proyecto:** Plataforma Analítica e Inteligente de Benefactores y Captación de Recursos – **Fundación 1380**  
**Asignatura:** ET0155 – Fundamentos de Big Data | **Institución Universitaria Pascual Bravo**  
**Duración total estimada:** 8 a 10 minutos (2 minutos por bloque + demostración en Google Colab)  
**Notebook de respaldo en vivo:** [Avance_2_Fundacion_1380_Colab.ipynb](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb)

> **Nota de organización del equipo:**  
> Este guion está estructurado sobre los **4 bloques temáticos** del documento `GUION_AVANCE_2.odt` (**Persona 1, Persona 2, Persona 3 y Persona 4**).  
> - Si exponen **4 personas en total**, cada uno toma un bloque tal como está abajo.  
> - Si exponen **5 personas en total** (tú + 4 compañeros), dividan la **Persona 4** en dos intervenciones de 1,5 min: **Persona 4** presenta **Teléfonos Compartidos (Caso 4 Hermanos)** y **Persona 5** presenta **Tablero de KPIs + Gobierno y Seguridad de Datos**.

---

## Checklist Previo (2 minutos antes de empezar)
1. Tener abierta la presentación de diapositivas (`Presentacion_Avance_2_Fundacion_1380.pptx`).
2. Tener abierto en otra pestaña **Google Colab** con todas las celdas ya ejecutadas (`Entorno de ejecución → Ejecutar todas`), para no perder tiempo esperando instalaciones en vivo.
3. Tener claro qué celda muestra cada integrante durante su intervención.

---

## Bloque 1 – Persona 1: Introducción, ETL Mejorado y Almacenamiento (Data Lake + Data Warehouse)
* **Diapositivas asociadas:** Diapositiva 1 (Portada), Diapositiva 2 (Resumen de Avance 2), Diapositiva 3 (ETL Mejorado) y Diapositiva 4 (Data Lake + Data Warehouse).
* **Qué mostrar en Google Colab:** **Celdas `[4]`, `[5]` y `[18]`** (hash SHA-256, resumen de transacciones normalizadas y tablas en DuckDB).

### Guion oral:
> *"Buenos días/tardes profesor y compañeros. Para este segundo avance del proyecto de la **Fundación 1380**, nos enfocamos en convertir el diagnóstico del Avance 1 en una solución analítica e inteligente completamente funcional en **Google Colab**.*
>
> *En primer lugar, perfeccionamos nuestro proceso **ETL (Extracción, Transformación y Carga)** en Python. Trabajamos siempre sobre una copia de trabajo verificada con firma criptográfica **SHA-256**, garantizando al 100 % que el Excel original de **2.744 registros y 130 columnas** nunca se modifica.*
>
> *Al mejorar el ETL, desambiguamos los meses de 2024, 2025 y 2026, limpiamos las **97 variantes de texto** en la columna `SOCIO`, normalizamos fechas híbridas y aplicamos **expresiones regulares (Regex / NLP ligero)** sobre los comentarios libres para rescatar información clave que antes se perdía: detectamos **530 benefactores** que aportan en compañía de familiares o amigos, **45 casos** con restricción explícita de no contacto y **245** con canal WhatsApp.*
>
> *Finalmente, transformamos esa matriz ancha en **20.804 transacciones históricas confirmadas** entre 2008 y 2026, que suman **COP \$3.020 millones**. Persistimos la información en un **Data Lake** con capas `raw`, `bronze`, `silver` y `gold` en archivos **Parquet**, y cargamos un **Data Warehouse** en **DuckDB** con 7 tablas en esquema estrella (`dim_benefactor`, `dim_telemercaderista`, `dim_recurso`, `dim_tiempo`, `fact_aportes`, `fact_agenda_contactos` y `audit_log_etl`), lo que nos permite consultar toda la base con SQL en milisegundos. Le doy paso a mi compañero/a para explicar la clasificación."*

### Demostración rápida en Colab (15 seg):
- Mostrar la salida de la **Celda `[5]`** (las `20,804` transacciones y los `COP $3,020,016,428`) y la **Celda `[18]`** con la lista de las 7 tablas en DuckDB.

---

## Bloque 2 – Persona 2: Clasificación de Benefactores, Frecuencia y Comportamiento Histórico
* **Diapositivas asociadas:** Diapositiva 5 (Reglas y Segmentos de Clasificación) y Diapositiva 6 (Comportamiento Histórico, Frecuencia y Ficha Individual).
* **Qué mostrar en Google Colab:** **Celdas `[7]` y `[8]`** (tabla de clasificación, auditoría de `ULT PAGO` y ficha individual `consultar_ficha_benefactor(3)`).

### Guion oral:
> *"Gracias. Una vez tuvimos los datos limpios y modelados en nuestro Data Warehouse, desarrollamos el **Módulo 3: Clasificación y Comportamiento Histórico de los Benefactores**.*
>
> *Para cumplir con la regla de basarnos estrictamente en evidencia analítica sin inventar causas personales, implementamos reglas objetivas combinando la **frecuencia histórica total** y la **recencia en el período 2024–2026**, obteniendo 4 segmentos claros sobre los 2.744 benefactores:*
> - ***Permanentes o recurrentes:* 940 benefactores (34,26 %)**, quienes tienen 4 o más aportes históricos y al menos 2 aportes recientes entre 2024 y 2026. Son el núcleo que sostiene a la Fundación.
> - ***Sin aportes recientes que requieren revisión:* 678 benefactores (24,71 %)**, de los cuales 320 aportaron en años anteriores (2008–2023) y 358 no tienen montos positivos registrados en la matriz; aclarando metodológicamente que una celda vacía significa «sin aporte registrado», no prueba que nunca haya donado.
> - ***Con un único aporte registrado:* 601 benefactores (21,90 %)** en el período reciente.
> - ***Esporádicos:* 525 benefactores (19,13 %)** con participación intermitente.
>
> *Además, para cada benefactor el sistema calcula automáticamente sus **8 atributos clave**: fecha del último aporte —auditando `ULT PAGO` con **2.165 fechas válidas** al corte del 18 de noviembre de 2026—, número de aportes registrados, intervalo promedio en meses entre donaciones, valor acumulado, ticket promedio, recurso al que más contribuye, tendencia histórica y si aporta con familiares o amigos —donde detectamos **530 casos documentados** como `PERM-DONA CON SU ESPOSO` o `FLIA OCAMPO`—. Ahora los dejo con la parte de Inteligencia Artificial."*

### Demostración rápida en Colab (15 seg):
- Mostrar en la **Celda `[7]`** la tabla de las 4 categorías y los rangos de antigüedad de `ULT PAGO`, y en la **Celda `[8]`** la ficha individual generada por `consultar_ficha_benefactor(3)`.

---

## Bloque 3 – Persona 3: Recursos de Mayor Participación, Modelo de IA y Recomendación
* **Diapositivas asociadas:** Diapositiva 7 (Recursos de Captación `a`–`i`), Diapositiva 8 (Modelo de IA `RandomForestClassifier` y Evaluación) y Diapositiva 9 (Prototipo de Recomendación por Telemercaderista, Fecha y Recurso).
* **Qué mostrar en Google Colab:** **Celdas `[10]`, `[11]`, `[12]` y `[13]`** (catálogo de recursos, métricas de evaluación, curvas ROC/matriz de confusión y función `recomendar_benefactores`).

### Guion oral:
> *"Hola a todos. Continuando con el análisis, abordamos los **recursos de mayor participación** y el **Módulo 4 de Inteligencia Artificial**.*
>
> *Primero mapeamos los **9 recursos oficiales (`a` hasta `i`)** combinando columnas monetarias y evidencia en texto y boletas: los líderes son **Bono** (con **2.042 benefactores** y \$259,9 millones registrados en meses recientes) y **Donación directa** (**1.981 benefactores** y \$2.721 millones acumulados), seguidos por **Evento** (310), **Banquete navideño** (214 y \$38,3 millones) y **Rifa cantarrilla** (136).*
>
> *Para el modelo predictivo, cuidamos un principio clave exigido en el proyecto: **diferenciar un verdadero modelo supervisado de una segmentación basada en reglas** cuando faltan etiquetas confiables.*
> - *Para los 5 recursos con suficiente historial (Donación directa, Bono, Rifa cantarrilla, Evento y Banquete navideño), entrenamos un **`RandomForestClassifier`** (200 árboles con pesos balanceados) comparado frente a una **`LogisticRegression`** en `scikit-learn`. Para evitar fuga de datos (**data leakage**), en Donación directa y Bono entrenamos con variables históricas de **2008–2024** para predecir la participación efectiva en **2025–2026**.*
> - *Evaluamos con división estratificada **80 % entrenamiento / 20 % prueba** y validación cruzada **5-Fold**, midiendo **Accuracy, Precision, Recall, Especificidad, F1-Score, ROC-AUC y Brier Score**, graficando la matriz de confusión, las curvas ROC y la importancia de variables.*
> - *Para recursos con menos de 60 registros explícitos —como Bingo (34), Visita a parroquias (50) o Día de madres y padres (48)—, documentamos la limitación de etiquetas y aplicamos un **motor híbrido basado en reglas RFM y similitud de eventos**.*
>
> *Finalmente, integramos todo en el prototipo `recomendar_benefactores`, donde seleccionamos **telemercaderista, fecha de gestión y recurso (`a`–`i`)**, excluyendo automáticamente a quienes tienen restricción de no contacto y alertando si el teléfono es compartido."*

### Demostración rápida en Colab (20 seg):
- Mostrar en la **Celda `[11]`** la tabla de métricas, en la **Celda `[12]`** las curvas ROC + Matriz de confusión, y en la **Celda `[13]`** el ranking de recomendación para `Sandra` en `b. Bono` y `Viviana` en `g. Banquete navideño`.

---

## Bloque 4 – Persona 4: Control de Teléfonos Compartidos (4 Hermanos), KPIs y Gobierno de Datos
*(Nota: Si son 5 integrantes, Persona 4 expone hasta el caso de los 4 hermanos y Persona 5 toma desde Visualizaciones/KPIs y Gobierno de Datos).*

* **Diapositivas asociadas:** Diapositiva 10 (Control de Telemercadeo y Caso Obligatorio de los 4 Hermanos), Diapositiva 11 (Primeras Visualizaciones y los 11 KPIs) y Diapositiva 12 (Gobierno de Datos, Seguridad y Conclusiones).
* **Qué mostrar en Google Colab:** **Celdas `[16]`, `[20]`, `[21]` y `[23]`** (prueba de Juan, Felipe, Jesús y Daniel, tabla de los 11 KPIs, los 6 gráficos y auditoría RBAC/HMAC/SHA-256).

### Guion oral:
> *"Y para cerrar, resolvimos la parte operativa, visual y de gobierno de datos.*
>
> *Primero, en el **Módulo 5 (Gestión de Telemercaderistas)** detectamos en la base real **156 grupos de teléfonos compartidos**, donde hasta **7 personas** distintas tienen el mismo número. Para evitar saturar a una familia el mismo día sin fusionar a las personas, implementamos la clase `GestorContactosTelemercadeo`.*
>
> *Aquí en Colab probamos el **caso obligatorio de los 4 hermanos: Juan, Felipe, Jesús y Daniel**, quienes comparten el mismo teléfono pero tienen responsables distintos (**Viviana, Sandra, Hna Lina y Jorge**) e intereses diferentes (Bono, Donación directa, Banquete y Rifa). Al intentar llamarlos a todos el mismo día (`2026-11-23`), el sistema conserva a los 4 como personas separadas, aprueba el primer turno para Juan y **detecta automáticamente la colisión** para Felipe, Jesús y Daniel, reprogramándolos en fechas espaciadas (`2026-11-25`, `2026-11-27` y `2026-11-30`), además de bloquear cualquier intento sobre los 45 registros con restricción de no contacto.*
>
> *(Si hay Persona 5, inicia aquí) Segundo, construimos en el **Módulo 6** el tablero inicial con los **11 indicadores clave (KPIs)** y **6 gráficos analíticos**: distribución de segmentos, evolución del recaudo 2008–2026 (mostrando el pico de \$448,7 millones en 2025), participación por los 9 recursos, carga por telemercaderista, canales de pago y estacionalidad mensual.*
>
> *Por último, en el **Módulo 8 (Gobierno y Seguridad de Datos)** implementamos el Índice Global de Calidad (**IGCD**), control de acceso por rol (**RBAC**) —donde el mensajero solo ve datos logísticos de domicilio—, tokenización **HMAC-SHA256** de teléfonos, aislamiento de columnas sensibles (`ENFERMO` y `CALAMIDAD`), backup automático del Data Warehouse en DuckDB, bitácora de linaje (`audit_log_etl`), verificación final **SHA-256** del Excel original y nuestra suite de autoverificación en verde. ¡Muchas gracias, quedamos atentos a sus preguntas!"*

### Demostración rápida en Colab (20 seg):
- Mostrar la **Celda `[16]`** (las 4 filas de los hermanos sin fusionar + tabla de reprogramación anti-saturación), la **Celda `[21]`** (panel de 6 gráficos) y el final de la **Celda `[23]`** (`TODAS LAS ASERCIONES APROBADAS`).

---

## Banco de Respuestas Rápidas ante Preguntas del Profesor

| Pregunta probable del profesor | Quién responde | Respuesta concreta y técnica |
| :--- | :---: | :--- |
| **¿Cómo garantizan que el Excel original no se modificó?** | Persona 1 | Se calcula su hash **SHA-256** al inicio y al final (`assert HASH_INICIO == HASH_FINAL`), se copia a `datalake/raw/` y `openpyxl` lo abre en modo `read_only=True`. |
| **¿Qué diferencia hay entre Data Lake y Data Warehouse en su proyecto?** | Persona 1 | El **Data Lake** (Parquet en `raw/bronze/silver/gold`) guarda los datos históricos crudos e intermedios con *schema-on-read*; el **Data Warehouse** (**DuckDB**) usa *schema-on-write* en esquema estrella optimizado para SQL y KPIs. |
| **¿Cómo clasifican a un recurrente sin inventar causas personales?** | Persona 2 | Con reglas objetivas sobre `fact_aportes`: $\ge 4$ aportes totales y $\ge 2$ en 2024–2026. Si una celda está vacía se reporta como «sin aporte registrado», sin suponer motivos personales. |
| **¿Por qué usaron Random Forest y también reglas híbridas?** | Persona 3 | `RandomForestClassifier` captura relaciones no lineales RFM en recursos con cientos de etiquetas (validado con `5-Fold CV` y sin *data leakage* temporal 2008–2024 → 2025–2026). Para recursos con $<60$ casos (ej. Bingo=34), usamos reglas RFM+similitud porque un modelo supervisado puro tendría sobreajuste. |
| **¿Qué pasa si dos telemercaderistas llaman al mismo número el mismo día?** | Persona 4 | El sistema nunca fusiona a las personas (Juan, Felipe, Jesús y Daniel conservan sus IDs), pero consulta `agenda` por `telefono_token` + `fecha_programada`, bloquea la segunda llamada del día y reprograma con días de enfriamiento. |
| **¿Cómo protegen los datos de salud (`ENFERMO`/`CALAMIDAD`)?** | Persona 4 (o 5) | Se excluyen del modelo de IA comercial, se reemplazan en vistas operativas por una bandera pastoral discreta y se restringen mediante control de acceso por rol (`RBAC`). |
