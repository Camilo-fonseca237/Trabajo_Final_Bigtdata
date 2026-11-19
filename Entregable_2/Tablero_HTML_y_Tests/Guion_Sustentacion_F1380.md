# Guion para sustentar el trabajo final

## Antes de exponer

1. Abra `resultados/dashboard.html` y deje preparada la pestaña.
2. Tenga listo el notebook `Trabajo_Final_F1380.ipynb` y ejecute las celdas en orden.
3. Use únicamente el ejemplo ficticio `DEMO-PERSONA` para mostrar teléfonos compartidos. No proyecte nombres, cédulas, teléfonos, direcciones ni comentarios reales.
4. Si va a ejecutar el notebook localmente, seleccione un kernel de Python que tenga `ipykernel`. El archivo de notebook compartido registró un error de entorno por falta de ese paquete y, como consecuencia, otro `NameError` en una celda posterior. Instálelo en el intérprete seleccionado si es necesario:

   ```powershell
   python -m pip install ipykernel
   ```

   Después, reinicie el kernel y ejecute todas las celdas desde el principio. En Colab, suba también `pipeline.py` y `contact_manager.py`.

## Presentación oral sugerida

> Buenas tardes. Presento el trabajo final de analítica de benefactores para la Fundación 1380. El objetivo es organizar el historial de aportes para consultar su comportamiento, presentar indicadores y apoyar la planificación de contactos.
>
> La fuente entregada es una hoja Excel con 2.744 registros y 130 columnas. La tratamos como solo lectura. El proceso ETL extrae la hoja, normaliza valores y fechas que se pueden interpretar, y genera salidas agregadas. No exportamos nombres, cédulas, teléfonos, direcciones ni comentarios.
>
> Para clasificar a los benefactores aplicamos reglas descriptivas sobre los aportes anuales. En este corte, el resultado fue: 707 recurrentes, 536 esporádicos, 958 con un único año de aporte registrado, 185 sin aportes recientes y 358 sin aportes registrados. “Sin aportes registrados” no significa que la persona nunca haya aportado; significa que no hay un monto positivo en las columnas históricas consideradas.
>
> Para describir el comportamiento calculamos los años con aportes positivos entre 2008 y 2025 y la antigüedad de la fecha disponible en “ULT PAGO”. Hay 2.165 fechas interpretables de 2.744 registros. En esta ejecución, 794 fechas válidas tienen más de un año de antigüedad. La fecha de corte es el 18 de noviembre de 2026; algunos valores vacíos, inválidos o posteriores a ese corte se excluyen.
>
> Como primera aproximación de inteligencia artificial, entrenamos una regresión logística para estimar si existe un aporte positivo en “TOTAL 2026”, usando únicamente el historial hasta 2025. En una partición aleatoria estratificada, con 545 registros de prueba, el ROC-AUC fue 0,773, la exactitud 67,2%, la precisión 71,3% y el recall 47,6%. Esto mide la capacidad de distinguir los dos resultados dentro de esta evaluación, no garantiza que una persona vaya a aportar. Además, 2026 puede ser un periodo incompleto, así que el modelo es exploratorio y necesita una validación temporal antes de usarse en producción.
>
> En recursos, ordenamos las columnas con registros positivos. El bono 2026 es el más frecuente, con 729 registros positivos, seguido del banquete con 184. Este orden refleja participación registrada en la hoja; no demuestra la preferencia individual ni que un recurso haya causado una donación.
>
> El tablero permite seleccionar segmento y año, consultar gráficos de cantidad y monto, ver la frecuencia y antigüedad del último pago, y probar una planificación de contacto por telemercaderista, fecha y recurso.
>
> Para teléfonos compartidos no fusionamos personas: cada beneficiario mantiene su propia referencia y usamos un token de grupo para coordinar el calendario. Si dos gestiones comparten el token y la fecha, la segunda se desplaza a otro día. El token debe generarse con HMAC y una clave secreta en el entorno autorizado; el prototipo no almacena teléfonos y su agenda solo se conserva en memoria del navegador.
>
> Finalmente, las salidas analíticas son agregadas, el Excel original no se modifica y las solicitudes de no contacto se respetan en la planificación. Esta entrega es un prototipo local: todavía no consulta una agenda persistente de llamadas ni se conecta a un sistema operativo de la Fundación. Como siguiente paso proponemos validar los resultados con responsables de los datos, incorporar almacenamiento seguro de las gestiones y evaluar el modelo con un periodo futuro.

## Demostración en pantalla

### 1. Clasificación de un benefactor

- En el notebook, mostrar la distribución de los cinco segmentos.
- Explicar la regla: recurrente significa aporte positivo en al menos tres de los años 2023–2026; el aporte único significa un solo año positivo en todo el historial.
- Si preguntan por un caso individual, usar el ejemplo didáctico de abajo. No imprimir una fila real del Excel.

Ejemplo ficticio para explicar la regla:

| Año | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|
| Aporte registrado | Sí | Sí | Sí | No |

Con tres años positivos en la ventana reciente, la regla lo clasifica como **recurrente**. La clasificación es histórica, no una valoración de la persona.

### 2. Comportamiento histórico

- Mostrar los rangos de frecuencia y la distribución de antigüedad de `ULT PAGO`.
- Señalar que la fecha está normalizada desde el número de serie de Excel o texto válido.
- Distinguir “sin registro” de “no ocurrió”: los vacíos no se convierten en cero ni se interpretan como evidencia de ausencia.

### 3. Modelo

- Explicar la etiqueta: `TOTAL 2026 > 0`.
- Explicar las variables: monto histórico transformado, años activos, aportes recientes y último año positivo; sin datos de identidad o contacto.
- Mostrar ROC-AUC, precisión, recall y matriz de confusión.
- Recalcar que el holdout aleatorio no equivale a evaluación temporal y que el modelo no decide a quién contactar.

### 4. Selección de recurso y contacto

- En el tablero, seleccionar telemercaderista, fecha y recurso.
- Introducir una referencia ficticia, como `DEMO-PERSONA-1`.
- Agregar la gestión y señalar que la tabla se encuentra en memoria del navegador; recargar la página la borra.
- Mostrar que marcar “No contactar” bloquea la planificación.

### 5. Teléfono compartido

- Programar `DEMO-PERSONA-1` y `DEMO-PERSONA-2` con el mismo token ficticio `DEMO-GRUPO-01` para la misma fecha.
- Mostrar que ambas personas permanecen separadas, pero las fechas quedan en días distintos.
- Explicar que la fuente de Excel no basta para comprobar llamadas pendientes; la coordinación real requiere una agenda autorizada y persistente.

### 6. Visualizaciones y gobierno

- Filtrar el tablero por segmento y año.
- Mostrar gráficos de montos y beneficiarios con aporte, tabla de segmentos, orden de recursos y resúmenes de frecuencia/recencia.
- Indicar que el Warehouse SQLite contiene dimensiones y hechos agregados; las salidas no exponen filas individuales.

## Preguntas que pueden hacer

**¿Por qué no se entrena un modelo para recomendar directamente el recurso a cada beneficiario?**  
La base no tiene una etiqueta fiable de interés o respuesta por persona y recurso. El modelo actual estima únicamente si existe un aporte positivo registrado en el total de 2026. Recomendar un recurso individual con esos datos sería inventar una preferencia.

**¿ROC-AUC 0,773 significa 77,3% de probabilidad de acertar?**  
No. Significa que, en el conjunto de prueba, el modelo ordena un caso positivo por encima de uno negativo aproximadamente en esa proporción de pares. No es exactitud ni una probabilidad individual calibrada.

**¿El teléfono compartido combina a los beneficiarios?**  
No. Cada uno conserva su referencia propia. El token identifica un grupo de coordinación para espaciar gestiones; no es una clave de identidad ni autoriza el contacto.

**¿El prototipo detecta automáticamente números repetidos en el Excel?**  
El módulo incluye una función HMAC que permite crear un token local a partir del número con una clave secreta. El tablero de demostración recibe el token ya calculado; todavía no integra una importación segura de teléfonos ni los compara con un historial real de llamadas.

**¿El plan de llamadas se conserva al cerrar el tablero?**  
No. La demostración lo mantiene en memoria del navegador. La persistencia y la consulta de contactos pendientes son trabajo futuro que requeriría permisos y almacenamiento seguro.

**¿Qué sigue para producción?**  
Validar moneda, fecha de corte y reglas de negocio; agregar una tabla transaccional y agenda segura; verificar consentimiento y restricciones; y evaluar el modelo en un periodo futuro antes de apoyar decisiones operativas.
