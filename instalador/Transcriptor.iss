; Instalador de Transcriptor (Inno Setup 6)
; Compilar con:  instalador\construir_instalador.bat
; Requiere haber corrido antes PyInstaller (Transcriptor.spec -> build_instalador\dist\Transcriptor)
; y tener ffmpeg/ffprobe/ffplay copiados en build_instalador\bin (lo hace el .bat).

#define AppName "Transcriptor"
#define AppVersion "1.0"
#define Raiz ".."

[Setup]
AppId={{6E1C5B0A-3F4E-4C8B-9B57-7A2D1E0F4C31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Nicolás
; Instalación por usuario: la app escribe input/, output/, logs/ y .env junto al .exe,
; así que no puede ir en Archivos de programa. No pide permisos de administrador.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Raiz}\instalador\salida
OutputBaseFilename=Transcriptor_Instalador_{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
DiskSpanning=no
WizardStyle=modern
SetupIconFile={#Raiz}\recursos\transcriptor.ico
UninstallDisplayIcon={app}\Transcriptor.exe
UninstallDisplayName={#AppName}

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Programa (PyInstaller onedir)
Source: "{#Raiz}\build_instalador\dist\Transcriptor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; ffmpeg / ffprobe / ffplay
Source: "{#Raiz}\build_instalador\bin\*.exe"; DestDir: "{app}\bin"; Flags: ignoreversion
; Modelos: Whisper large-v3-turbo + diarización pyannote (funciona sin internet ni token)
Source: "{#Raiz}\models\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo\*"; DestDir: "{app}\models\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Raiz}\models\models--pyannote--speaker-diarization-community-1\*"; DestDir: "{app}\models\models--pyannote--speaker-diarization-community-1"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\input"
Name: "{app}\output"
Name: "{app}\logs"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\Transcriptor.exe"; WorkingDir: "{app}"
Name: "{group}\Carpeta de resultados"; Filename: "{app}\output"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\Transcriptor.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Transcriptor.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Se borran logs y checkpoints temporales; las transcripciones en output\ se conservan.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\models"
Type: files; Name: "{app}\.env"
