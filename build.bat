@echo off
rem Build hry Chuj (PyInstaller, onedir) -> dist\Chuj\Chuj.exe
rem Spustit dvojklikom alebo z terminalu: build.bat
rem
rem Nezavisi od PC ani cesty k projektu: ak .venv chyba (napr. po klonovani
rem z githubu na inom PC), vytvori sa novy zo systemoveho "python" (musi
rem byt v PATH) a nainstaluju sa zavislosti z requirements.txt. Ak .venv uz
rem existuje, zavislosti sa len doinstaluju/overia (rychly no-op krok).
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo .venv neexistuje, vytvaram novy virtualny prostredie...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo Nepodarilo sa vytvorit .venv - over, ze je Python nainstalovany a v PATH.
        pause
        exit /b 1
    )
)
set PY=.venv\Scripts\python.exe

%PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Instalacia zavislosti z requirements.txt zlyhala.
    pause
    exit /b 1
)
%PY% -m pip show pyinstaller >nul 2>&1 || %PY% -m pip install pyinstaller
%PY% -m PyInstaller Chuj.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo BUILD ZLYHAL
    pause
    exit /b 1
)
echo.
echo Hotovo: dist\Chuj\Chuj.exe
echo Na rozdanie zbal cely priecinok dist\Chuj do zipu.
pause
