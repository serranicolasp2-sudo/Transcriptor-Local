@echo off
chcp 65001 >nul 2>&1
echo ============================================================
echo    REEMPLAZAR NOMBRES DE HABLANTES
echo ============================================================
echo.
echo Uso: reemplazar_nombres.bat "SPEAKER 01=Nicolas" "SPEAKER 02=Juan" "SPEAKER 03=Maria" "SPEAKER 04=Pedro"
echo.

call "%~dp0entorno\Scripts\activate.bat"

python "%~dp0scripts\reemplazar_nombres.py" --mapeo %*

echo.
pause
