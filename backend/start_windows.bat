:: This method is not recommended, and we recommend you use the `start.sh` file with WSL instead.
@echo off
SETLOCAL DISABLEDELAYEDEXPANSION

:: Get the directory of the current script
SET "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%" || exit /b

:: Define the local virtual environment binary directory
SET "VENV_BIN=%SCRIPT_DIR%.venv\Scripts"
SET "PYTHON_CMD=python"
IF EXIST "%VENV_BIN%\python.exe" SET "PYTHON_CMD=%VENV_BIN%\python.exe"

"%PYTHON_CMD%" --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Python was not found. Install Python or create backend\.venv first.
    exit /b 1
)

:: Add conditional Playwright browser installation using venv tools
IF /I "%WEB_LOADER_ENGINE%" == "playwright" (
    IF "%PLAYWRIGHT_WS_URL%" == "" (
        echo Installing Playwright browsers...
        IF EXIST "%VENV_BIN%\playwright.exe" (
            "%VENV_BIN%\playwright.exe" install chromium
            "%VENV_BIN%\playwright.exe" install-deps chromium
        ) ELSE (
            playwright install chromium
            playwright install-deps chromium
        )
    )

    "%PYTHON_CMD%" -c "import nltk; nltk.download('punkt_tab')"
)

SET "KEY_FILE=.webui_secret_key"
IF NOT "%WEBUI_SECRET_KEY_FILE%" == "" (
    SET "KEY_FILE=%WEBUI_SECRET_KEY_FILE%"
)

IF "%PORT%"=="" SET PORT=8080
IF "%HOST%"=="" SET HOST=0.0.0.0
IF "%FORWARDED_ALLOW_IPS%"=="" SET "FORWARDED_ALLOW_IPS=*"
SET "WEBUI_SECRET_KEY=%WEBUI_SECRET_KEY%"
SET "WEBUI_JWT_SECRET_KEY=%WEBUI_JWT_SECRET_KEY%"
IF "%WEBUI_SECRET_KEY_LENGTH%" == "" (
    SET "WEBUI_SECRET_KEY_LENGTH=24"
)

:: Check if WEBUI_SECRET_KEY and WEBUI_JWT_SECRET_KEY are not set
IF "%WEBUI_SECRET_KEY% %WEBUI_JWT_SECRET_KEY%" == " " (
    echo Loading WEBUI_SECRET_KEY from file, not provided as an environment variable.

    IF NOT EXIST "%KEY_FILE%" (
        echo Generating WEBUI_SECRET_KEY
        :: Generate cryptographic randomness; exclusive creation preserves an existing key.
        "%PYTHON_CMD%" -c "import secrets,sys; n=int(sys.argv[2]); assert n>0, 'WEBUI_SECRET_KEY_LENGTH must be positive'; f=open(sys.argv[1], 'x', encoding='ascii'); f.write(secrets.token_urlsafe(n)); f.close()" "%KEY_FILE%" "%WEBUI_SECRET_KEY_LENGTH%"
        IF ERRORLEVEL 1 (
            echo Could not create WEBUI_SECRET_KEY.
            exit /b 1
        )
        echo WEBUI_SECRET_KEY generated
    )

    echo Loading WEBUI_SECRET_KEY from %KEY_FILE%
    SET /p WEBUI_SECRET_KEY=<"%KEY_FILE%"
)

:: Prefer the project environment and retain support for an activated environment on PATH.
SET "WEBUI_SECRET_KEY=%WEBUI_SECRET_KEY%"
IF "%UVICORN_WORKERS%"=="" SET UVICORN_WORKERS=1

"%PYTHON_CMD%" -m uvicorn open_webui.main:app --host "%HOST%" --port "%PORT%" --forwarded-allow-ips "%FORWARDED_ALLOW_IPS%" --workers %UVICORN_WORKERS% --ws auto
