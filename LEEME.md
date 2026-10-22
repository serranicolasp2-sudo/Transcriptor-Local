# Transcriptor Local — Whisper Large-v3-Turbo + Diarización de 4 Hablantes

> **Estación de trabajo de reconocimiento de voz, diarización de hablantes y edición interactiva.**  
> 100% Local, Privado y Offline.  
> Desarrollado con el diseño visual oficial de **Tu Tiendita IA** (Sitio web oficial: [tutiendita-ia.store](https://tutiendita-ia.store)).

---

## 🎨 Identidad Visual y Diseño de Marca: "Tu Tiendita IA"

El **Transcriptor Local** cuenta con una interfaz gráfica moderna desarrollada sobre el framework CustomTkinter Fluent, personalizada con la paleta de diseño oficial de **Tu Tiendita IA** ([tutiendita-ia.store](https://tutiendita-ia.store)), plataforma y tienda líder en Inteligencia Artificial aplicada.

### Paleta Oficial "Tu Tiendita IA" y Asignación de Roles:
- **Azul Birome (`#1E3C96` / `#2A4FC0`)**: Acciones principales de inicio, botones de reproducción ▶ de audio por segmento en el Visor y asignación del **Hablante 1**.
- **Azul Tinta Profundo (`#16205A` / `#0A1024`)**: Fondo inmersivo de la aplicación, barra de título integrada y tarjetas elevadas.
- **Rosa Malvón (`#E0435C` / `#FF7A90`)**: Botón de cancelación de emergencia, alertas de error y asignación del **Hablante 2**.
- **Amarillo Yema (`#FFD23F` / `#FFDD66`)**: Barra de progreso animada, marcos de finalización exitosa, botones de exportación y asignación del **Hablante 3**.
- **Azul Celeste / Periwinkle (`#AFC0FF`)**: Insignias de tiempo (timestamps), chips de estado y asignación del **Hablante 4**.
- **Plata y Papel (`#95A2C2` / `#F6F7FA`)**: Tipografía *Segoe UI* de alta legibilidad, títulos en mayúsculas de métricas y textos principales de transcripción.

---

## 📖 Descripción General

El **Transcriptor Local** es una herramienta integral de escritorio que transforma cualquier archivo de audio o video en texto escrito de alta precisión, identificando y separando automáticamente **quién habla en cada momento** (diarización de hasta 4 interlocutores distintos).

### ¿Para qué sirve y quiénes lo utilizan?
- **Podcasters y Creadores de Contenido**: Generación de subtítulos profesionales `.SRT` para YouTube, TikTok, Reels o Premiere, con timestamps sincronizados milimétricamente.
- **Periodistas e Investigadores**: Transcripción rápida de entrevistas cara a cara o telefónicas sin perder tiempo tipeando a mano.
- **Abogados, Notarios y Empresas**: Transcripción confidencial de declaraciones, audiencias y reuniones de directorio con separación clara de los participantes.
- **Docentes y Estudiantes**: Conversión de clases magistrales, conferencias y talleres a documentos Word listos para estudiar.

### Privacidad Total y Funcionamiento 100% Offline
A diferencia de servicios en la nube (como Google Cloud, AWS, Otter o plataformas web) que te cobran por minuto y suben tus audios confidenciales a servidores remotos, el **Transcriptor Local funciona íntegramente dentro de tu computadora**. No envía ni un solo byte por internet, no requiere tokens activos de Hugging Face para funcionar y no tiene ningún límite en la duración de los audios que podés procesar.

---

## 🧠 Modelos de Inteligencia Artificial Integrados

La aplicación viene empaquetada con los pesos y modelos locales de IA listos para usar:

1. **Whisper `large-v3-turbo` (OpenAI)**:
   - La arquitectura más avanzada, veloz y precisa de la familia Whisper.
   - Entrenada con más de 5 millones de horas de audio multilingüe.
   - Puntuación automática perfecta (puntos, comas, signos de interrogación y admiración).
   - Excelente comprensión del español con soporte para modismos y acentos rioplatenses, latinoamericanos y españoles, además de inglés y más de 90 idiomas adicionales.
   - Resistencia excepcional al ruido ambiente, música de fondo o reverberación.

2. **Pyannote Speaker Diarization Community-1 / 3.1 (Diarización Neural de Hablantes)**:
   - El modelo de referencia a nivel mundial para segmentación e identificación de locutores.
   - Analiza la huella acústica de cada voz a lo largo del tiempo y determina qué fragmento corresponde a cada uno de los 4 hablantes.
   - Cuenta con soporte de fallback automático para compatibilidad garantizada.

---

## 📑 Estructura de la Aplicación: Las 4 Pestañas

La aplicación organiza todo el flujo de trabajo en 4 pestañas especializadas:

### 1. Pestaña "Transcripción" (Flujo Principal)
- **Selección de Archivo**: Soporta cualquier formato de audio o video (.mp3, .wav, .m4a, .mp4, .mkv, .flac, .mov, etc.) y calcula de inmediato su duración total.
- **Configuración de los 4 Hablantes**: Permite pre-asignar nombres personalizados a cada uno de los 4 hablantes (por ejemplo: "Entrevistador", "Invitado", "Nicolás", "Whitney"), asociando visualmente sus colores de marca (Birome, Malvón, Yema, Periwinkle).
- **Stat Tiles de Métricas en Vivo**: 4 tarjetas de elevación estilizadas que monitorean el proceso en tiempo real:
  - **Audio Procesado**: Tiempo de audio analizado / Duración total.
  - **Tiempo Transcurrido**: Cronómetro en vivo desde el inicio del render.
  - **Tiempo Restante**: Estimación dinámica calculada según la velocidad de procesamiento.
  - **Memoria RAM**: Monitoreo de consumo de memoria del sistema y de la aplicación.
- **Barra de Progreso Yema**: Indicador porcentual animado con filete de marca.
- **Terminal de Logs Integrada**: Muestra detalladamente cada fase (extracción de audio a 16 kHz mono, diarización acústica, decodificación Whisper y ensamble de salidas).
- **Tarjeta de Resultados Exitosos**: Al completar la tarea, despliega una tarjeta destacada con borde Yema que permite abrir directamente con un solo clic el archivo `.TXT`, el informe `.DOCX`, la carpeta contenedora o cargar el proyecto en el Visor y Editor.

### 2. Pestaña "Visor y Editor"
- Permite abrir cualquier archivo `*_completo.json` generado en la carpeta `output/`.
- Muestra toda la transcripción desglosada en tarjetas independientes por segmento de tiempo.
- **Reproductor de Audio Integrado**: Cada segmento incluye un botón de reproducción ▶ en color Birome que reproduce exclusivamente el fragmento de audio correspondiente a esa frase, permitiéndote verificar la exactitud de lo que se dijo.
- **Edición en Vivo**: Podés corregir cualquier palabra, nombre propio o signo de puntuación directamente sobre la caja de texto.
- **Reasignación de Hablante**: Podés cambiar el hablante de cualquier segmento mediante un menú desplegable si una frase correspondía a otra persona.
- **Re-exportación Instantánea**: El botón *Guardar Cambios y Re-exportar Todo* actualiza y vuelve a generar en un segundo todos los archivos (.TXT, .SRT, .DOCX y .JSON) con tus correcciones aplicadas, ¡sin necesidad de volver a transcribir el audio!

### 3. Pestaña "Administrar Hablantes"
- Diseñada para reasignar nombres de forma masiva en proyectos ya transcriptos.
- Si en un proyecto de 2 horas los hablantes quedaron identificados como `SPEAKER_00` y `SPEAKER_01`, podés mapear en esta pestaña:
  - `SPEAKER_00` ➔ "Martín"
  - `SPEAKER_01` ➔ "Laura"
- Al presionar **"Aplicar Cambios Globales"**, el programa renombra automáticamente a los interlocutores en los cientos de segmentos del proyecto y re-exporta los archivos finales al instante.

### 4. Pestaña "Configuración"
- **Motor y Hardware de esta PC**: Muestra con qué se está transcribiendo (modelo, CPU o placa NVIDIA) y el procesador, la RAM y la placa detectados en tu equipo.
- **Modelos y Aceleración**: Descargá desde la misma app otros modelos de Whisper y la aceleración NVIDIA, con barra de progreso (ver [Modelos y aceleración opcionales](#-modelos-y-aceleración-opcionales)).
- **Token de Hugging Face (Opcional)**: Campo seguro por si deseás vincular tu propia cuenta para futuras actualizaciones de modelos.
- **Accesos Rápidos**: Botones para abrir en el Explorador de Windows las carpetas `input/`, `output/` y `logs/`.
- **Diseño y Tema Visual**: Información institucional acreditando el tema visual de **Tu Tiendita IA** ([tutiendita-ia.store](https://tutiendita-ia.store)).

---

## 📄 Formatos de Salida Generados

Por cada audio procesado, el Transcriptor Local genera automáticamente 4 archivos en la carpeta `output/`:

1. **Subtítulos `.SRT`**:
   - Sincronizados con formato estándar de subtitulado:
     ```srt
     1
     00:00:01,200 --> 00:00:04,500
     [Hablante 1]: Hola, ¿cómo están todos hoy?
     ```
   - Listos para importar directamente en Adobe Premiere Pro, DaVinci Resolve, Final Cut Pro, CapCut, o subir a YouTube.

2. **Texto Plano `.TXT`**:
   - Documento limpio, fácil de leer y copiar, estructurado por bloques de texto con identificación de locutor.

3. **Informe Profesional `.DOCX` (Microsoft Word)**:
   - Documento listo para entregar a clientes o directivos.
   - Incluye portada con metadatos (nombre de archivo, duración total, fecha, cantidad de participantes).
   - Tabla estadística con la distribución del tiempo de habla por persona.
   - Cuerpo de transcripción con títulos en color por interlocutor.

4. **Base de Datos del Proyecto `*_completo.json`**:
   - Archivo JSON estructurado con todos los timestamps exactos de inicio y fin, nivel de confianza probabilístico, texto del segmento y etiqueta de hablante.
   - Es el archivo que podés reabrir en cualquier momento desde la pestaña "Visor y Editor".

---

## 🚀 Guía de Uso Rápida

1. **Colocá tus audios**: Podés copiar tus audios o videos en la carpeta `input/` o buscarlos en cualquier disco con el botón **"Examinar..."**.
2. **Definí los nombres**: En la tarjeta de Hablantes, escribí los nombres reales de los participantes si los conocés (o dejalos por defecto como Hablante 1, 2, etc.).
3. **Iniciá la transcripción**: Presioná el botón grande **"Iniciar Transcripción"**.
4. **Seguí las métricas**: Vas a ver cómo avanzan los stat tiles de tiempo transcurrido, tiempo restante y memoria RAM.
5. **Revisá y disfrutá tus resultados**: Al terminar, hacé clic en **"Abrir Carpeta Output"**, abrí el informe de Word o cargalo en el **Visor y Editor** para repasar cualquier detalle.

---

## 📁 Formatos de Entrada Compatibles

- **Archivos de Audio**: `.mp3`, `.wav`, `.m4a`, `.flac`, `.aac`, `.ogg`, `.wma`.
- **Archivos de Video**: `.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.ts`, `.wmv`.
*(El motor extrae automáticamente la pista de audio a 16.000 Hz monoaural antes del análisis sin dañar tu video original).*

---

## ⚡ Modelos y aceleración opcionales

La versión estándar viene lista para usar: **Whisper large-v3-turbo en la CPU**. Desde **Configuración → Modelos y Aceleración** se pueden sumar, con un clic:

| Componente | Descarga | Para qué |
|---|---|---|
| **Whisper small** | 486 MB | Más rápido y liviano. Para equipos con 8 GB de RAM o audios muy largos. |
| **Whisper large-v3** | 3,1 GB | Máxima precisión. Bastante más lento y pide más memoria. |
| **Aceleración NVIDIA** | 568 MB | Transcribe con la placa de video (GeForce GTX 16xx / RTX, driver actualizado). |

Cómo funciona:

- **Fuentes gratuitas y oficiales:** los modelos salen de Hugging Face (los mismos que usa faster-whisper) y la aceleración NVIDIA del paquete oficial `nvidia-cublas-cu12` de PyPI. Cada archivo tiene la dirección, el tamaño y la huella SHA-256 fijados en `src/componentes.py`: si lo que llega no coincide, no se instala.
- **En segundo plano y con barra de progreso**, con velocidad y tiempo restante. Se puede pausar: si se corta internet o cerrás la app, sigue desde donde quedó.
- **Al terminar pide reiniciar la aplicación** y, al volver a abrirla, ya usa lo que descargaste. Lo elegido se puede cambiar en "Modelo a usar" y "Usar la placa NVIDIA".
- **Si la placa falla** (driver viejo, poca memoria de video), la transcripción sigue sola con la CPU y lo avisa.
- Todo se guarda en `models/`, que se borra al desinstalar. Cada componente se puede eliminar desde la misma pantalla.
- La diarización (pyannote) sigue en la CPU: la placa acelera la parte de Whisper, que es la más pesada.

**Placas AMD Radeon:** el motor (CTranslate2) tiene desde 2026 una versión para ROCm, pero todavía da resultados erróneos en algunas placas. Queda en evaluación.

### Desde el código fuente

Lo mismo se puede hacer desde la terminal, con el entorno activado:

```bash
python -m src.componentes listar                    # qué hay instalado y qué se usa al abrir
python -m src.componentes instalar whisper-small    # o whisper-large-v3, nvidia-cuda12
python -m src.componentes usar small                # modelo a usar
python -m src.componentes gpu si                    # usar la placa NVIDIA (si / no)
python -m src.componentes eliminar whisper-small
```

La aceleración NVIDIA necesita **CTranslate2 4.6.3 o posterior**: desde esa versión ya no hace falta cuDNN, solo cuBLAS.

---

## 📦 Paquetes de Distribución

1. **Instalador Completo (`Transcriptor Instalador 1.0.exe` — 1.77 GB)**:
   - Empaqueta el ejecutable nativo, los modelos locales de IA completos (Whisper large-v3-turbo y Pyannote), FFmpeg y todas las dependencias.
   - Crea accesos directos en el Escritorio y Menú Inicio.
   - No requiere instalar Python ni ninguna librería externa.
2. **Versión Portable (`Transcriptor Portable.zip` — 2.95 GB)**:
   - Descomprimí en cualquier disco o unidad externa (disco SSD portátil / pendrive).
   - Iniciá la aplicación haciendo doble clic en `Transcriptor.exe`.
   - Las carpetas `input/`, `output/` y `logs/` quedan autocontenidas dentro del mismo directorio.

---

## 💻 Requisitos del Sistema

- **Sistema Operativo**: Windows 10 u 11 (64 bits).
- **Procesador**: Intel Core i5 / i7 / i9 o AMD Ryzen 5 / 7 / 9 (mínimo 4 núcleos físicos).
- **Memoria RAM**: 8 GB mínimo (16 GB recomendados para procesamiento fluido con large-v3-turbo; con 8 GB podés descargar Whisper small desde la app).
- **Placa Gráfica (Opcional)**: la versión estándar transcribe con la CPU. Para usar una NVIDIA GeForce GTX 1650, RTX 2060, 3060, 4060 o superior, descargá la **Aceleración NVIDIA** desde Configuración (568 MB) con drivers de NVIDIA actualizados.
- **Referencia medida**: en un Ryzen 7 5700X3D con 32 GB, large-v3-turbo en CPU tarda ~0,96× la duración del audio y usa ~11 GB de RAM.
- **Espacio en Disco**: ~5 GB libres para instalación y archivos temporales de procesamiento.

---

*Desarrollado para la suite creativa de **Tu Tiendita IA** · [https://tutiendita-ia.store](https://tutiendita-ia.store)*
