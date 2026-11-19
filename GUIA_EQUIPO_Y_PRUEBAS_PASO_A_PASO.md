# Guía Completa para el Equipo y Manual Paso a Paso de Pruebas (SIBDA-1380)

Esta guía está diseñada para que **todos los integrantes del equipo** comprendan al 100 % cómo funciona la solución de la **Fundación 1380**, cómo probar cada módulo en **Google Colab** sin errores y cómo responder cualquier pregunta del profesor durante las sustentaciones del **Avance 1** y del **Avance 2**.

---

## Parte 1. Resumen Ejecutivo para que Todo el Equipo Entienda el Proyecto

### 1.1 ¿Cuál es el problema real de la Fundación 1380?
La Fundación lleva 19 años (2008–2026) registrando a sus **2.744 benefactores** en una sola hoja de Excel (`Hoja1`) con **130 columnas**:
- **Problema 1 (Estructura):** En vez de agregar filas por cada aporte nuevo, agregaban **columnas hacia la derecha** (`2008`..`2023`, luego todos los meses de `2024`, luego todos los meses de `2025`, luego todos los meses de `2026`).
- **Problema 2 (Calidad):** En una misma columna mezclaron números con notas de texto (p. ej., en `FECHA` escribieron `RETIRAR` o `27/'8/2020`; en `BONO 2026` mezclaron pesos con números de boletas `549-804` y frases como `08/09/26 le hablo del bono`; en `SOCIO` escribieron **97 variantes** distintas).
- **Problema 3 (Teléfonos compartidos):** Hay **156 números de teléfono** compartidos por varias personas de una misma familia (hasta 7 personas con el mismo número). Como distintas telemercaderistas (Sandra, Viviana, Hna Lina, Jorge) llaman por separado, pueden saturar a la misma casa el mismo día.
- **Problema 4 (Decisiones a ciegas):** No existía un modelo que recomendara a qué benefactor llamar según el recurso (Bono, Donación directa, Banquete, Rifa cantarrilla, Bingo, Eventos, etc.).

### 1.2 ¿Cómo lo resuelve nuestra arquitectura Big Data (SIBDA-1380)?
1. **Inmutabilidad (Regla de Oro):** Nunca tocamos el Excel original. Calculamos su firma digital **SHA-256**, sacamos una copia en `datalake/raw/` y trabajamos sobre la copia.
2. **ETL en Python (Pandas + OpenPyXL + Regex):**
   - Limpia las 130 columnas y les pone nombres únicos.
   - Usa expresiones regulares (**Regex / NLP**) para leer los comentarios y detectar automáticamente:
     - Quién aporta con **familiares o amigos** (**530 benefactores**).
     - Quién pidió **no ser contactado** o falleció (**45 benefactores**).
     - Quién usa **WhatsApp** (**245 benefactores**).
     - Quién tiene notas sensibles de salud (`ENFERMO` / `CALAMIDAD`) para proteger su privacidad.
   - Convierte la tabla ancha de 130 columnas en una tabla vertical normalizada (*unpivot / melt*) con **20.804 transacciones reales** que suman **COP \$3.020.016.428**.
3. **Data Lake (Parquet) + Data Warehouse (DuckDB):**
   - **Data Lake:** Guarda archivos `.parquet` en capas `bronze/` (crudo), `silver/` (limpio) y `gold/` (analítico).
   - **Data Warehouse:** Carga un modelo en estrella dentro de **DuckDB** (`fundacion_1380_dw.duckdb`) con 7 tablas (`dim_benefactor`, `dim_telemercaderista`, `dim_recurso`, `dim_tiempo`, `fact_aportes`, `fact_agenda_contactos`, `audit_log_etl`) para hacer consultas SQL en milisegundos.
4. **Clasificación Analítica (Módulo 3):**
   - Clasifica a los **2.744 benefactores** con reglas matemáticas claras (sin inventar excusas personales):
     - **Permanente o recurrente:** **940** (34,26 %) → $\ge 4$ aportes totales y $\ge 2$ en 2024–2026.
     - **Sin aportes recientes que requieren revisión:** **678** (24,71 %) → $0$ aportes en 2024–2026.
     - **Con un único aporte registrado:** **601** (21,90 %) → $1$ solo aporte histórico y reciente.
     - **Esporádico:** **525** (19,13 %) → $2$ o $3$ aportes (o $\ge 4$ históricos con solo $1$ reciente).
5. **Inteligencia Artificial (Módulo 4):**
   - Entrena un modelo supervisado **`RandomForestClassifier`** (y lo compara contra `LogisticRegression`) en `scikit-learn` con validación cruzada de 5 pliegues (`5-Fold CV`) y conjunto de prueba (`20 %`) para predecir la probabilidad de afinidad en los recursos con suficientes etiquetas históricas (**Donación directa, Bono, Rifa cantarrilla, Evento, Banquete navideño**).
   - Para los recursos con pocas etiquetas explícitas (**Bingo [34], Visita a parroquias [50], Día de madres y padres [48], Otro [57]**), utiliza un **motor híbrido (Scoring RFM + Similitud NLP)**, explicando la diferencia entre un modelo predictivo supervisado y una segmentación por reglas.
6. **Control de Telemercaderistas y Teléfonos Compartidos (Módulo 5):**
   - Mantiene a cada persona como un registro individual (**no los fusiona**), pero antes de agendar una llamada revisa si ese número telefónico ya tiene una llamada programada ese día. Si ya está ocupado (como en el caso obligatorio de los 4 hermanos **Juan, Felipe, Jesús y Daniel**), bloquea el choque y reprograma automáticamente para otro día.

---

## Parte 2. Paso a Paso para Probar TODO en Google Colab

### 2.1 Cómo abrir y ejecutar cualquiera de los 2 Notebooks (con 1 Clic desde GitHub)
Ahora que el repositorio está publicado en GitHub, puedes abrir cualquiera de los cuadernos directamente en Google Colab con **un solo clic** (sin necesidad de descargar el `.ipynb`):
- **Abrir Avance 1 en Google Colab:** [https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_1/Avance_1_Fundacion_1380_Colab.ipynb)
- **Abrir Avance 2 en Google Colab:** [https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb](https://colab.research.google.com/github/Camilo-fonseca237/Trabajo_Final_Bigtdata/blob/main/Entregable_2/Avance_2_Fundacion_1380_Colab.ipynb)

*(Opcionalmente, también puedes entrar a [https://colab.research.google.com/](https://colab.research.google.com/) → **Archivo → Subir cuaderno** y seleccionar el `.ipynb` desde tu computador).*
4. En el menú superior de Colab, haz clic en **Entorno de ejecución → Ejecutar todas** (*Runtime → Run all*).
5. En la **Celda 2 (Carga del Excel)** aparecerá un botón **"Elegir archivos"** (*Choose Files*):
   - Selecciona el archivo [Recursos/BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx](file:///c:/Users/JuanCamiloFonsecaMej/Documents/Trabajo%20final%20Big%20data/Recursos/BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx) de tu computador.
   - *(Tip opcional para no subirlo cada vez)*: Si subes el Excel a tu Google Drive en la carpeta `Mi unidad/Fundacion1380/BD_F1380_SeudonimizadaAnonimizadaencriptada.xlsx` y montas Drive en Colab, el notebook lo detecta automáticamente sin pedirte subirlo.

---

### 2.2 Qué debes verificar en cada celda del Notebook de Avance 2 (Lista de Chequeo de Pruebas)

| Celda / Sección en Colab | Qué hace | Qué resultado debes ver en pantalla |
| :--- | :--- | :--- |
| **Sección 1 (Instalación)** | Instala `duckdb`, `openpyxl`, `pyarrow`, `scikit-learn`, `plotly`. | Mensaje: `Librerías cargadas correctamente`. |
| **Sección 2.1 (Ingesta Inmutable)** | Calcula `SHA-256` del Excel y crea copia en `sibda_1380/datalake/raw/`. | `Dimensiones: 2744 filas x 130 columnas` y `SHA-256 Original: 38ce3c1b1ffad55af2afbc646d762c0bb9958dff46470cedcbc57cf43ef90e8a`. |
| **Sección 2.2 (ETL Mejorado)** | Limpia las 130 columnas, aplica Regex familiar/restricciones y hace *unpivot* 2008–2026. | `20,804` transacciones confirmadas, `COP $3,020,016,428`, `530` con vínculo familiar, `45` con restricción, `156` grupos de teléfonos compartidos. |
| **Sección 3.1 (Clasificación Módulo 3)** | Clasifica los 2.744 benefactores en las 4 categorías y calcula intervalos/montos. | Tabla con: `Permanente o recurrente = 940`, `Sin aportes recientes = 678`, `Con un único aporte = 601`, `Esporádico = 525`. |
| **Sección 3.2 (Ficha Individual)** | Ejecuta `consultar_ficha_benefactor(3)` y muestra ejemplos familiares. | Ficha completa con los 8 atributos obligatorios del benefactor `COD=3` y tabla de 8 benefactores que aportan con familiares. |
| **Sección 4.1 y 4.2 (Modelo IA Módulo 4)** | Entrena `RandomForestClassifier` y `LogisticRegression` con `5-Fold CV` y `Test 20%`. | Tabla comparativa con `Accuracy`, `Precision`, `Recall`, `F1_Score`, `ROC_AUC_Test` y `ROC_AUC_5Fold_CV` para los recursos principales. |
| **Sección 4.3 (Gráficos Evaluación IA)** | Grafica evaluación del modelo. | 3 gráficos: **Matriz de Confusión**, **Curvas ROC** de los 5 modelos supervisados y **Top 10 Variables Más Importantes**. |
| **Sección 4.4 (Recomendador IA)** | Ejecuta `recomendar_benefactores(...)` por telemercaderista, fecha y recurso. | Tablas con el Top de benefactores recomendados para `Sandra` (`b. Bono`) y `Viviana` (`g. Banquete navideño`) con `% de afinidad`. |
| **Sección 5.1 y 5.2 (Telemercadeo y 4 Hermanos)** | Ejecuta `GestorContactosTelemercadeo` con **Juan, Felipe, Jesús y Daniel**. | Tabla 1: Los 4 hermanos registrados como 4 personas separadas. Tabla 2: Juan queda `PROGRAMADO` el `2026-11-23` y Felipe, Jesús y Daniel quedan `REPROGRAMADOS ANTI-SATURACIÓN` (`2026-11-25`, `2026-11-27`, `2026-11-30`). |
| **Sección 6 (Data Lake y DuckDB)** | Guarda Parquet (`bronze`, `silver`, `gold`) y crea 7 tablas en DuckDB. | Lista de 7 tablas en DuckDB: `dim_benefactor`, `dim_telemercaderista`, `dim_recurso`, `dim_tiempo`, `fact_aportes`, `fact_agenda_contactos`, `audit_log_etl`. |
| **Sección 7.1 y 7.2 (Tablero KPIs Módulo 6)** | Calcula los 11 KPIs y dibuja el tablero de control. | Tabla resumen con los 11 KPIs + Panel con **6 gráficos analíticos**. |
| **Sección 8 (Gobierno y Seguridad Módulo 8)** | Calcula `IGCD`, prueba roles `RBAC`, crea backup de DuckDB y verifica `SHA-256` final. | Vista restringida para `MENSAJERO`, auditoría `PER_/ID_/TEL_: APROBADA`, ruta del backup `.duckdb` y confirmación `SHA-256 inicial == SHA-256 final`. |

---

### 2.3 Pruebas Interactivas en Vivo (Para que Practiquen antes de la Sustentación)

Durante la sustentación, el profesor suele pedir: *"Muéstreme otro benefactor"*, *"Cambie de telemercaderista o de recurso"*, o *"Qué pasa si programo otra llamada al mismo teléfono"*. Puedes crear una celda nueva al final de Colab y pegar cualquiera de estas pruebas:

#### Prueba A: Consultar la ficha completa de cualquier otro benefactor
```python
# Puedes cambiar el número por cualquier COD entre 1 y 2744 (ej. 1, 15, 120, 552)
consultar_ficha_benefactor(15)
```

#### Prueba B: Cambiar de Telemercaderista, Fecha y Recurso en el Recomendador de IA
```python
# Prueba con "Hna Lina", "Viviana", "Sandra", "Jorge" o "TODOS"
# Y con cualquiera de los 9 recursos:
#   "a. Donación directa", "b. Bono", "c. Rifa cantarrilla", "d. Evento",
#   "e. Bingo", "f. Visita a parroquias", "g. Banquete navideño",
#   "h. Día de madres y padres", "i. Otro recurso configurable"
display(
    recomendar_benefactores(
        telemercaderista="Hna Lina",
        fecha_gestion="2026-11-28",
        recurso_captacion="c. Rifa cantarrilla",
        top_n=10,
    )
)
```

#### Prueba C: Intentar que otra telemercaderista llame a Juan o a Felipe el mismo día (sin reprogramación automática)
```python
# Si ponemos auto_reprogramar_si_colision=False, verás el estado BLOQUEADO_SATURACION_FAMILIAR
resultado_choque = gestor.programar_contacto(
    id_benefactor=9002,  # Felipe (Hermano 2)
    responsable="Sandra",
    fecha_programada="2026-11-23",  # Mismo día que Juan (Hermano 1)
    recurso_gestionar="a. Donación directa",
    auto_reprogramar_si_colision=False,
)
pd.DataFrame([resultado_choque])
```

#### Prueba D: Probar el Control de Acceso por Rol (RBAC - Módulo 8)
```python
# Comparar lo que ve una TELEMERCADERISTA vs lo que ve el MENSAJERO
print("Vista TELEMERCADERISTA (Viviana):")
display(
    consultar_vista_por_rol(
        "TELEMERCADERISTA", usuario_telemercaderista="Viviana", limite=5
    )
)

print("Vista MENSAJERO (solo datos logísticos de domicilio):")
display(consultar_vista_por_rol("MENSAJERO", limite=5))
```

#### Prueba E: Probar la Tokenización Criptográfica HMAC-SHA256 de Teléfonos en Google Colab
```python
# Demuestra que dos formatos distintos del mismo teléfono generan exactamente el mismo token sin revelar el número
print("Formato 1:", generar_token_hmac_telefono("+57 310-555-8899"))
print("Formato 2:", generar_token_hmac_telefono("573105558899"))
```

---

## Parte 3. Guion Rápido de Sustentación para el Equipo (Cómo Dividir la Exposición)

Si exponen entre varios integrantes (o individualmente en bloques), este orden cubre el 100 % de la rúbrica en 8–10 minutos:

1. **Integrante 1 – Problema, Arquitectura y Gobierno (2 min):**
   - Explica la problemática del Excel de 130 columnas, la arquitectura **Lakehouse (Parquet + DuckDB)** y muestra en la **Sección 2.1 y Sección 8** cómo el hash **SHA-256** garantiza que el Excel original jamás se modifica y cómo se protegen los datos sensibles (`ENFERMO` / `CALAMIDAD`) y roles (`RBAC`).
2. **Integrante 2 – ETL Mejorado y Almacenamiento (2 min):**
   - Muestra en la **Sección 2.2 y Sección 6** cómo se limpiaron las 97 variantes de `SOCIO`, las fechas mixtas, la extracción Regex de vínculos familiares (`530`) y restricciones (`45`), y cómo el *unpivot* generó las **20.804 transacciones** en DuckDB (`fact_aportes`).
3. **Integrante 3 – Clasificación de Benefactores e Inteligencia Artificial (3 min):**
   - Muestra en la **Sección 3** la tabla con las 4 categorías (`940` recurrentes, `678` sin aportes recientes, `601` único aporte, `525` esporádicos) y ejecuta `consultar_ficha_benefactor(3)`.
   - Muestra en la **Sección 4** por qué se usó `RandomForestClassifier` sin *data leakage*, enseña las curvas ROC / importancia de variables, explica la diferencia frente al motor híbrido para recursos con pocas etiquetas (`Bingo`, `Día de madres/padres`) y ejecuta en vivo `recomendar_benefactores(...)`.
4. **Integrante 4 – Control de Teléfonos Compartidos (4 Hermanos) y Tablero de KPIs (3 min):**
   - Muestra en la **Sección 5** el caso obligatorio de **Juan, Felipe, Jesús y Daniel**: demuestra que están registrados como **4 personas distintas** con el mismo teléfono y cómo el sistema evita que Viviana, Sandra, Lina y Jorge saturen a la familia el mismo día.
   - Cierra con la **Sección 7** mostrando los **11 KPIs** y los **6 gráficos** del tablero de control.

