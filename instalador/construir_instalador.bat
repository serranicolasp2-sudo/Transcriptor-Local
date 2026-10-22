@echo off
chcp 65001 >nul 2>&1
:: Genera instalador\salida\Transcriptor_Instalador_X.exe
:: Requisitos: entorno\ con PyInstaller, ffmpeg en el PATH, Inno Setup 6.
setlocal
cd /d "%~dp0.."

echo [1/3] Compilando con PyInstaller...
"entorno\Scripts\python.exe" -m PyInstaller Transcriptor.spec --noconfirm --clean --distpath build_instalador\dist --workpath build_instalador\work
if errorlevel 1 goto :error

echo [2/3] Copiando ffmpeg, ffprobe y ffplay...
if not exist build_instalador\bin mkdir build_instalador\bin
for %%B in (ffmpeg ffprobe ffplay) do call :copiar_bin %%B
if not exist build_instalador\bin\ffplay.exe goto :error
if not exist build_instalador\bin\ffprobe.exe goto :error
if not exist build_instalador\bin\ffmpeg.exe goto :error

echo [3/3] Generando instalador con Inno Setup...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
"%ISCC%" instalador\Transcriptor.iss
if errorlevel 1 goto :error

echo.
echo Listo: instalador\salida\
pause
exit /b 0

:copiar_bin
for /f "delims=" %%P in ('where %1 2^>nul') do (
    copy /y "%%P" build_instalador\bin\ >nul
    exit /b 0
)
echo No se encontro %1 en el PATH.
exit /b 1

:error
echo.
echo ERROR: fallo la construccion del instalador.
pause
exit /b 1
