@echo off
title LINE - Auditor Medico Digital
setlocal enabledelayedexpansion

:: Redirigir TODO el output a un log de diagnostico
set "LOG_FILE=%~dp0start_debug.log"
echo [%date% %time%] INICIO > "%LOG_FILE%"

cls
echo ============================================
echo   LINE - Auditor Medico Digital
echo   Health ^& Life IPS SAS  ^|  Capstone SIC 2025
echo ============================================
echo.
echo  ► Los mensajes se estan guardando en: start_debug.log
echo.
cd /d "%~dp0"
echo [%date% %time%] Directorio: %cd% >> "%LOG_FILE%"

:: ── 1. Verificar Python ────────────────────────────────────────
echo [1/6] Verificando Python...
echo [%date% %time%] Buscando Python... >> "%LOG_FILE%"

:: Intentar con python, py -3, y python3
set "PYTHON_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    echo   [OK] python encontrado >> "%LOG_FILE%"
    goto :py_found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    echo   [OK] py -3 encontrado >> "%LOG_FILE%"
    goto :py_found
)

where python3 >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    echo   [OK] python3 encontrado >> "%LOG_FILE%"
    goto :py_found
)

echo [ERROR] Python no encontrado.
echo        Busque: python, py -3, python3
echo        Instale desde: https://www.python.org/downloads/
echo [%date% %time%] ERROR: Python no encontrado >> "%LOG_FILE%"
pause
exit /b 1

:py_found

:: Verificar que realmente funcione
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] %PYTHON_CMD% no responde correctamente.
    pause
    exit /b 1
)

:: Mostrar version
for /f "delims=" %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "pyfull=%%v"
echo   [OK] %pyfull%
echo [%date% %time%] %pyfull% >> "%LOG_FILE%"

:: ── 2. Verificar archivos del modelo ───────────────────────────
echo [2/6] Verificando archivos del modelo...
echo [%date% %time%] Verificando modelos... >> "%LOG_FILE%"

if exist "models\auditor_medico_cnn.keras" (
    echo   [OK] Modelo CNN encontrado
) else (
    echo   [WARN] Modelo CNN no encontrado: models\auditor_medico_cnn.keras
    echo         La auditoria funcionara solo con reglas heuristicas.
    echo [%date% %time%] WARN: Modelo CNN no encontrado >> "%LOG_FILE%"
)

if exist "models\artefactos_preprocesamiento.pkl" (
    echo   [OK] Artefactos de preprocesamiento encontrados
) else (
    echo   [WARN] Artefactos de preprocesamiento no encontrados
    echo [%date% %time%] WARN: Artefactos no encontrados >> "%LOG_FILE%"
)

:: ── 3. Entorno virtual ─────────────────────────────────────────
echo [3/6] Configurando entorno virtual...
echo [%date% %time%] Configurando venv... >> "%LOG_FILE%"

if exist "venv\Scripts\python.exe" (
    echo   [OK] Entorno virtual encontrado. Activando...
    call venv\Scripts\activate.bat
) else (
    echo   Creando entorno virtual...
    %PYTHON_CMD% -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo al crear entorno virtual
        echo [%date% %time%] ERROR: Fallo al crear venv >> "%LOG_FILE%"
        pause
        exit /b 1
    )
    echo   [OK] Entorno virtual creado. Activando...
    call venv\Scripts\activate.bat
)

:: ── 4. Instalar dependencias ───────────────────────────────────
echo [4/6] Instalando dependencias...
echo [%date% %time%] Instalando dependencias... >> "%LOG_FILE%"
pip install -r requirements.txt -q
if !errorlevel! neq 0 (
    echo   [WARN] Algunas dependencias fallaron. Verifique requirements.txt
    echo [%date% %time%] WARN: Fallo en pip install >> "%LOG_FILE%"
) else (
    echo   [OK] Dependencias instaladas
)

:: ── 5. Crear base de datos ─────────────────────────────────────
echo [5/6] Verificando base de datos...
echo [%date% %time%] Verificando BD... >> "%LOG_FILE%"

if not exist "linea.db" (
    echo   Creando base de datos SQLite desde dataset maestro...
    if not exist "data\dataset_maestro.csv" (
        echo [ERROR] No se encuentra data\dataset_maestro.csv
        echo        Coloque el archivo dataset_maestro.csv en la carpeta data/
        echo [%date% %time%] ERROR: dataset_maestro.csv no encontrado >> "%LOG_FILE%"
        pause
        exit /b 1
    )
    python build_db.py
    if !errorlevel! neq 0 (
        echo [ERROR] Fallo al crear linea.db
        echo [%date% %time%] ERROR: Fallo build_db.py >> "%LOG_FILE%"
        pause
        exit /b 1
    )
    echo   [OK] Base de datos creada
) else (
    echo   [OK] Base de datos existente
)

:: ── 5b. Configurar archivo .env ─────────────────────────────────────
echo   Verificando configuracion .env...
if not exist ".env" (
    if exist ".env.example" (
        echo   Creando .env desde .env.example...
        copy ".env.example" ".env" >nul
        echo   [OK] .env creado desde .env.example
        echo         Por favor revise .env y configure las variables necesarias
    ) else (
        echo   [WARN] No existe .env.example. Creando .env vacio...
        echo # LINE - Auditor Medico Digital > .env
        echo # Variables de entorno >> .env
        echo NVIDIA_API_KEY=tu_api_key_aqui >> .env
        echo NVIDIA_MODEL=nvidia/nemotron-3-nano-8b-v1 >> .env
        echo   [WARN] .env creado vacio. Por favor configure NVIDIA_API_KEY
    )
) else (
    echo   [OK] .env ya existe
)

:: ── 5c. Verificar API Key de NVIDIA (Nemotron) ───────────────────
:: Leer NVIDIA_API_KEY desde .env si no está definida en entorno
if not defined NVIDIA_API_KEY (
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="NVIDIA_API_KEY" set "NVIDIA_API_KEY=%%b"
    )
)
if defined NVIDIA_API_KEY (
    if "%NVIDIA_API_KEY%"=="tu_api_key_aqui" (
        echo   [WARN] NVIDIA_API_KEY no configurada. Nemotron no estara disponible.
    ) else (
        echo   [OK] NVIDIA_API_KEY configurada para Nemotron
    )
) else (
    echo   [WARN] NVIDIA_API_KEY no encontrada. Nemotron no estara disponible.
)

:: ── 6. Iniciar servidor ────────────────────────────────────────
echo [6/6] Iniciando backend...
echo [%date% %time%] Iniciando servidor... >> "%LOG_FILE%"

:: Verificar si el puerto 8000 ya esta en uso
netstat -ano | findstr ":8000 " >nul 2>&1
if !errorlevel! equ 0 (
    echo   [WARN] Puerto 8000 en uso. Cerrando proceso anterior...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do (
        if not "%%a"=="" (
            taskkill /f /pid %%a >nul 2>&1
        )
    )
    timeout /t 2 /nobreak >nul
    echo   [OK] Puerto 8000 liberado
)

:: Iniciar servidor en ventana separada
echo   Iniciando FastAPI en http://localhost:8000 ...
start "LINE-Backend" cmd /c "title LINE-Backend && call venv\Scripts\activate.bat && python server.py"

:: Esperar a que el servidor responda
echo   Esperando servidor...
set "SERVER_READY="
for /l %%i in (1,1,15) do (
    timeout /t 1 /nobreak >nul
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" >nul 2>&1
    if !errorlevel! equ 0 (
        set "SERVER_READY=1"
        goto :server_ready
    )
)
:server_ready

if defined SERVER_READY (
    echo   [OK] Servidor respondiendo en http://localhost:8000
    echo [%date% %time%] Servidor listo >> "%LOG_FILE%"
) else (
    echo   [WARN] El servidor aun no responde. Revise la ventana LINE-Backend.
    echo [%date% %time%] WARN: Servidor no responde >> "%LOG_FILE%"
)

:: Abrir frontend en el navegador
echo   Abriendo frontend...
start "" "frontend\index.html"

:: ── Resumen Final ──────────────────────────────────────────────
echo.
echo ============================================
echo   LINE iniciado exitosamente
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: frontend\index.html
echo   API Docs: http://localhost:8000/docs
echo   Log diag: start_debug.log
echo.
echo   Para detener, cierre la ventana LINE-Backend
echo   o presione Ctrl+C aqui.
echo ============================================
echo.
echo Presione cualquier tecla para finalizar...
echo (El servidor seguira corriendo en su ventana)
pause >nul
exit /b 0
