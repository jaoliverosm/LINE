#!/usr/bin/env python3
"""
start.py - Script de inicio multiplataforma para LINE - Auditor Medico Digital
Este script reemplaza start.bat y funciona en Windows, Linux y macOS.

Uso:
    python start.py
    python start.py --no-browser  # No abrir navegador automáticamente
    python start.py --port 8080  # Usar puerto diferente
"""
import os
import sys
import subprocess
import platform
import shutil
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

# Configuración
BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / "venv"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
DB_FILE = BASE_DIR / "linea.db"
DATASET_FILE = BASE_DIR / "data" / "dataset_maestro.csv"
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"
LOG_FILE = BASE_DIR / "start_debug.log"
DEFAULT_PORT = 8000

# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(message):
    """Escribe mensaje al log y a consola"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def print_header():
    """Imprime encabezado del script"""
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}  LINE - Auditor Medico Digital{Colors.ENDC}")
    print(f"{Colors.HEADER}  Health & Life IPS SAS  |  Capstone SIC 2025{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print()
    log("INICIO del script start.py")

def find_python():
    """Busca Python instalado en el sistema"""
    log("Buscando Python instalado...")
    
    # Intentar con python, python3, py
    python_names = ["python", "python3", "py"]
    
    for python_name in python_names:
        try:
            result = subprocess.run(
                [python_name, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                log(f"Python encontrado: {python_name} ({version})")
                print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} {python_name} ({version})")
                return python_name
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    log("ERROR: Python no encontrado")
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} Python no encontrado")
    print("  Instale desde: https://www.python.org/downloads/")
    return None

def check_models():
    """Verifica que los archivos del modelo existan"""
    log("Verificando archivos del modelo...")
    print(f"{Colors.OKCYAN}[2/6]{Colors.ENDC} Verificando archivos del modelo...")
    
    models_dir = BASE_DIR / "models"
    cnn_model = models_dir / "auditor_medico_cnn.keras"
    artifacts = models_dir / "artefactos_preprocesamiento.pkl"
    
    if cnn_model.exists():
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Modelo CNN encontrado")
        log("Modelo CNN encontrado")
    else:
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} Modelo CNN no encontrado")
        log("WARN: Modelo CNN no encontrado")
    
    if artifacts.exists():
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Artefactos de preprocesamiento encontrados")
        log("Artefactos encontrados")
    else:
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} Artefactos no encontrados")
        log("WARN: Artefactos no encontrados")

def setup_venv(python_cmd):
    """Configura o crea el entorno virtual"""
    log("Configurando entorno virtual...")
    print(f"{Colors.OKCYAN}[3/6]{Colors.ENDC} Configurando entorno virtual...")
    
    venv_python = VENV_DIR / "Scripts" / "python.exe" if platform.system() == "Windows" else VENV_DIR / "bin" / "python"
    
    if venv_python.exists():
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Entorno virtual encontrado")
        log("Entorno virtual encontrado")
        return str(venv_python)
    
    print("  Creando entorno virtual...")
    log("Creando entorno virtual...")
    
    try:
        subprocess.run(
            [python_cmd, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Entorno virtual creado")
        log("Entorno virtual creado")
        return str(venv_python)
    except subprocess.CalledProcessError as e:
        print(f"  {Colors.FAIL}[ERROR]{Colors.ENDC} Fallo al crear entorno virtual")
        log(f"ERROR: Fallo al crear venv - {e}")
        return None

def install_dependencies(venv_python):
    """Instala dependencias desde requirements.txt"""
    log("Instalando dependencias...")
    print(f"{Colors.OKCYAN}[4/6]{Colors.ENDC} Instalando dependencias...")
    
    if not REQUIREMENTS_FILE.exists():
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} requirements.txt no encontrado")
        log("WARN: requirements.txt no encontrado")
        return
    
    pip_cmd = [venv_python, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)]
    
    try:
        subprocess.run(pip_cmd, check=True, capture_output=True)
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Dependencias instaladas")
        log("Dependencias instaladas")
    except subprocess.CalledProcessError as e:
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} Algunas dependencias fallaron")
        log(f"WARN: Fallo en pip install - {e}")

def setup_database(venv_python):
    """Crea la base de datos si no existe"""
    log("Verificando base de datos...")
    print(f"{Colors.OKCYAN}[5/6]{Colors.ENDC} Verificando base de datos...")
    
    if DB_FILE.exists():
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Base de datos existente")
        log("Base de datos existente")
        return
    
    if not DATASET_FILE.exists():
        print(f"  {Colors.FAIL}[ERROR]{Colors.ENDC} dataset_maestro.csv no encontrado")
        log("ERROR: dataset_maestro.csv no encontrado")
        print("  Coloque el archivo dataset_maestro.csv en la carpeta data/")
        return False
    
    print("  Creando base de datos SQLite desde dataset maestro...")
    log("Creando base de datos...")
    
    try:
        subprocess.run(
            [venv_python, str(BASE_DIR / "build_db.py")],
            check=True,
            capture_output=True
        )
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Base de datos creada")
        log("Base de datos creada")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  {Colors.FAIL}[ERROR]{Colors.ENDC} Fallo al crear base de datos")
        log(f"ERROR: Fallo build_db.py - {e}")
        return False

def setup_env_file():
    """Configura archivo .env"""
    log("Verificando configuración .env...")
    print(f"  Verificando configuración .env...")
    
    if ENV_FILE.exists():
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} .env ya existe")
        log(".env ya existe")
        return
    
    if ENV_EXAMPLE_FILE.exists():
        print("  Creando .env desde .env.example...")
        log("Creando .env desde .env.example...")
        shutil.copy(ENV_EXAMPLE_FILE, ENV_FILE)
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} .env creado desde .env.example")
        log(".env creado desde .env.example")
        print("    Por favor revise .env y configure las variables necesarias")
    else:
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} No existe .env.example. Creando .env vacío...")
        log("WARN: No existe .env.example, creando .env vacío")
        with open(ENV_FILE, "w") as f:
            f.write("# LINE - Auditor Medico Digital\n")
            f.write("# Variables de entorno\n")
            f.write("NVIDIA_API_KEY=tu_api_key_aqui\n")
            f.write("NVIDIA_MODEL=nvidia/nemotron-3-nano-8b-v1\n")
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} .env creado vacío. Por favor configure NVIDIA_API_KEY")
        log(".env creado vacío")

def check_nvidia_api_key():
    """Verifica si la API key de NVIDIA está configurada"""
    log("Verificando NVIDIA_API_KEY...")
    
    nvidia_key = os.environ.get("NVIDIA_API_KEY")
    
    if not nvidia_key and ENV_FILE.exists():
        # Leer desde .env
        try:
            with open(ENV_FILE, "r") as f:
                for line in f:
                    if line.startswith("NVIDIA_API_KEY="):
                        nvidia_key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    
    if nvidia_key and nvidia_key != "tu_api_key_aqui":
        print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} NVIDIA_API_KEY configurada para Nemotron")
        log("NVIDIA_API_KEY configurada")
    else:
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} NVIDIA_API_KEY no configurada. Nemotron no estará disponible.")
        log("WARN: NVIDIA_API_KEY no configurada")

def kill_port_process(port):
    """Mata procesos usando el puerto especificado"""
    log(f"Verificando puerto {port}...")
    
    try:
        if platform.system() == "Windows":
            # Windows: usar netstat y taskkill
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.split('\n'):
                if f":{port}" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                            log(f"Proceso {pid} en puerto {port} terminado")
                        except subprocess.CalledProcessError:
                            pass
        else:
            # Linux/macOS: usar lsof y kill
            try:
                result = subprocess.run(
                    ["lsof", "-t", "-i", f":{port}"],
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    for pid in result.stdout.split():
                        try:
                            subprocess.run(["kill", "-9", pid], capture_output=True)
                            log(f"Proceso {pid} en puerto {port} terminado")
                        except subprocess.CalledProcessError:
                            pass
            except FileNotFoundError:
                pass
    except Exception as e:
        log(f"Error al verificar puerto {port}: {e}")

def start_server(venv_python, port=DEFAULT_PORT):
    """Inicia el servidor FastAPI"""
    log(f"Iniciando servidor en puerto {port}...")
    print(f"{Colors.OKCYAN}[6/6]{Colors.ENDC} Iniciando backend...")
    
    # Matar procesos en el puerto
    kill_port_process(port)
    time.sleep(1)
    
    # Iniciar servidor en proceso separado
    server_cmd = [venv_python, str(BASE_DIR / "server.py")]
    
    try:
        if platform.system() == "Windows":
            # Windows: iniciar en una consola nueva (equivalente a `start`).
            # Se pasa la lista de argumentos SIN shell para que las rutas con
            # espacios (ej. "Final_version_ HL") no rompan el comando.
            subprocess.Popen(
                server_cmd,
                cwd=str(BASE_DIR),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # Linux/macOS: iniciar en background
            subprocess.Popen(
                server_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(BASE_DIR),
            )
        
        log("Servidor iniciado")
        print(f"  Iniciando FastAPI en http://localhost:{port}...")
        
        # Esperar a que el servidor responda
        print("  Esperando servidor...")
        for i in range(15):
            time.sleep(1)
            try:
                urlopen(f"http://localhost:{port}/api/health", timeout=2)
                print(f"  {Colors.OKGREEN}[OK]{Colors.ENDC} Servidor respondiendo en http://localhost:{port}")
                log(f"Servidor listo en puerto {port}")
                return True
            except URLError:
                continue
        
        print(f"  {Colors.WARNING}[WARN]{Colors.ENDC} El servidor aún no responde. Revise la ventana LINE-Backend.")
        log("WARN: Servidor no responde")
        return False
        
    except Exception as e:
        print(f"  {Colors.FAIL}[ERROR]{Colors.ENDC} Fallo al iniciar servidor: {e}")
        log(f"ERROR: Fallo al iniciar servidor - {e}")
        return False

def open_frontend(open_browser=True):
    """Abre el frontend en el navegador"""
    frontend_file = BASE_DIR / "frontend" / "index.html"
    
    if not frontend_file.exists():
        print(f"  {Colors.FAIL}[ERROR]{Colors.ENDC} frontend/index.html no encontrado")
        log("ERROR: frontend/index.html no encontrado")
        return
    
    if open_browser:
        log("Abriendo frontend...")
        print("  Abriendo frontend...")
        webbrowser.open(f"file:///{frontend_file}")
    else:
        print(f"  Frontend disponible en: file:///{frontend_file}")

def print_summary(port=DEFAULT_PORT):
    """Imprime resumen final"""
    print()
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}  LINE iniciado exitosamente{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print(f"  Backend:  http://localhost:{port}")
    print(f"  Frontend: frontend/index.html")
    print(f"  API Docs: http://localhost:{port}/docs")
    print(f"  Log diag: start_debug.log")
    print()
    print(f"  Para detener, cierre la ventana LINE-Backend")
    print(f"  o presione Ctrl+C aquí.")
    print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
    print()
    log("Script completado exitosamente")

def main():
    """Función principal"""
    # Parse argumentos
    open_browser = "--no-browser" not in sys.argv
    port = DEFAULT_PORT
    
    for arg in sys.argv:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except ValueError:
                pass
    
    # Inicializar log
    log("="*60)
    log("INICIO del script start.py")
    
    print_header()
    
    # 1. Verificar Python
    python_cmd = find_python()
    if not python_cmd:
        sys.exit(1)
    
    # 2. Verificar modelos
    check_models()
    
    # 3. Configurar entorno virtual
    venv_python = setup_venv(python_cmd)
    if not venv_python:
        sys.exit(1)
    
    # 4. Instalar dependencias
    install_dependencies(venv_python)
    
    # 5. Configurar base de datos
    if not setup_database(venv_python):
        sys.exit(1)
    
    # 6. Configurar .env
    setup_env_file()
    check_nvidia_api_key()
    
    # 7. Iniciar servidor
    if not start_server(venv_python, port):
        sys.exit(1)
    
    # 8. Abrir frontend
    open_frontend(open_browser)
    
    # Resumen
    print_summary(port)
    
    # Mantener script corriendo
    try:
        input("Presione Enter para finalizar... (El servidor seguirá corriendo)")
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario")
        log("Interrumpido por usuario")

if __name__ == "__main__":
    main()
