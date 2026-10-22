# Traspaso: modelos descargables y aceleración NVIDIA

**Fecha:** 2026-10-22 · **Hecho por:** Claude (Claude Code) · **Sigue:** Antigravity / Nicolás, para probar en Windows

## Lo que se pidió

> La versión estándar ya instalada; las otras se ofrecen para descargar desde la misma aplicación, se instalan solas en segundo plano con barra de progreso y después piden reiniciar.

- **Estándar (incluido):** Whisper large-v3-turbo en CPU. Sin cambios.
- **Descargables:** Whisper small, Whisper large-v3 y Aceleración NVIDIA.
- **AMD Radeon:** queda fuera por ahora. CTranslate2 publica desde la 4.7.0 (febrero de 2026) una versión con ROCm, con wheels para Windows en sus *releases* de GitHub, no en PyPI. Pero hay reportes de **transcripciones erróneas sin aviso** en una RX 7900 XTX ([issue #2114](https://github.com/OpenNMT/CTranslate2/issues/2114)) y de choques de versión con el instalador HIP de Windows ([issue #2016](https://github.com/OpenNMT/CTranslate2/issues/2016)). Además, las RX 6600/6700 no están en la lista de placas soportadas. Si se retoma: un componente más que cambie el `ctranslate2` por el de ROCm, y una prueba que compare un audio corto contra la CPU antes de activarlo.

## Qué se hizo

| Archivo | Cambio |
|---|---|
| `src/componentes.py` (nuevo) | Catálogo fijado (URL con revisión, tamaño y SHA-256 de cada archivo), descarga con reanudación (`.part` + `Range`), reintentos, verificación, cancelación, extracción de las DLL del wheel de NVIDIA, ajustes (`ajustes.json`), elección del motor y línea de comandos `python -m src.componentes`. |
| `src/engine.py` | Registra las DLL de NVIDIA antes de cargar Whisper; carga el modelo y el dispositivo elegidos (`motor_actual()`); **si la placa falla al cargar o a mitad de la transcripción, sigue con la CPU** y lo avisa en el progreso; graba en el `.json` el motor real (antes decía fijo "CPU (AMD Ryzen)"). Además le pasa a Whisper el audio ya leído con `soundfile`, en lugar de la ruta (ver "Arreglo aparte"). |
| `src/gui.py` | Configuración desplazable; tarjeta "Motor y Hardware de esta PC" con datos **detectados** (antes mostraba fijos los de la PC de Nicolás); tarjeta nueva "Modelos y Aceleración" con Descargar / Cancelar / Seguir / Eliminar, barra de progreso con velocidad y tiempo restante, selector de modelo, interruptor de placa y aviso "Reiniciar ahora". Si se cierra con una descarga en curso, pregunta y la deja en pausa. |
| `tests/test_componentes.py`, `tests/test_motor.py` (nuevos) | 17 tests (ver abajo). |
| `LEEME.md` | Sección "Modelos y aceleración opcionales"; requisitos corregidos: el README decía que la app usaba la placa y no era así. |
| `.gitignore` | `ajustes.json`. |

**No hace falta tocar** `Transcriptor.spec` (el módulo nuevo se importa de forma directa y solo usa la biblioteca estándar) ni `instalador/Transcriptor.iss` (todo se guarda en `models\`, que el desinstalador ya borra).

### Por qué el paquete NVIDIA es solo cuBLAS

Desde la **4.6.3**, las versiones oficiales de CTranslate2 se compilan **sin cuDNN** (PR [#1949](https://github.com/OpenNMT/CTranslate2/pull/1949): conv1d propio en CUDA). En el `ctranslate2.dll` de la 4.8.3 para Windows solo aparece `cublas64_12.dll`. Por eso el paquete baja `nvidia-cublas-cu12==12.8.4.1` de PyPI (568 MB) y extrae `cublas64_12.dll` y `cublasLt64_12.dll`, más la licencia de NVIDIA. **El `entorno\` tiene que tener `ctranslate2>=4.6.3`**; si no, la app lo detecta y muestra "actualizá el Transcriptor" en vez de activar la placa.

## Cómo se verificó (Linux, sin GPU)

- **Las 10 URLs reales del catálogo** responden con el tamaño fijado, y los archivos chicos dan la misma SHA-256.
- **Instalación real** con el módulo: Whisper small (486 MB, 5 s) y el paquete NVIDIA (568 MB, 25 s, las dos DLL extraídas con su tamaño correcto).
- **El modelo instalado transcribe**: `engine.transcribir_whisper` con small elegido en los ajustes, sobre un audio de prueba con dos voces.
- **Interfaz** (Xvfb, Python 3.12, motor simulado): descarga real de small con la barra, pregunta de reinicio, small elegido en el menú y aviso de reinicio; pausa de large-v3 con lo bajado guardado y "En pausa · N MB bajados / Seguir" al reabrir; interruptor de placa con el paquete instalado; eliminar; comando de reinicio.
- **17 tests** con un servidor HTTP local: huella incorrecta, cancelar y retomar sin rebajar, conexión cortada, servidor que ignora `Range`, 404, falta de espacio, extracción del wheel, borrado con un archivo en uso, ajustes rotos, elección de motor y vuelta a CPU (al cargar, a mitad de la transcripción, sin tapar errores de CPU y sin disparar con Cancelar).

```bash
entorno\Scripts\python -m pytest tests
```

## Lo que falta probar en Windows (checklist)

1. **Compilar** con `instalador\construir_instalador.bat`, instalar y abrir **Configuración**: los datos de "Motor y Hardware" tienen que ser los de esa PC.
2. **Descargar Whisper small**: barra, velocidad, "quedan…". Al terminar pregunta si reiniciar → **Sí** → la app se vuelve a abrir sola y el encabezado dice "Whisper small". Transcribir un audio corto.
3. **Pausa**: empezar large-v3, tocar **Cancelar**, cerrar la app, abrirla: tiene que decir "En pausa · N MB bajados" y **Seguir** retoma sin empezar de cero.
4. **Sin placa NVIDIA**: la fila NVIDIA dice "No compatible" y el botón está desactivado.
5. **Con placa NVIDIA** (GTX 16xx / RTX, driver 527.41 o posterior, el mínimo para CUDA 12):
    - descargar la aceleración → reiniciar → "Motor y Hardware" dice `… · placa NVIDIA · float16`;
    - transcribir y comparar el tiempo contra la CPU;
    - apagar "Usar la placa NVIDIA", reiniciar: vuelve a la CPU.
6. **La placa falla**: con el paquete instalado, renombrar `models\nvidia-cuda12\cublasLt64_12.dll` y abrir la app. Tiene que mostrar "Las librerías de NVIDIA no cargan…" y transcribir con la CPU.
7. **Eliminar la aceleración con la app abierta y en uso**: Windows no deja borrar la DLL cargada. La app deja de usarla igual y la carpeta se limpia sola en el próximo arranque.
8. **Versión portable**: lo mismo desde el `.zip` descomprimido en un pendrive (todo queda en su `models\`).

## Arreglo aparte (para tener en cuenta)

`engine.py` le pasaba a Whisper la **ruta** del WAV, y eso hace que faster-whisper lo abra con PyAV. Con las versiones actuales (`faster-whisper` 1.2.1 y `av` 19.0.2) falla con `open() got an unexpected keyword argument 'metadata_errors'`. Pasó al probar este cambio con un entorno nuevo. Ahora se lee el WAV con `soundfile` (ya era una dependencia) y se le pasa el audio cargado. Si en `entorno\` hay versiones viejas no cambia nada; si se actualiza, ya no se rompe.
