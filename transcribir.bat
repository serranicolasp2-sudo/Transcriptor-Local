@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo    TRANSCRIPTOR LOCAL - faster-whisper + pyannote
echo ============================================================
echo.

:: Activar entorno virtual
call "%~dp0entorno\Scripts\activate.bat"

:: Verificar que el token esté configurado (no hace falta si los modelos ya están en models\)
python -c "from src.config import cargar_token_hf, modelos_diarizacion_locales as m; import sys; sys.exit(0 if (m() or cargar_token_hf()) else 1)" 2>nul
if errorlevel 1 (
    echo.
    echo ❌ ERROR: Token de Hugging Face no configurado.
    echo.
    echo    Edita el archivo .env en esta carpeta
    echo    y reemplaza TU_TOKEN_AQUI por tu token.
    echo.
    echo    Instrucciones:
    echo    1. Crea cuenta en https://huggingface.co
    echo    2. Acepta terminos en:
    echo       https://huggingface.co/pyannote/speaker-diarization-3.1
    echo       https://huggingface.co/pyannote/segmentation-3.0
    echo    3. Genera token en: https://huggingface.co/settings/tokens
    echo    4. Pegalo en el archivo .env
    echo.
    pause
    exit /b 1
)

:: Ejecutar transcriptor
python "%~dp0scripts\transcribir.py" %*

echo.
echo ============================================================
echo    Procesamiento finalizado.
echo    Los resultados estan en la carpeta output/
echo ============================================================
echo.
pause
