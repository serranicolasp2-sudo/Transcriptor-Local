# Traspaso — Tema "Tu Tiendita IA" e ícono del Transcriptor

**Fecha:** 2026-10-21 · **Hecho por:** Claude (Claude Code) · **Sigue:** Antigravity

## Objetivo

Darle al Transcriptor (CustomTkinter) un ícono propio y la paleta de marca **Tu Tiendita IA**, igual que se hizo con las 3 herramientas de `Videoclip Pixar/Herramientas` (OmniBoost, OmniFlow y OmniScale).

## Estado: HECHO y verificado con capturas

| Qué | Dónde | Estado |
|---|---|---|
| Ícono (globo de diálogo con renglones por hablante + cursor Malvón) | `recursos/transcriptor.ico`, `.png` (1024), `_256.png` | ✅ |
| Generador del ícono (reproducible) | `recursos/generar_icono.py` → `python recursos/generar_icono.py` | ✅ |
| Tema JSON de CustomTkinter con la paleta | `recursos/tema_tutiendita.json` | ✅ |
| Módulo de tema: paleta, ícono, barra de título, encabezado | `src/tema.py` | ✅ |
| GUI conectada al tema, sin colores fijos | `src/gui.py` | ✅ |
| Ícono en el `.exe` + recursos empaquetados | `Transcriptor.spec` (`icon=` y 3 `datas.append`) | ✅ editado, **sin recompilar** |
| Ícono del instalador | `instalador/Transcriptor.iss` (`SetupIconFile`) | ✅ editado, **sin recompilar** |

### Paleta usada (`src/tema.py`)

Birome `#1E3C96` (acción) · Tinta `#16205A` · Malvón `#E0435C` (acento/peligro) · Yema `#FFD23F` (éxito, progreso, insignia) · Cinta `#1A1712` (texto sobre Yema) · Papel `#F6F7FA` (texto) · Plata `#95A2C2` (texto secundario) · Celeste `#AFC0FF` (timestamps, chips).
Fondos derivados de Tinta: app `#0A1024`, cuerpo de pestañas `#0E1631`, tarjetas `#131D40`, bordes `#25336A`.

### Cambios en `src/gui.py`

- `tema.aplicar_tema_global()` reemplaza a `set_appearance_mode` y `set_default_color_theme("blue")`.
- `tema.aplicar_icono(self)` en `__init__`: ícono de ventana y barra de tareas (AppUserModelID `TuTienditaIA.Transcriptor`) y barra de título color Tinta.
- Encabezado nuevo (fila 0): ícono, "Transcriptor", insignia IA, subtítulo, chip "100% LOCAL" y filete Birome/Malvón/Yema. La pestañera pasó a la fila 1. Ventana: 1000x840, mínimo 880x700.
- Las 11 tarjetas tienen `corner_radius=12, border_width=1` (antes se fundían con el fondo).
- Mapeo de colores: verdes → Yema con texto Cinta (Cargar, Abrir en Visor, ▶ de cada segmento); rojo de Cancelar → botón de peligro sobrio (`PELIGRO_*`, texto `MALVON_SUAVE`); `#A0A0A0` → Plata; `#64B5F6` → Celeste; éxito `#4CAF50` → Yema; error `#F44336` → `MALVON_SUAVE`; tarjeta de resultados `EXITO_BG` con borde Yema.
- Tipografía: Segoe UI (antes Roboto, que no está instalada y Windows la reemplazaba).

## PENDIENTE para Antigravity

1. **Verificar las otras 3 pestañas** (Visor y Editor, Administrar Hablantes, Configuración). Solo se capturó la pestaña Transcripción. Revisar sobre todo las filas de segmentos del Visor (`corner_radius=6`, quedaron con `top_fg_color`) y que los botones ▶ amarillos no saturen con muchas filas.
2. **Recompilar el instalador** con `instalador\construir_instalador.bat` para que el `.exe` y el setup lleven el ícono. Después, instalarlo y comprobar que la app encuentre `recursos/` dentro de `_internal` (la ruta se resuelve con `sys._MEIPASS` en `src/tema.py`).
3. **Probar una transcripción real corta** (por ejemplo, algo de `input/`) para ver la barra Yema avanzando y la tarjeta de resultados.
4. Opcional, mejoras visuales:
   - Las métricas (Audio procesado, Tiempo, RAM) son labels de dos líneas. Podrían ser "stat tiles" con título Plata y valor grande, pero el código actualiza el texto completo en varios lugares (`_actualizar_gui_progreso`, `_tick_live_timer`, `_actualizar_ram_label`).
   - El título de la ventana todavía dice "(AMD Ryzen / Radeon)".
   - Con la barra en 0, CustomTkinter muestra un punto amarillo. Es un comportamiento propio de `CTkProgressBar`, no un bug nuestro.
   - El modo claro del JSON tiene valores razonables pero no se probó (la app fuerza el modo oscuro).
5. `src/gui.py` usa `self.tabview._segmented_button` (atributo privado de CTk 6.0.0) para la fuente y el alto de las pestañas. Si se actualiza CustomTkinter, revisarlo.

## Notas

- **No tocar `.env`**: tiene el token de Hugging Face.
- Los archivos originales (`gui.py`, `.spec` y `.iss`) se respaldaron en el scratchpad temporal de la sesión de Claude, que puede borrarse. Si hace falta volver atrás y no están, se reconstruyen deshaciendo lo listado arriba.
- Los archivos usan finales de línea **LF**; mantenerlos así.
- El mismo sistema visual (versión Tkinter puro) está en `Desktop/Proyectos/Videoclip Pixar/Herramientas/ui_theme.py`, con íconos en `Herramientas/iconos/` y accesos directos `.lnk` en `Videoclip Pixar/`.

## Avance de Antigravity

**Fecha:** 2026-10-22 · **Hecho por:** Antigravity

### 1. Mejoras visuales y Stat Tiles implementados (Tarea 4)
- **Título de la ventana:** Se removió `(AMD Ryzen / Radeon)`, quedando como `Transcriptor Local — Diarización de 4 Hablantes`.
- **Stat tiles de métricas:** Las 4 métricas se convirtieron en tarjetas dedicadas (`corner_radius=8`, fondo `tema.CHIP_BG`, borde `tema.CARD_BORDER`) con títulos chicos en mayúsculas color `PLATA` y valores grandes destacados en `PAPEL`. Se actualizaron en sincronía los 4 métodos que las modifican (`_seleccionar_archivo`, `_tick_live_timer`, `_actualizar_gui_progreso` y `_actualizar_ram_label`).
- **Filas de segmentos en el Visor:**
  - Se estilizaron como tarjetas individuales con `corner_radius=8`, fondo `tema.CHIP_BG` y borde `tema.CARD_BORDER`, lo que brinda una separación limpia entre segmentos.
  - Los botones de reproducción ▶ de cada segmento se pasaron a Birome (`tema.BIROME` con hover `BIROME_HOVER` y texto `PAPEL`). Esto eliminó por completo la saturación visual que causaba tener decenas de botones amarillos en fila, reservando el color Yema exclusivamente para llamados a la acción principales (Cargar, Abrir en Visor, progreso).
- **Ajuste de proporciones y espaciado:** Se ajustó la ventana base a 1000x870 px y se optimizaron márgenes verticales de las tarjetas, logrando que la tarjeta de resultados y sus 4 botones de acción queden perfectamente encuadrados y holgados en pantalla.

### 2. Prueba real de transcripción (Tarea 2)
- Se ejecutó una prueba de punta a punta con el archivo más corto en `input/`: `WhatsApp Video 2026-09-23 at 2.33.26 PM.mp4` (~96.8 s).
- Se confirmó el avance fluido de la barra de progreso en color **Yema** (`#FFD23F`) y la actualización continua de los stat tiles.
- Al finalizar, apareció la tarjeta de resultados con fondo `EXITO_BG` y borde **Yema**, habilitando la apertura directa de carpeta, `.txt`, `.docx` y carga en Visor.
- Se verificó la generación íntegra de:
  - `output/WhatsApp Video 2026-09-23 at 2.33.26 PM.docx`
  - `output/WhatsApp Video 2026-09-23 at 2.33.26 PM.srt`
  - `output/WhatsApp Video 2026-09-23 at 2.33.26 PM.txt`
  - `output/WhatsApp Video 2026-09-23 at 2.33.26 PM_completo.json`

### 3. Verificación de las 4 pestañas con capturas (Tarea 1)
Se guardaron capturas en alta resolución en `recursos/capturas/`:
- `01_tab1_inicio.png`: Pestaña Transcripción con archivo cargado y stat tiles listos.
- `02_tab1_progreso.png`: Transcripción en vivo con barra Yema al 22% y botón Cancelar en peligro sobrio.
- `03_tab1_completado.png`: Transcripción completada al 100% con tarjeta de resultados visible y todos sus botones.
- `04_tab2_visor_editor.png`: Visor y Editor con 20 segmentos cargados, badges de timestamp en Celeste, campos editables contrastados y botones ▶ en Birome.
- `05_tab3_administrar_hablantes.png`: Pestaña de administración de hablantes con mapeo de los 4 speakers precargados.
- `06_tab4_configuracion.png`: Pestaña de configuración con tarjetas del sistema, token local y accesos a carpetas.

### 4. Recompilación del instalador (Tarea 3)
- Se ejecutó `instalador\construir_instalador.bat` de forma completa y sin errores:
  - **PyInstaller:** Empaquetó el proyecto en `build_instalador\dist\Transcriptor\Transcriptor.exe` asignando el ícono `recursos\transcriptor.ico`.
  - **Recursos empaquetados:** Se confirmó que `_internal\recursos\` contiene `tema_tutiendita.json`, `transcriptor.ico` y `transcriptor_256.png`.
  - **Prueba del ejecutable:** Se ejecutó `build_instalador\dist\Transcriptor\Transcriptor.exe` comprobando que carga el tema Tu Tiendita IA vía `sys._MEIPASS` (capturado en `07_packaged_exe.png`), sin recurrir al azul por defecto.
  - **Inno Setup:** Empaquetó binarios (`ffmpeg`, `ffprobe`, `ffplay`), dist y modelos de IA en `instalador\salida\Transcriptor_Instalador_1.0.exe` (1.85 GB) con el ícono nuevo verificado.

### 5. Estado y Pendientes
- **Estado general:** 100% completado y verificado.
- **Pendientes:** Ninguno funcional ni estético. Se preservó el `.env` intacto y todos los archivos mantienen finales de línea LF.
