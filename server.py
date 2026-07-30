"""
server.py
=========
Backend FastAPI para LINE - Auditor Medico Digital.
  - Carga modelo .keras + artefactos .pkl
  - Endpoint Apitude ADRES (verificacion BDUA)
  - Analisis de prefactura CSV con cruce HC vs PF
  - Modelo dual: CNN local + NVIDIA Nemotron externo
  - SQLite linea.db como fuente de datos

Ejecutar: uvicorn server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
import sys, json, sqlite3, time, warnings, io, os as _os, logging
from pathlib import Path
from typing import Optional

import numpy as np, pandas as pd, requests
from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# PDF text extraction (usado cuando el toggle esta en Nemotron)
try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pypdf no instalado. No se podrán procesar PDFs.")

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

# Load environment variables from .env file
load_dotenv(BASE / ".env")

from preprocesamiento import cargar_artefactos, predecir_inconsistencia
from backend.adres_scraper import consultar_afiliacion
from backend.xgboost_inferencia import modelo_xgboost_disponible, cargar_modelo_xgboost, predecir_xgboost

warnings.filterwarnings("ignore")

# ── Config ─────────────────────────────────────────────────────────
# ── CONFIGURACIÓN DE BASE DE DATOS ─────────────────────────────────────
# MOTOR DE BASE DE DATOS ACTUAL: SQLite (por defecto para desarrollo)
#
# Para migrar a SQL Server:
# 1. Cambiar DB_ENGINE en .env a "sqlserver"
# 2. Configurar DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD en .env
# 3. Modificar la función _query() para usar pyodbc o sqlalchemy
# 4. Reemplazar sqlite3.connect() con la conexión a SQL Server
#
# Para migrar a MySQL:
# 1. Cambiar DB_ENGINE en .env a "mysql"
# 2. Configurar DB_HOST, DB_PORT, DB_DATABASE, DB_USER, DB_PASSWORD en .env
# 3. Modificar la función _query() para usar mysql-connector-python o sqlalchemy
# 4. Reemplazar sqlite3.connect() con la conexión a MySQL
#
# RUTA DE LA BASE DE DATOS:
# - SQLite: archivo local (linea.db)
# - SQL Server: servidor remoto (configurar en .env)
# - MySQL: servidor remoto (configurar en .env)
DB_PATH = BASE / "linea.db"
MODEL_PATH = BASE / "models" / "auditor_medico_cnn.keras"

# NVIDIA Nemotron config
# La API key se lee de variable de entorno con fallback a la key proporcionada
NVIDIA_API_KEY = _os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Nombre del modelo: configurable via variable de entorno
NVIDIA_MODEL = _os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-nano-30b-a3b")

# ── RUTAS DE ARCHIVOS DE DATOS (CAMBIAR EN PRODUCCIÓN) ────────────────
# Estas rutas apuntan a archivos CSV externos con datos de prueba.
# En producción, cambiar estas rutas a las ubicaciones reales de los datos.
#
# HC_DETALLE_PATH: Historia Clínica Detalle
# - Actualmente: CSV en carpeta data/ (datos de prueba del proyecto)
# - Producción: Cambiar a ruta real del archivo HC o usar tabla de BD
#
# PF_ORIGINAL_PATH: Prefactura Original (referencia)
# - Actualmente: CSV en carpeta data/ (datos de prueba del proyecto)
# - Producción: Cambiar a ruta real o eliminar si no se usa
HC_DETALLE_PATH = BASE / "data" / "03_historia_clinica_detalle.csv"
PF_ORIGINAL_PATH = BASE / "data" / "04_prefactura.csv"

# ── Logging estructurado (ISO 27001 A.8.15) ────────────────────────
log_level = _os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("line-server")

app = FastAPI(title="LINE - Auditor Medico Digital", version="2.0")

# ── CORS restringido (ISO 27001 A.8.21) ───────────────────────────
CORS_ORIGINS = _os.environ.get("CORS_ORIGINS", "*")  # "*" por defecto para desarrollo
if CORS_ORIGINS == "*":
    origins = ["*"]
else:
    origins = [o.strip() for o in CORS_ORIGINS.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

# ── Security Headers Middleware (ISO 27001 A.8.21) ─────────────────
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://fonts.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' http://127.0.0.1:8000; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# ── Estado del servidor ────────────────────────────────────────────
modelo = None
modelo_cargado = False
xgboost_cargado = False
hc_detalle_df: Optional[pd.DataFrame] = None
prefactura_ref_df: Optional[pd.DataFrame] = None


@app.on_event("startup")
def startup():
    global modelo, modelo_cargado, xgboost_cargado, hc_detalle_df, prefactura_ref_df

    # 1. Cargar modelo CNN
    try:
        from tensorflow import keras
        modelo = keras.models.load_model(str(MODEL_PATH), compile=False)
        modelo_cargado = True
        logger.info("Modelo auditor_medico_cnn.keras cargado")
    except Exception as e:
        modelo_cargado = False
        logger.warning(f"Modelo CNN NO cargado: {e}")

    # 2. Cargar artefactos de preprocesamiento
    try:
        _ = cargar_artefactos()
        logger.info("Artefactos preprocesamiento cargados")
    except Exception as e:
        logger.warning(f"Artefactos NO cargados: {e}")

    # 2b. Cargar modelo XGBoost
    global xgboost_cargado
    if modelo_xgboost_disponible():
        try:
            cargar_modelo_xgboost()
            xgboost_cargado = True
            logger.info("Modelo XGBoost cargado")
        except Exception as e:
            xgboost_cargado = False
            logger.warning(f"Modelo XGBoost NO cargado: {e}")
    else:
        xgboost_cargado = False
        logger.info("Modelo XGBoost no encontrado (ejecute 01_entrenamiento_xgboost.py primero)")

    # 3. Cargar HC detalle (historia clinica) desde CSV original
    try:
        if HC_DETALLE_PATH.exists():
            hc_detalle_df = pd.read_csv(str(HC_DETALLE_PATH))
            logger.info(f"HC detalle cargado: {len(hc_detalle_df)} registros")
        else:
            logger.warning(f"HC detalle no encontrado en {HC_DETALLE_PATH}. Usando BD local.")
            # Fallback: intentar cargar desde linea.db si existe tabla
            try:
                rows = _query("SELECT * FROM historia_clinica_detalle LIMIT 1")
                if rows:
                    all_rows = _query("SELECT * FROM historia_clinica_detalle")
                    hc_detalle_df = pd.DataFrame(all_rows)
                    logger.info(f"HC detalle cargado desde BD: {len(hc_detalle_df)} registros")
                else:
                    hc_detalle_df = pd.DataFrame()
            except Exception:
                hc_detalle_df = pd.DataFrame()
                logger.warning("HC detalle no disponible. El analisis de prefactura usara solo reglas.")
    except Exception as e:
        hc_detalle_df = pd.DataFrame()
        logger.warning(f"Error cargando HC detalle: {e}")


# ── Helpers SQLite ─────────────────────────────────────────────────
# ── FUNCIÓN DE CONSULTA A BASE DE DATOS ────────────────────────────────
# Esta función actualmente usa SQLite.
# Para migrar a SQL Server o MySQL, modificar esta función para usar:
# - pyodbc (SQL Server)
# - mysql-connector-python (MySQL)
# - sqlalchemy (genérico, soporta múltiples motores)
#
# Ejemplo con sqlalchemy:
# from sqlalchemy import create_engine
# engine = create_engine(f"{DB_ENGINE}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_DATABASE}")
# df = pd.read_sql_query(sql, engine)
def _query(sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _row(sql: str, params=()) -> Optional[dict]:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _s(v) -> str:
    """Convierte None/nan a string vacio para JSON limpio."""
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v)


def _num(v, default: float = 0.0) -> float:
    """
    Convierte a float de forma segura: None, NaN, celdas vacias o texto
    no numerico -> default. Evita que un NaN llegue a la respuesta JSON
    (FastAPI serializa con allow_nan=False y devolveria un 500).
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if pd.isna(f) else f


def _normalizar_eps(eps: str) -> str:
    """
    Normaliza el nombre de la EPS para comparaciones.
    Elimina sufijos como 'EPS', 'EPS-S', etc. y palabras comunes.
    Ejemplo: 'Salud Total EPS' -> 'SALUD TOTAL'
    Ejemplo: 'LABORAL C SALUD TOTAL ENTIDAD PROMOTORA DE SALUD DEL REGIMEN' -> 'SALUD TOTAL'
    """
    if not eps:
        return ""
    eps_upper = eps.upper().strip()
    
    # Eliminar palabras comunes que no son parte del nombre de la EPS
    palabras_a_eliminar = [
        'EPS', 'EPS-S', ' - EPS', '-EPS',
        'ENTIDAD PROMOTORA DE SALUD', 'ENTIDAD PROMOTORA',
        'DEL REGIMEN', 'DE SALUD', 'S.A.', 'S.A', 'SAS',
        'LABORAL C', 'LABORAL', 'COOMEVA', 'SALUDCOOP'
    ]
    
    for palabra in palabras_a_eliminar:
        eps_upper = eps_upper.replace(palabra, '').strip()
    
    # Eliminar espacios múltiples
    eps_upper = ' '.join(eps_upper.split())
    
    return eps_upper


def _normalizar_documento(doc: str) -> str:
    """
    Normaliza el numero de documento eliminando espacios y caracteres no numericos.
    """
    if not doc:
        return ""
    return ''.join(filter(str.isdigit, doc.strip()))


def _normalizar_texto(s: str) -> str:
    """
    Normaliza texto para comparaciones flexibles:
    mayusculas, sin tildes, sin espacios multiples.
    """
    import unicodedata
    if not s:
        return ""
    s = s.upper().strip()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    s = ' '.join(s.split())
    return s


def _extraer_datos_adres(adres_data: dict) -> dict:
    """
    Extrae campos relevantes de ADRES sin importar la estructura
    (data anidada o campos planos).
    """
    result = {"nombres": "", "apellidos": "", "eps": "", "regimen": ""}
    if not adres_data:
        return result
    if "data" in adres_data and adres_data["data"]:
        d = adres_data["data"]
        result["nombres"] = _s(d.get("nombres", ""))
        result["apellidos"] = _s(d.get("apellidos", ""))
        estado = d.get("estado_afiliacion", {}) or {}
        result["eps"] = _s(estado.get("entidad_normalizada", "") or estado.get("entidad", ""))
        result["regimen"] = _s(estado.get("regimen", ""))
    else:
        result["nombres"] = _s(adres_data.get("nombres", ""))
        result["apellidos"] = _s(adres_data.get("apellidos", ""))
        result["eps"] = _s(adres_data.get("eps", ""))
        result["regimen"] = _s(adres_data.get("regimen", ""))
    return result


def _validar_cruce_adres(adres_data: dict, form_data: dict) -> dict:
    """
    Cruza los datos del formulario contra los datos reales de ADRES/BDUA.
    Compara: nombres, apellidos, EPS, regimen con flexibilidad.

    Args:
        adres_data: Respuesta del scraper ADRES
        form_data: Dict con nombres, apellidos, eps, tipo_afiliacion del formulario

    Returns:
        dict con:
          - campos: lista de {campo, formulario, adres, coincide, detalle}
          - n_discrepancias: conteo
          - validacion_pasa: bool (True = sin discrepancias graves)
          - conclusion: texto resumen
    """
    adres = _extraer_datos_adres(adres_data)
    if not adres["nombres"] and not adres["apellidos"]:
        return {
            "campos": [],
            "n_discrepancias": 0,
            "discrepancias_graves": 0,
            "validacion_pasa": True,
            "conclusion": "ADRES no devolvió datos personales para cruzar. No se puede validar.",
        }

    nombre_form = _s(form_data.get("nombres", ""))
    apellido_form = _s(form_data.get("apellidos", ""))
    eps_form = _s(form_data.get("eps", ""))
    regimen_form = _s(form_data.get("tipo_afiliacion", ""))

    campos = []
    discrepancias_graves = 0
    discrepancias_leves = 0

    # ── 1. Validar nombres completos ──
    completo_form = _normalizar_texto(f"{nombre_form} {apellido_form}")
    completo_adres = _normalizar_texto(f"{adres['nombres']} {adres['apellidos']}")

    nombres_coinciden = False
    detalle_nombres = ""
    if completo_form and completo_adres:
        if completo_form == completo_adres:
            nombres_coinciden = True
            detalle_nombres = "Coincidencia exacta"
        else:
            # Comparación flexible: primer nombre + primer apellido
            partes_f = completo_form.split()
            partes_a = completo_adres.split()
            pn_f = partes_f[0] if partes_f else ""
            pa_f = partes_f[-1] if len(partes_f) > 1 else ""
            pn_a = partes_a[0] if partes_a else ""
            pa_a = partes_a[-1] if len(partes_a) > 1 else ""

            if pn_f == pn_a and pa_f == pa_a:
                nombres_coinciden = True
                detalle_nombres = f"Coincidencia parcial (primer nombre '{pn_f}' y apellido '{pa_f}' coinciden)"
            elif completo_form in completo_adres or completo_adres in completo_form:
                nombres_coinciden = True
                detalle_nombres = "Coincidencia parcial (un nombre contiene al otro)"
            else:
                detalle_nombres = f"NO coinciden: Form='{completo_form}' vs ADRES='{completo_adres}'"
    else:
        detalle_nombres = "Faltan datos del formulario o ADRES para comparar nombres"
        nombres_coinciden = True  # No se puede determinar, no penalizar

    if not nombres_coinciden:
        discrepancias_graves += 1

    campos.append({
        "campo": "nombres_completos",
        "formulario": f"{nombre_form} {apellido_form}",
        "adres": f"{adres['nombres']} {adres['apellidos']}",
        "coincide": nombres_coinciden,
        "detalle": detalle_nombres,
    })

    # ── 2. Validar EPS ──
    eps_form_norm = _normalizar_eps(eps_form)
    eps_adres_norm = _normalizar_eps(adres["eps"])

    eps_coincide = False
    detalle_eps = ""
    if eps_form_norm and eps_adres_norm:
        if eps_form_norm == eps_adres_norm:
            eps_coincide = True
            detalle_eps = "Coincidencia exacta"
        elif eps_form_norm in eps_adres_norm or eps_adres_norm in eps_form_norm:
            eps_coincide = True
            detalle_eps = f"Coincidencia parcial ('{eps_form_norm}' ≈ '{eps_adres_norm}')"
        else:
            detalle_eps = f"NO coinciden: Form='{eps_form_norm}' vs ADRES='{eps_adres_norm}'"
    else:
        detalle_eps = "Faltan datos de EPS para comparar"
        eps_coincide = True

    if not eps_coincide:
        discrepancias_leves += 1

    campos.append({
        "campo": "eps",
        "formulario": eps_form,
        "adres": adres["eps"],
        "coincide": eps_coincide,
        "detalle": detalle_eps,
    })

    # ── 3. Validar regimen ──
    regimen_form_norm = _normalizar_texto(regimen_form)
    regimen_adres_norm = _normalizar_texto(adres["regimen"])

    regimen_coincide = False
    detalle_regimen = ""
    if regimen_form_norm and regimen_adres_norm:
        if regimen_form_norm == regimen_adres_norm:
            regimen_coincide = True
            detalle_regimen = "Coincidencia exacta"
        elif regimen_form_norm in regimen_adres_norm or regimen_adres_norm in regimen_form_norm:
            regimen_coincide = True
            detalle_regimen = f"Coincidencia parcial"
        else:
            detalle_regimen = f"NO coinciden: Form='{regimen_form_norm}' vs ADRES='{regimen_adres_norm}'"
    else:
        detalle_regimen = "Faltan datos de regimen para comparar"
        regimen_coincide = True

    if not regimen_coincide:
        discrepancias_leves += 1

    campos.append({
        "campo": "regimen",
        "formulario": regimen_form,
        "adres": adres["regimen"],
        "coincide": regimen_coincide,
        "detalle": detalle_regimen,
    })

    # ── Conclusion ──
    n_discrepancias = discrepancias_graves + discrepancias_leves
    if discrepancias_graves > 0:
        validacion_pasa = False
        conclusion = f"DATOS NO COINCIDEN: {discrepancias_graves} discrepancia(s) grave(s) en nombres. Posible suplantación."
    elif discrepancias_leves > 0:
        validacion_pasa = True
        conclusion = f"DISCREPANCIAS MENORES: {discrepancias_leves} campo(s) no coinciden (EPS o régimen). Se procede con advertencia."
    else:
        validacion_pasa = True
        conclusion = "TODO COINCIDE: Datos del formulario validados contra ADRES."

    return {
        "campos": campos,
        "n_discrepancias": n_discrepancias,
        "discrepancias_graves": discrepancias_graves,
        "validacion_pasa": validacion_pasa,
        "conclusion": conclusion,
    }


# ── Endpoints ──────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    try:
        n_filas_cruce = _query("SELECT COUNT(*) as c FROM cruce_maestro")[0]["c"]
    except Exception:
        n_filas_cruce = 0
    return {
        "status": "ok" if (modelo_cargado or xgboost_cargado) else "degraded",
        "modelo_cargado": modelo_cargado,
        "xgboost_cargado": xgboost_cargado,
        "modo": "ia" if (modelo_cargado or xgboost_cargado) else "reglas",
        "db_path": str(DB_PATH),
        "n_filas_cruce": n_filas_cruce,
        "hc_detalle_disponible": hc_detalle_df is not None and len(hc_detalle_df) > 0,
    }


@app.get("/api/modelos")
def listar_modelos():
    """Lista los modelos de IA disponibles para auditoria de prefactura."""
    modelos = []
    # Modelo CNN local
    modelos.append({
        "id": "cnn_local",
        "nombre": "CNN MobileNetV2 (Local)",
        "descripcion": "Modelo entrenado localmente con dataset de 500+ cruces. Detecta inconsistencias HC vs PF mediante red neuronal convolucional sobre features tabulares convertidas a imagen 32x32.",
        "disponible": modelo_cargado,
        "tipo": "clasificacion_binaria",
        "modo_uso": "automatico",
    })
    # Modelo XGBoost local
    modelos.append({
        "id": "xgboost_local",
        "nombre": "XGBoost (Local)",
        "descripcion": "Modelo XGBoost entrenado localmente con features tabulares. Rapido, interpretable, con SHAP para explicar cada prediccion.",
        "disponible": xgboost_cargado,
        "tipo": "clasificacion_binaria",
        "modo_uso": "automatico",
    })
    # Modelo NVIDIA Nemotron
    modelos.append({
        "id": "nemotron_externo",
        "nombre": "NVIDIA Nemotron-3-nano",
        "descripcion": "Modelo de razonamiento LLM externo via API de NVIDIA. Analiza cada cruce con contexto clinico completo y genera explicaciones detalladas.",
        "disponible": bool(NVIDIA_API_KEY) and NVIDIA_API_KEY != "",
        "tipo": "razonamiento_llm",
        "modo_uso": "api_externa",
    })
    return {"modelos": modelos, "seleccionado_por_defecto": "cnn_local"}


# ── Cliente NVIDIA Nemotron ─────────────────────────────────────────

def _analizar_con_nemotron(
    paciente_info: dict,
    diagnostico: str,
    items_pf: list[dict],
    items_hc: list[dict],
    cruces: list[dict],
) -> dict:
    """
    Envia los datos de la prefactura y HC al modelo NVIDIA Nemotron
    para obtener analisis detallado de inconsistencias.
    """
    if not NVIDIA_API_KEY:
        return {"disponible": False, "error": "API key de NVIDIA no configurada"}

    # Construir prompt estructurado con reglas de negocio del jefe
    prompt = f"""Eres un auditor médico especializado en validación de prefacturas del sistema de salud colombiano (SGSSS).

## Datos del Paciente
- ID: {paciente_info.get('id', 'N/A')}
- EPS: {paciente_info.get('eps', 'N/A')}
- Régimen: {paciente_info.get('tipo_afiliacion', 'N/A')}
- Diagnóstico principal: {diagnostico}

## Items Facturados (Prefactura)
{chr(10).join([
    f"- {i+1}. CUPS: {item.get('codigo_cups_facturado', 'N/A')} | {item.get('descripcion_servicio_facturado', 'N/A')} | Cant: {item.get('cantidad_facturada', '?')} | Valor: ${item.get('valor_total', 0):,.0f}"
    for i, item in enumerate(items_pf)
])}

## Registros en Historia Clínica (por atención)
{chr(10).join([
    f"- {i+1}. CUPS: {item.get('codigo_cups', 'N/A')} | {item.get('descripcion', 'N/A')} | Cant: {item.get('cantidad_realizada', '?')} | Soporte: {item.get('soporte_clinico', 'N/A')}"
    for i, item in enumerate(items_hc)
])}

## Cruces Realizados (HC vs PF)
{chr(10).join([
    f"- Item {i+1}: PF CUPS {c.get('codigo_cups_pf', 'N/A')} vs HC CUPS {c.get('codigo_cups_hc', 'N/A')} | PF Cant: {c.get('cantidad_pf', '?')} vs HC Cant: {c.get('cantidad_hc', '?')} | Alerta: {c.get('tipo_alerta', 'NINGUNA')}"
    for i, c in enumerate(cruces)
])}

## REGLAS DE NEGOCIO PARA AUDITORÍA (CRÍTICO)

Analiza cada cruce aplicando las siguientes reglas de negocio del sistema de salud colombiano:

1. **COMPARACIÓN POR SET DE CUPS POR ATENCIÓN** (no fila a fila):
   - Debes comparar el SET completo de códigos CUPS facturados vs el SET completo de códigos CUPS con soporte clínico de toda la atención
   - Un código facturado es válido si aparece en el set de códigos con soporte clínico de esa misma atención
   - No compares solo pares aislados de filas; analiza la canasta completa de servicios

2. **VALIDACIÓN DE AUTORIZACIÓN EPS (Ambulatorio)**:
   - Servicios ambulatorios con valor >$100,000 COP requieren autorización previa de la EPS
   - Si el servicio es ambulatorio y alto valor, verifica si tiene autorización documentada
   - Marca como "SIN_AUTORIZACION_EPS" si no hay evidencia de autorización

3. **VALIDACIÓN DE SOPORTE MÉDICO DIARIO (Hospitalario)**:
   - Hospitalizaciones con tratamientos complejos (valor >$200,000 COP) requieren soporte médico diario
   - Verifica que haya evidencia de notas médicas diarias durante la hospitalización
   - Marca como "SIN_SOPORTE_MEDICO_DIARIO" si no hay soporte documentado

4. **DETECCIÓN DE SERVICIOS DE ALTO COSTO**:
   - Servicios de alto costo (>$500,000 COP) requieren validación especial
   - Verifica si están en Anexo 9 de servicios de alto costo del SGSSS
   - Marca como "SERVICIO_ALTO_COSTO_SIN_VALIDACION" si no hay validación

5. **VALIDACIÓN TEMPORAL**:
   - La facturación debe ocurrir dentro de los 7 días posteriores a la atención
   - Marca como "FACTURACION_TARDIA" si hay más de 7 días entre atención y facturación

6. **DETECCIÓN DE FUGAS DE INGRESO**:
   - Procedimientos con soporte clínico que no fueron facturados (pérdida económica para la IPS)
   - Marca como "NO_FACTURADO" si el código HC no aparece en el set de códigos facturados

Analiza cada cruce y determina:
1. ¿El servicio facturado está clínicamente justificado según el diagnóstico?
2. ¿Hay discrepancias en cantidades o códigos CUPS?
3. ¿Se facturaron servicios sin soporte clínico en el set completo de la atención?
4. ¿Hay servicios clínicos realizados que no se facturaron (fuga de ingreso)?
5. ¿Se cumplen las reglas de autorización EPS, soporte médico diario y validación temporal?

Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{{
  "analisis_general": "resumen breve de la auditoria aplicando reglas de negocio",
  "total_items": {{cantidad}},
  "consistentes": {{numero}},
  "inconsistentes": {{numero}},
  "detalle_cruces": [
    {{
      "item": {{numero}},
      "codigo_cups_pf": "codigo",
      "codigo_cups_hc": "codigo",
      "resultado": "CONSISTENTE|INCONSISTENTE",
      "tipo_alerta": "SIN_SOPORTE_CLINICO|CODIGO_NO_COINCIDE|CANTIDAD_DISCORDANTE|NO_FACTURADO|DIAGNOSTICO_NO_RELACIONADO|SIN_AUTORIZACION_EPS|SIN_SOPORTE_MEDICO_DIARIO|SERVICIO_ALTO_COSTO_SIN_VALIDACION|FACTURACION_TARDIA|CONSISTENTE",
      "severidad": "ALTA|MEDIA|NINGUNA",
      "explicacion": "explicacion detallada del analisis aplicando reglas de negocio"
    }}
  ],
  "recomendacion": "APROBAR|REVISAR|RECHAZAR",
  "observaciones": "notas adicionales sobre la prefactura considerando reglas de negocio del SGSSS"
}}
"""

    try:
        resp = requests.post(
            NVIDIA_API_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Eres un auditor médico experto en el sistema de salud colombiano. Responde siempre en formato JSON válido.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Intentar extraer JSON de la respuesta
        try:
            # Buscar bloque JSON entre llaves
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                resultado = json.loads(json_str)
            else:
                resultado = {"respuesta_raw": content}
        except json.JSONDecodeError:
            resultado = {"respuesta_raw": content}

        return {
            "disponible": True,
            "modelo": NVIDIA_MODEL,
            "resultado": resultado,
            "tokens_usados": data.get("usage", {}),
        }

    except requests.Timeout:
        return {"disponible": True, "error": "Timeout en la consulta a NVIDIA (60s)", "resultado": None}
    except Exception as e:
        return {"disponible": True, "error": str(e), "resultado": None}


# ── Analisis PDF con Nemotron ────────────────────────────────────

async def _analizar_prefactura_pdf(
    content: bytes,
    filename: str,
    tipo_doc: str,
    num_doc: str,
    id_atencion: str,
    modelo_selector: str,
) -> dict:
    """
    Extrae texto de un PDF de factura/prefactura y lo envia a Nemotron
    para analisis. No genera cruces estructurados ni usa CNN.
    """
    # 1. Extraer texto del PDF
    try:
        reader = PdfReader(io.BytesIO(content))
        paginas = []
        for page in reader.pages:
            texto = page.extract_text() or ""
            paginas.append(texto)
        texto_pdf = "\n---\n".join(paginas)
    except Exception as e:
        raise HTTPException(400, f"Error al leer PDF: {e}")

    if not texto_pdf.strip():
        raise HTTPException(400, "No se pudo extraer texto del PDF")

    # 2. Obtener datos del paciente desde BD local
    paciente_info = {}
    if num_doc:
        pac_rows = _query(
            "SELECT id_paciente, tipo_documento, eps_paciente as eps, tipo_afiliacion, ciudad FROM pacientes WHERE id_paciente LIKE ? LIMIT 1",
            (f"%{num_doc}%",),
        )
        if pac_rows:
            paciente_info = pac_rows[0]

    atencion_info = {}
    if id_atencion:
        atencion_row = _row(
            "SELECT DISTINCT id_atencion, fecha_atencion, tipo_atencion, diagnostico_principal_cie10, descripcion_diagnostico FROM atenciones WHERE id_atencion=?",
            (id_atencion,),
        )
        if atencion_row:
            atencion_info = atencion_row

    diagnostico_hc = f"{_s(atencion_info.get('diagnostico_principal_cie10'))} - {_s(atencion_info.get('descripcion_diagnostico'))}"

    # 3. Consultar HC para contexto (si hay atencion)
    items_hc = []
    if hc_detalle_df is not None and len(hc_detalle_df) > 0 and id_atencion:
        mask_atn = hc_detalle_df["id_atencion"].astype(str).str.contains(id_atencion, na=False, regex=False)
        hc_rows = hc_detalle_df[mask_atn]
        for _, row in hc_rows.iterrows():
            items_hc.append({
                "codigo_cups": _s(row.get("codigo_cups", "")),
                "descripcion": _s(row.get("descripcion", "")),
                "cantidad_realizada": _num(row.get("cantidad_realizada", 0)),
            })

    # 4. Enviar TODO a Nemotron
    prompt = f"""Eres un auditor médico especializado en validación de facturas y prefacturas del sistema de salud colombiano (SGSSS).

## Datos del Paciente (Formulario)
- Identificación: {tipo_doc} {num_doc}
- EPS: {paciente_info.get('eps', 'No especificada')}
- Régimen: {paciente_info.get('tipo_afiliacion', 'No especificado')}
- Diagnóstico registrado: {diagnostico_hc or 'No disponible'}

## Historial Clínico de la Atención
{chr(10).join([
    f"- CUPS: {h['codigo_cups']} | {h['descripcion']} | Cant realizada: {h['cantidad_realizada']}"
    for h in items_hc
]) if items_hc else "(Sin registros de HC disponibles para esta atención)"}

## Texto Extraído de la Factura PDF
{texto_pdf[:8000]}

{'---' if len(texto_pdf) > 8000 else ''}

Analiza la factura y determina:
1. ¿Cuáles son los servicios/procedimientos facturados? (código, descripción, cantidad, valor)
2. ¿Los servicios están clínicamente justificados según el diagnóstico?
3. ¿Hay discrepancias entre lo facturado y lo registrado en historia clínica?
4. ¿Hay servicios facturados sin soporte clínico?
5. ¿Hay servicios realizados NO facturados (fuga de ingreso)?

Responde ÚNICAMENTE en formato JSON con la siguiente estructura:
{{
  "analisis_general": "resumen breve de la auditoria",
  "tipo_documento": "FACTURA|PREFACTURA",
  "items_detectados": [
    {{
      "codigo": "codigo del servicio",
      "descripcion": "descripcion",
      "cantidad": 0,
      "valor_unitario": 0,
      "valor_total": 0,
      "analisis": "analisis de este item"
    }}
  ],
  "total_items": 0,
  "consistentes": 0,
  "inconsistentes": 0,
  "fugas_detectadas": ["descripcion de cada fuga"],
  "recomendacion": "APROBAR|REVISAR|RECHAZAR",
  "observaciones": "notas adicionales"
}}
"""

    if not NVIDIA_API_KEY:
        return {
            "tipo_archivo": "pdf",
            "pdf_filename": filename,
            "error": "API key de NVIDIA no configurada",
            "nemotron": {"disponible": False, "error": "API key no configurada"},
        }

    try:
        resp = requests.post(
            NVIDIA_API_URL,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": NVIDIA_MODEL,
                "messages": [
                    {"role": "system", "content": "Eres un auditor médico experto colombiano. Responde siempre en formato JSON válido."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        content_resp = data["choices"][0]["message"]["content"]

        resultado: dict = {}
        try:
            start = content_resp.find("{")
            end = content_resp.rfind("}") + 1
            if start >= 0 and end > start:
                resultado = json.loads(content_resp[start:end])
        except json.JSONDecodeError:
            resultado = {"respuesta_raw": content_resp}

        nemotron_result = {
            "disponible": True,
            "modelo": NVIDIA_MODEL,
            "resultado": resultado,
            "tokens_usados": data.get("usage", {}),
        }

    except requests.Timeout:
        nemotron_result = {"disponible": True, "error": "Timeout en la consulta a NVIDIA (90s)"}
    except Exception as e:
        nemotron_result = {"disponible": True, "error": str(e)}

    # 5. Armar respuesta
    items_detectados = (nemotron_result.get("resultado", {}) or {}).get("items_detectados", []) if nemotron_result.get("resultado") else []
    n_items = len(items_detectados)
    return {
        "tipo_archivo": "pdf",
        "pdf_filename": filename,
        "resumen": {
            "total_items": n_items,
            "consistentes": (nemotron_result.get("resultado", {}) or {}).get("consistentes", 0),
            "inconsistentes": (nemotron_result.get("resultado", {}) or {}).get("inconsistentes", 0),
            "fugas_encontradas": len((nemotron_result.get("resultado", {}) or {}).get("fugas_detectadas", [])),
            "recomendacion": (nemotron_result.get("resultado", {}) or {}).get("recomendacion", "REVISAR"),
        },
        "paciente": {
            "id": paciente_info.get("id_paciente", ""),
            "tipo_documento": tipo_doc,
            "eps": paciente_info.get("eps", ""),
            "tipo_afiliacion": paciente_info.get("tipo_afiliacion", ""),
        },
        "atencion": {
            "id": id_atencion,
            "diagnostico": diagnostico_hc,
        },
        "pdf_texto": texto_pdf[:2000],  # preview del texto extraido
        "modelos": {
            "cnn_local": None,  # PDF no se procesa con CNN
            "nemotron_externo": nemotron_result,
        },
    }


# ── Endpoint: Analizar Prefactura ──────────────────────────────────

@app.post("/api/prefactura/analizar")
async def analizar_prefactura(
    file: UploadFile = File(...),
    tipo_doc: str = Form("CC"),
    num_doc: str = Form(""),
    eps: str = Form(""),
    nombres: str = Form(""),
    apellidos: str = Form(""),
    tipo_afiliacion: str = Form(""),
    id_atencion: str = Form(""),
    modelo_selector: str = Form("ambos"),
    adres_result: str = Form(None),
):
    """
    Recibe un archivo CSV de prefactura, lo cruza con la historia clínica
    y ejecuta los modelos seleccionados (CNN local, Nemotron externo, o ambos).

    El CSV debe tener al menos las columnas:
      codigo_cups_facturado, descripcion_servicio_facturado, cantidad_facturada
    Y opcionalmente: id_prefactura, id_atencion, id_paciente, valor_unitario,
                     valor_total, fecha_facturacion, eps
    """
    # Parsear resultado de ADRES si viene del frontend
    adres_data = None
    if adres_result:
        try:
            import json
            adres_data = json.loads(adres_result)
        except:
            pass
    # ── Detectar tipo de archivo ──
    is_pdf = file.filename and file.filename.lower().endswith(".pdf")
    is_csv = file.filename and file.filename.lower().endswith(".csv")

    if not is_csv and not is_pdf:
        raise HTTPException(400, "Debe subir un archivo CSV (para CNN/Nemotron) o PDF (solo Nemotron)")

    if is_pdf and modelo_selector not in ("nemotron_externo", "ambos"):
        raise HTTPException(400, "PDF solo se puede procesar con el modelo NVIDIA Nemotron. Cambie el toggle a Nemotron.")

    # 1. Leer archivo
    content = await file.read()

    # ── MODO PDF (solo Nemotron) ──
    if is_pdf:
        if not PDF_SUPPORT:
            raise HTTPException(500, "PDF support not available (pypdf no instalado)")
        return await _analizar_prefactura_pdf(content, file.filename, tipo_doc, num_doc, id_atencion, modelo_selector)

    # ── MODO CSV (CNN y/o Nemotron) ──
    try:
        df_pf = pd.read_csv(io.StringIO(content.decode("utf-8-sig")))
    except Exception as e:
        raise HTTPException(400, f"Error al leer CSV: {e}")

    if df_pf.empty:
        raise HTTPException(400, "El archivo CSV está vacío")

    # 2. Validar columnas mínimas
    col_mapping = {
        "codigo_cups_facturado": ["codigo_cups_facturado", "codigo_cups", "cups", "codigo"],
        "descripcion_servicio_facturado": ["descripcion_servicio_facturado", "descripcion", "servicio", "descripcion_servicio"],
        "cantidad_facturada": ["cantidad_facturada", "cantidad", "cant"],
        "valor_total": ["valor_total", "valor", "total", "valortotal"],
        "id_atencion": ["id_atencion", "atencion"],
        "id_prefactura": ["id_prefactura", "prefactura", "id"],
        "eps": ["eps", "eps_paciente"],
        "tipo_documento": ["tipo_documento", "tipo_doc"],
        "numero_documento": ["numero_documento", "num_doc", "documento", "cedula"],
    }

    def _find_col(df, possible_names):
        for name in possible_names:
            for col in df.columns:
                if col.strip().lower() == name.lower():
                    return col
        return None

    col_cups = _find_col(df_pf, col_mapping["codigo_cups_facturado"])
    col_desc = _find_col(df_pf, col_mapping["descripcion_servicio_facturado"])
    col_cant = _find_col(df_pf, col_mapping["cantidad_facturada"])
    col_eps = _find_col(df_pf, col_mapping["eps"])
    col_tipo_doc = _find_col(df_pf, col_mapping["tipo_documento"])
    col_num_doc = _find_col(df_pf, col_mapping["numero_documento"])

    if not col_cups:
        raise HTTPException(400, f"CSV debe contener columna 'codigo_cups_facturado'. Columnas encontradas: {list(df_pf.columns)}")

    # 3. Normalizar columnas
    pf_items = []
    csv_eps = None
    csv_tipo_doc = None
    csv_num_doc = None
    
    for idx, row in df_pf.iterrows():
        item = {
            "codigo_cups_facturado": _s(row.get(col_cups, "")).strip(),
            "descripcion_servicio_facturado": _s(row.get(col_desc, "")).strip() if col_desc else "",
            "cantidad_facturada": _num(row.get(col_cant, 1) if col_cant else 1, default=1.0),
            "valor_unitario": _num(row.get(_find_col(df_pf, ["valor_unitario", "vr_unitario", "precio"]), 0)),
            "valor_total": _num(row.get(_find_col(df_pf, col_mapping["valor_total"]), 0)),
            "id_prefactura": _s(row.get(_find_col(df_pf, col_mapping["id_prefactura"]), "")).strip() or f"PF-UPL-{idx}",
            "id_atencion": _s(row.get(_find_col(df_pf, col_mapping["id_atencion"]), id_atencion)).strip() or id_atencion,
            "id_paciente": _s(row.get(_find_col(df_pf, ["id_paciente", "paciente"]), "")).strip(),
        }
        pf_items.append(item)
        
        # Capturar datos del paciente del CSV (primera fila)
        if idx == 0:
            if col_eps:
                csv_eps = str(row.get(col_eps, "")).strip()
            if col_tipo_doc:
                csv_tipo_doc = str(row.get(col_tipo_doc, "")).strip()
            if col_num_doc:
                csv_num_doc = str(row.get(col_num_doc, "")).strip()

    # 4. Usar datos del CSV si están disponibles, sino usar del formulario
    final_tipo_doc = csv_tipo_doc if csv_tipo_doc else tipo_doc
    final_num_doc = csv_num_doc if csv_num_doc else num_doc
    final_eps = csv_eps if csv_eps else eps  # Usar EPS del formulario si CSV no tiene

    # 5. Obtener datos del paciente desde BD local (busqueda por documento)
    paciente_info = {}
    if final_num_doc:
        # Normalizar documento para busqueda
        doc_normalizado = _normalizar_documento(final_num_doc)
        logger.debug(f"Buscando paciente con documento: {doc_normalizado}")
        
        # Buscar por id_paciente (que es el número de documento en esta BD)
        pac_rows = _query(
            "SELECT id_paciente, tipo_documento, eps_paciente as eps, tipo_afiliacion, ciudad FROM pacientes WHERE id_paciente=? LIMIT 1",
            (doc_normalizado,),
        )
        if pac_rows:
            paciente_info = pac_rows[0]
            logger.info(f"Paciente encontrado en BD local: {paciente_info['id_paciente']}")
        else:
            logger.info(f"Paciente NO encontrado en BD local: {final_num_doc}")
    
    # 5. Obtener atencion y diagnostico
    atencion_id = id_atencion or (pf_items[0]["id_atencion"] if pf_items else "")
    
    # 5. Obtener datos del paciente desde la historia clínica (atenciones)
    hc_paciente_info = {}
    if atencion_id:
        # Buscar datos del paciente en la atención
        atencion_paciente_row = _row(
            "SELECT p.id_paciente, p.tipo_documento, p.eps_paciente as eps FROM atenciones a JOIN pacientes p ON a.id_paciente = p.id_paciente WHERE a.id_atencion=? LIMIT 1",
            (atencion_id,),
        )
        if atencion_paciente_row:
            hc_paciente_info = atencion_paciente_row

    # ── FLUJO DE VALIDACIÓN ESTRICTA (3 pasos obligatorios) ──
    
    # Resultados de verificaciones para mostrar al usuario
    verificaciones = {
        "adres": {"verificado": False, "encontrado": False, "mensaje": ""},
        "bd_local": {"verificado": False, "encontrado": False, "mensaje": ""},
    }
    
    puede_proceder_ia = False
    error_validacion = None
    
    # ── PASO 1: Verificar ADRES (obligatorio) ──
    adres_error_tecnico = False  # Para distinguir error técnico vs datos incorrectos
    
    logger.debug(f"Datos ADRES proporcionados: {bool(adres_data)}")
    
    if not adres_data:
        # Si no se proporcionó resultado ADRES, consultar automáticamente
        logger.info("Consultando ADRES automáticamente...")
        from backend.adres_scraper import consultar_afiliacion
        try:
            adres_data = consultar_afiliacion(final_tipo_doc, final_num_doc)
            verificaciones["adres"]["verificado"] = True
            verificaciones["adres"]["encontrado"] = adres_data.get("encontrado", False)
            logger.debug(f"Resultado ADRES fuente: {adres_data.get('fuente')}")
            
            # Distinguir entre error técnico y datos no encontrados
            if adres_data.get("fuente") == "adres_no_disponible" or adres_data.get("error") in ["BDUA_NO_DISPONIBLE", "CAPTCHA_REQUERIDO", "ESTRUCTURA_NO_RECONOCIDA"]:
                adres_error_tecnico = True
                verificaciones["adres"]["indicador"] = "⚠️"
                verificaciones["adres"]["mensaje"] = f"ADRES no disponible (error técnico). {adres_data.get('mensaje', 'Modo contingencia activado.')}"
                logger.warning(f"ADRES error técnico: {adres_data.get('error')}")
            elif adres_data.get("encontrado"):
                verificaciones["adres"]["indicador"] = "✅"
                verificaciones["adres"]["mensaje"] = f"Paciente encontrado en ADRES: {adres_data.get('nombres', '')} {adres_data.get('apellidos', '')} - EPS: {adres_data.get('eps', '')}"
                logger.info(f"ADRES paciente encontrado")
            else:
                verificaciones["adres"]["indicador"] = "❌"
                verificaciones["adres"]["mensaje"] = f"Paciente NO encontrado en ADRES. {adres_data.get('mensaje', 'Verifique el número de documento.')}"
                logger.warning(f"ADRES paciente NO encontrado")
        except Exception as e:
            adres_error_tecnico = True
            verificaciones["adres"]["verificado"] = True
            verificaciones["adres"]["encontrado"] = False
            verificaciones["adres"]["indicador"] = "⚠️"
            verificaciones["adres"]["mensaje"] = f"Error técnico consultando ADRES: {str(e)}. Modo contingencia activado."
            logger.error(f"Excepción ADRES: {e}")
    else:
        # Usar resultado ADRES proporcionado
        logger.debug("Usando datos ADRES proporcionados")
        verificaciones["adres"]["verificado"] = True
        
        # Verificar estructura de datos ADRES (puede tener 'data' o campos directos)
        if adres_data.get("fuente") == "adres_no_disponible" or adres_data.get("error") in ["BDUA_NO_DISPONIBLE", "CAPTCHA_REQUERIDO", "ESTRUCTURA_NO_RECONOCIDA"]:
            adres_error_tecnico = True
            verificaciones["adres"]["encontrado"] = False
            verificaciones["adres"]["indicador"] = "⚠️"
            verificaciones["adres"]["mensaje"] = f"ADRES no disponible (error técnico). {adres_data.get('mensaje', 'Modo contingencia activado.')}"
            logger.warning(f"ADRES error técnico (datos proporcionados): {adres_error_tecnico}")
        elif "data" in adres_data and adres_data["data"]:
            # Estructura con 'data' (nuevo formato del scraper)
            data_content = adres_data["data"]
            # NO sobrescribir nombres/apellidos del formulario con los de ADRES
            # para que la validación compare correctamente los datos reales.
            # Los nombres de ADRES solo se usan para mostrar info, no para validar.
            adres_nombres = data_content.get("nombres", "")
            adres_apellidos = data_content.get("apellidos", "")
            estado_afiliacion = data_content.get("estado_afiliacion", {})
            eps = estado_afiliacion.get("entidad", "")
            
            if adres_nombres and adres_apellidos:
                verificaciones["adres"]["encontrado"] = True
                verificaciones["adres"]["indicador"] = "✅"
                verificaciones["adres"]["mensaje"] = f"Paciente encontrado en ADRES: {adres_nombres} {adres_apellidos} - EPS: {eps}"
                logger.info("ADRES paciente encontrado (estructura data)")
            else:
                verificaciones["adres"]["encontrado"] = False
                verificaciones["adres"]["indicador"] = "❌"
                verificaciones["adres"]["mensaje"] = f"Paciente NO encontrado en ADRES. Datos incompletos."
                logger.warning("ADRES paciente NO encontrado (estructura data incompleta)")
        elif adres_data.get("encontrado"):
            # Estructura antigua con campo 'encontrado' directo
            verificaciones["adres"]["encontrado"] = True
            verificaciones["adres"]["indicador"] = "✅"
            verificaciones["adres"]["mensaje"] = f"Paciente encontrado en ADRES: {adres_data.get('nombres', '')} {adres_data.get('apellidos', '')} - EPS: {adres_data.get('eps', '')}"
            logger.info("ADRES paciente encontrado (estructura antigua)")
        else:
            verificaciones["adres"]["encontrado"] = False
            verificaciones["adres"]["indicador"] = "❌"
            verificaciones["adres"]["mensaje"] = f"Paciente NO encontrado en ADRES. {adres_data.get('mensaje', 'Verifique el número de documento.')}"
            logger.warning("ADRES paciente NO encontrado (datos proporcionados)")
    
    # ── PASO 2: Verificar BD Local (obligatorio) ──
    verificaciones["bd_local"]["verificado"] = True
    if paciente_info:
        verificaciones["bd_local"]["encontrado"] = True
        verificaciones["bd_local"]["indicador"] = "✅"
        # La tabla pacientes no guarda nombres: identificar por documento/EPS
        verificaciones["bd_local"]["mensaje"] = f"Paciente encontrado en BD local: {paciente_info.get('id_paciente', '')} - EPS: {paciente_info.get('eps', '')}"
    else:
        verificaciones["bd_local"]["encontrado"] = False
        verificaciones["bd_local"]["indicador"] = "❌"
        verificaciones["bd_local"]["mensaje"] = f"Paciente NO encontrado en base de datos de la clínica. Cédula: {final_num_doc}"
    
    # ── PASO 2.5: Cruzar datos del formulario contra ADRES ──
    validacion_adres = None
    if adres_data and adres_data.get("encontrado", False) and not adres_error_tecnico:
        validacion_adres = _validar_cruce_adres(
            adres_data,
            {
                "nombres": nombres,
                "apellidos": apellidos,
                "eps": final_eps,
                "tipo_afiliacion": tipo_afiliacion,
            },
        )
        logger.info(f"Validación cruce ADRES: {validacion_adres['conclusion']}")
    
    # ── PASO 3: Decidir si proceder con IA ──
    # Lógica actualizada con validacion cruzada ADRES:
    # - Si ADRES tiene error técnico → usar solo BD local (modo contingencia)
    # - Si ADRES responde pero paciente no encontrado → RECHAZAR
    # - Si ADRES responde, encontrado pero datos NO cruzan (nombre no coincide) → RECHAZAR
    # - Si ADRES responde, encontrado, datos cruzan con discrepancias menores → REVISAR
    # - Si ADRES responde, encontrado, datos cruzan OK + BD local → APROBAR
    
    if adres_error_tecnico:
        logger.warning("Modo contingencia (ADRES error técnico)")
        if not verificaciones["bd_local"]["encontrado"]:
            error_validacion = f"RECHAZO: Paciente no encontrado en base de datos local. ADRES no disponible para validación externa. {verificaciones['bd_local']['mensaje']}"
            puede_proceder_ia = False
        else:
            error_validacion = f"ADVERTENCIA: ADRES no disponible. Validación realizada solo con base de datos local."
            puede_proceder_ia = True
    elif not verificaciones["adres"]["encontrado"]:
        error_validacion = f"RECHAZO: Paciente no encontrado en ADRES. {verificaciones['adres']['mensaje']}"
        puede_proceder_ia = False
    elif validacion_adres and not validacion_adres["validacion_pasa"]:
        # ADRES encontró el documento pero los nombres NO coinciden → posible suplantación
        error_validacion = f"RECHAZO: {validacion_adres['conclusion']}"
        puede_proceder_ia = False
    elif not verificaciones["bd_local"]["encontrado"]:
        if validacion_adres and validacion_adres["n_discrepancias"] > 0:
            error_validacion = f"REVISAR: {validacion_adres['conclusion']}. Además paciente no encontrado en BD local."
            puede_proceder_ia = True  # REVISAR permite proceder pero con advertencia
        else:
            error_validacion = f"RECHAZO: Paciente encontrado en ADRES pero NO atendido en esta clínica. {verificaciones['bd_local']['mensaje']}"
            puede_proceder_ia = False
    else:
        if validacion_adres and validacion_adres["n_discrepancias"] > 0:
            error_validacion = f"REVISAR: {validacion_adres['conclusion']}"
            puede_proceder_ia = True  # REVISAR = proceder pero cambiar badge
        else:
            puede_proceder_ia = True
    
    logger.info(f"Resultado validación - puede_proceder_ia: {puede_proceder_ia}, error: {error_validacion}")
    
    # ── PASO 2.75: Extraer comparación de EPS para mostrar en frontend ──
    eps_formulario_val = final_eps
    eps_adres_valor = ""
    eps_verificado = False
    eps_coincide = True
    
    if validacion_adres:
        # Extraer el campo EPS del cruce ADRES
        eps_campo = next((c for c in validacion_adres.get("campos", []) if c["campo"] == "eps"), None)
        if eps_campo:
            eps_coincide = eps_campo["coincide"]
            eps_adres_valor = eps_campo["adres"]
            eps_verificado = True
    elif adres_data and adres_data.get("encontrado", False) and not adres_error_tecnico:
        # Si no hay validación ADRES completa, intentar extraer EPS directamente
        adres_extracted = _extraer_datos_adres(adres_data)
        eps_adres_valor = adres_extracted.get("eps", "")
        if eps_adres_valor:
            # Sí se pudo extraer EPS de ADRES: marcar como verificado y comparar
            eps_adres_norm = _normalizar_eps(eps_adres_valor)
            eps_form_norm = _normalizar_eps(eps_formulario_val)
            if eps_form_norm and eps_adres_norm:
                eps_coincide = eps_form_norm == eps_adres_norm or eps_form_norm in eps_adres_norm or eps_adres_norm in eps_form_norm
            eps_verificado = True
        # Si no se pudo extraer EPS, eps_verificado queda False (no se puede afirmar nada)
    
    verificaciones["eps_adres"] = {
        "verificado": eps_verificado,
        "coincide": eps_coincide,
        "formulario": eps_formulario_val,
        "adres": eps_adres_valor,
    }
    
    # Pasar validacion_adres a verificaciones
    if validacion_adres:
        verificaciones["cruce_adres"] = validacion_adres
    
    # ── CONTINUAR CON ANÁLISIS DE HC vs PF (solo si puede_proceder_ia = True) ──
    atencion_info = {}
    if atencion_id:
        atencion_row = _row(
            "SELECT DISTINCT id_atencion, fecha_atencion, tipo_atencion, diagnostico_principal_cie10, descripcion_diagnostico FROM atenciones WHERE id_atencion=?",
            (atencion_id,),
        )
        if atencion_row:
            atencion_info = atencion_row

    diagnostico = f"{_s(atencion_info.get('diagnostico_principal_cie10'))} - {_s(atencion_info.get('descripcion_diagnostico'))}"

    # ── Si no pasa las verificaciones, retornar sin ejecutar IA ──
    if not puede_proceder_ia:
        return {
            "resumen": {
                "total_items": len(pf_items),
                "consistentes": 0,
                "inconsistentes": len(pf_items),
                "inconsistencias_clinicas": 0,
                "inconsistencias_datos": 0,
                "detalles": {
                    "sin_soporte_clinico": 0,
                    "codigo_no_coincide": 0,
                    "cantidad_discordante": 0,
                },
                "fugas_encontradas": 0,
                "valor_total_prefactura": sum(item.get("valor_total", 0) or 0 for item in pf_items),
                "valor_en_inconsistencias": 0,
                "valor_inconsistencias_clinicas": 0,
                "valor_inconsistencias_datos": 0,
                "porcentaje_inconsistente": 100.0,
                "recomendacion": "RECHAZAR",
                "motivo_recomendacion": error_validacion,
            },
            "verificaciones": verificaciones,
            "paciente": {
                "id": paciente_info.get("id_paciente", ""),
                "tipo_documento": paciente_info.get("tipo_documento", tipo_doc),
                "eps": paciente_info.get("eps", ""),
                "tipo_afiliacion": paciente_info.get("tipo_afiliacion", ""),
                "encontrado_db_local": bool(paciente_info),
            },
            "atencion": {
                "id": atencion_id,
                "fecha": "",
                "tipo": "",
                "diagnostico": "",
            },
            "cruces": [],
            "fugas": [],
            "modelos": {
                "cnn_local": None,
                "xgboost_local": None,
                "nemotron_externo": None,
            },
        }

    # 6. Cruce con HC detalle (solo si pasa verificaciones)
    cruces = []
    items_hc_encontrados = []

    for pf_item in pf_items:
        cups_pf = pf_item["codigo_cups_facturado"]
        cant_pf = pf_item["cantidad_facturada"]
        atn_id = pf_item["id_atencion"] or atencion_id

        # Buscar en HC detalle
        hc_match = None
        if hc_detalle_df is not None and len(hc_detalle_df) > 0 and atn_id:
            # Buscar por id_atencion + codigo_cups (regex=False: el id se trata
            # como texto literal, no como expresion regular)
            mask_atn = hc_detalle_df["id_atencion"].astype(str).str.contains(atn_id, na=False, regex=False)
            mask_cups = hc_detalle_df["codigo_cups"].astype(str).str.strip() == cups_pf
            matches = hc_detalle_df[mask_atn & mask_cups]

            if not matches.empty:
                hc_match = matches.iloc[0].to_dict()
            else:
                # Buscar solo por id_atencion
                atn_matches = hc_detalle_df[mask_atn]
                if not atn_matches.empty:
                    hc_match = atn_matches.iloc[0].to_dict()
                    # No encontramos CUPS matching, pero hay HC para esta atencion
                    hc_match["_cups_no_match"] = True

        elif atn_id:
            # Buscar en cruce_maestro de la BD
            bd_rows = _query(
                "SELECT codigo_cups, descripcion, cantidad_realizada, soporte_clinico FROM cruce_maestro WHERE id_atencion=? AND codigo_cups_facturado=? LIMIT 1",
                (atn_id, cups_pf),
            )
            if bd_rows:
                hc_match = bd_rows[0]
            else:
                # Buscar directamente en historia_clinica_detalle de la BD
                # (la tabla puede no existir si la BD se construyo solo con
                # el dataset maestro: no debe tumbar el endpoint)
                try:
                    bd_hc_rows = _query(
                        "SELECT codigo_cups, descripcion, cantidad_realizada, soporte_clinico FROM historia_clinica_detalle WHERE id_atencion=? AND codigo_cups=? LIMIT 1",
                        (atn_id, cups_pf),
                    )
                except sqlite3.Error:
                    bd_hc_rows = []
                if bd_hc_rows:
                    hc_match = bd_hc_rows[0]

        # Determinar alertas
        alertas = []
        tipo_alerta = "CONSISTENTE"
        severidad = "NINGUNA"

        if hc_match is None:
            # No hay HC para este item facturado
            alertas.append(
                {
                    "tipo": "SIN_SOPORTE_CLINICO",
                    "severidad": "ALTA",
                    "descripcion": f"Servicio {cups_pf} facturado sin registro de soporte clínico en la HC.",
                }
            )
            tipo_alerta = "SIN_SOPORTE_CLINICO"
            severidad = "ALTA"
            resultado = "INCONSISTENTE"
        else:
            cups_hc = _s(hc_match.get("codigo_cups", "")).strip()
            cant_hc = _num(hc_match.get("cantidad_realizada", 0))
            soporte = _s(hc_match.get("soporte_clinico", "")).strip()

            if hc_match.get("_cups_no_match"):
                alertas.append(
                    {
                        "tipo": "CODIGO_NO_COINCIDE",
                        "severidad": "ALTA",
                        "descripcion": f"CUPS facturado {cups_pf} no coincide con ningún CUPS registrado en la HC (HC tiene: {cups_hc}).",
                    }
                )
                tipo_alerta = "CODIGO_NO_COINCIDE"
                severidad = "ALTA"
            elif cups_hc.upper() != cups_pf.upper():
                alertas.append(
                    {
                        "tipo": "CODIGO_NO_COINCIDE",
                        "severidad": "ALTA",
                        "descripcion": f"Código CUPS HC={cups_hc} vs PF={cups_pf} no coinciden.",
                    }
                )
                tipo_alerta = "CODIGO_NO_COINCIDE"
                severidad = "ALTA"

            if abs(cant_hc - cant_pf) > 1e-6:
                alertas.append(
                    {
                        "tipo": "CANTIDAD_DISCORDANTE",
                        "severidad": "MEDIA",
                        "descripcion": f"Cantidad HC={cant_hc} vs PF={cant_pf} difieren.",
                    }
                )
                if tipo_alerta == "CONSISTENTE":
                    tipo_alerta = "CANTIDAD_DISCORDANTE"
                    severidad = "MEDIA"

            if soporte.upper() == "NO":
                alertas.append(
                    {
                        "tipo": "SIN_SOPORTE_CLINICO",
                        "severidad": "ALTA",
                        "descripcion": f"Servicio {cups_pf} no tiene soporte clínico documentado.",
                    }
                )
                tipo_alerta = "SIN_SOPORTE_CLINICO"
                severidad = "ALTA"

            resultado = "INCONSISTENTE" if alertas else "CONSISTENTE"

            if hc_match and not hc_match.get("_cups_no_match"):
                items_hc_encontrados.append(
                    {
                        "codigo_cups": cups_hc,
                        "descripcion": _s(hc_match.get("descripcion", "")),
                        "cantidad_realizada": cant_hc,
                        "soporte_clinico": soporte,
                    }
                )

        cruce = {
            "item": len(cruces) + 1,
            "codigo_cups_pf": cups_pf,
            "descripcion_pf": pf_item["descripcion_servicio_facturado"],
            "cantidad_pf": cant_pf,
            "valor_total_pf": pf_item["valor_total"],
            "codigo_cups_hc": _s(hc_match.get("codigo_cups", "")) if hc_match else "",
            "descripcion_hc": _s(hc_match.get("descripcion", "")) if hc_match else "",
            "cantidad_hc": _num(hc_match.get("cantidad_realizada", 0)) if hc_match else 0,
            "resultado": resultado,
            "tipo_alerta": tipo_alerta,
            "severidad": severidad,
            "alertas": alertas,
            "soporte_clinico": _s(hc_match.get("soporte_clinico", "")) if hc_match else "NO",
        }
        cruces.append(cruce)

    # 7. Verificar items NO facturados (fuga de ingreso)
    # Una fuga es un procedimiento CON soporte clinico que no fue facturado
    # (misma definicion que usa el analisis por lote y la regla 6 de negocio).
    fugas = []
    if atencion_id:
        cups_facturados = set(c["codigo_cups_pf"] for c in cruces)
        hc_para_atencion = []

        # Buscar en hc_detalle_df (CSV) primero
        if hc_detalle_df is not None and len(hc_detalle_df) > 0:
            mask_atn = hc_detalle_df["id_atencion"].astype(str).str.contains(atencion_id, na=False, regex=False)
            hc_para_atencion = hc_detalle_df[mask_atn].to_dict('records') if not hc_detalle_df[mask_atn].empty else []

        # Si no se encontraron en CSV, buscar en BD SQLite
        # (la tabla puede no existir: no debe tumbar el endpoint)
        if not hc_para_atencion:
            try:
                hc_para_atencion = _query(
                    "SELECT codigo_cups, descripcion, cantidad_realizada, soporte_clinico FROM historia_clinica_detalle WHERE id_atencion=?",
                    (atencion_id,),
                )
            except sqlite3.Error:
                hc_para_atencion = []

        for hc_row in hc_para_atencion:
            cups_hc = _s(hc_row.get("codigo_cups", "")).strip()
            tiene_soporte = _s(hc_row.get("soporte_clinico", "")).strip().upper() == "SI"
            if cups_hc and tiene_soporte and cups_hc not in cups_facturados:
                fugas.append(
                    {
                        "codigo_cups": cups_hc,
                        "descripcion": _s(hc_row.get("descripcion", "")),
                        "cantidad_realizada": _num(hc_row.get("cantidad_realizada", 0)),
                        "tipo_alerta": "NO_FACTURADO",
                        "severidad": "ALTA",
                        "descripcion_alerta": f"Procedimiento {cups_hc} realizado según HC pero NO facturado (fuga de ingreso).",
                    }
                )

    # 8. Ejecutar modelo XGBoost local (si seleccionado)
    resultado_xgboost = None
    if modelo_selector in ("xgboost_local", "ambos") and xgboost_cargado:
        try:
            df_xgb = pd.DataFrame(cruces)
            rename_map_xgb = {
                "codigo_cups_pf": "codigo_cups_facturado",
                "codigo_cups_hc": "codigo_cups",
                "descripcion_hc": "descripcion",
                "cantidad_hc": "cantidad_realizada",
                "cantidad_pf": "cantidad_facturada",
                "valor_total_pf": "valor_total",
            }
            df_xgb = df_xgb.rename(columns=rename_map_xgb)
            # Usar el soporte clinico REAL del cruce (sobreescribirlo con "SI"
            # sesgaba al modelo hacia CONSISTENTE). Vacio = sin dato -> "SI"
            # para mantener el comportamiento neutro anterior.
            if "soporte_clinico" in df_xgb.columns:
                df_xgb["soporte_clinico"] = df_xgb["soporte_clinico"].replace("", "SI").fillna("SI")
            else:
                df_xgb["soporte_clinico"] = "SI"
            df_xgb["eps_atencion"] = paciente_info.get("eps", "")
            df_xgb["tipo_afiliacion"] = paciente_info.get("tipo_afiliacion", "Contributivo")
            df_xgb["tipo_atencion"] = atencion_info.get("tipo_atencion", "Ambulatoria")
            df_xgb["sede"] = "General"
            # Agregar valor_unitario (faltante - necesario para el scaler)
            if "valor_unitario" not in df_xgb.columns:
                df_xgb["valor_unitario"] = df_xgb["valor_total"] / df_xgb["cantidad_facturada"].replace(0, 1)
            df_xgb["diagnostico_principal_cie10"] = atencion_info.get("diagnostico_principal_cie10", "Z000")
            df_xgb["ciudad"] = paciente_info.get("ciudad", "Bogota")
            df_xgb["medico_tratante"] = atencion_info.get("medico_tratante", "MED-000")
            df_xgb["mes_atencion"] = 1
            df_xgb["edad"] = 30

            pred_xgb = predecir_xgboost(df_xgb)
            if pred_xgb.get("disponible", False):
                resultado_xgboost = {
                    "modelo": "XGBoost",
                    "disponible": True,
                    "probabilidades": pred_xgb["probabilidades"],
                    "predicciones": pred_xgb["predicciones"],
                    "threshold": pred_xgb["threshold"],
                    "consistentes": pred_xgb["consistentes"],
                    "inconsistentes": pred_xgb["inconsistentes"],
                }
                for i, cruce in enumerate(cruces):
                    if i < len(pred_xgb["probabilidades"]):
                        cruce["xgb_probabilidad"] = pred_xgb["probabilidades"][i]
                        cruce["xgb_prediccion"] = "INCONSISTENTE" if pred_xgb["predicciones"][i] == 1 else "CONSISTENTE"
            else:
                resultado_xgboost = {"modelo": "XGBoost", "disponible": False, "error": pred_xgb.get("error", "No disponible")}
        except Exception as e:
            resultado_xgboost = {"modelo": "XGBoost", "disponible": False, "error": str(e)}

    # 9. Ejecutar modelo CNN local (si seleccionado)
    resultado_cnn = None
    if modelo_selector in ("cnn_local", "ambos") and modelo_cargado:
        try:
            # Construir DataFrame con el formato esperado por predecir_inconsistencia
            df_cnn = pd.DataFrame(cruces)
            # Renombrar columnas para que coincidan con el pipeline
            rename_map = {
                "codigo_cups_pf": "codigo_cups_facturado",
                "codigo_cups_hc": "codigo_cups",
                "descripcion_hc": "descripcion",
                "cantidad_hc": "cantidad_realizada",
                "cantidad_pf": "cantidad_facturada",
                "valor_total_pf": "valor_total",
            }
            df_cnn = df_cnn.rename(columns=rename_map)
            # Agregar columnas necesarias que el pipeline espera
            df_cnn["edad"] = paciente_info.get("edad", 30)
            df_cnn["sexo"] = paciente_info.get("sexo", "M")
            df_cnn["eps_atencion"] = paciente_info.get("eps", "")
            df_cnn["tipo_afiliacion"] = paciente_info.get("tipo_afiliacion", "Contributivo")
            df_cnn["ciudad"] = paciente_info.get("ciudad", "Bogota")
            df_cnn["tipo_documento"] = paciente_info.get("tipo_documento", tipo_doc)
            df_cnn["tipo_atencion"] = atencion_info.get("tipo_atencion", "Ambulatoria")
            df_cnn["sede"] = "General"
            df_cnn["tipo_item"] = "consulta"
            # Igual que en XGBoost: conservar el soporte clinico real del cruce
            if "soporte_clinico" in df_cnn.columns:
                df_cnn["soporte_clinico"] = df_cnn["soporte_clinico"].replace("", "SI").fillna("SI")
            else:
                df_cnn["soporte_clinico"] = "SI"
            # Agregar valor_unitario (faltante - necesario para el StandardScaler)
            if "valor_unitario" not in df_cnn.columns:
                df_cnn["valor_unitario"] = df_cnn["valor_total"] / df_cnn["cantidad_facturada"].replace(0, 1)  # por defecto
            df_cnn["grupo_etario"] = "ADULTO"
            df_cnn["diagnostico_principal_cie10"] = atencion_info.get("diagnostico_principal_cie10", "Z000")
            df_cnn["medico_tratante"] = atencion_info.get("medico_tratante", "MED-000")
            df_cnn["profesional_responsable"] = "MED-000"
            df_cnn["mes_atencion"] = pd.to_datetime(atencion_info.get("fecha_atencion", "2025-01-01"), errors="coerce").month if atencion_info.get("fecha_atencion") else 1

            pred = predecir_inconsistencia(df_cnn)
            resultado_cnn = {
                "modelo": "CNN MobileNetV2",
                "disponible": True,
                "probabilidades": pred["probabilidades"],
                "predicciones": pred["predicciones"],
                "threshold": pred["threshold"],
                "consistentes": pred["consistentes"],
                "inconsistentes": pred["inconsistentes"],
            }

            # Fusionar predicciones CNN con cruces
            for i, cruce in enumerate(cruces):
                if i < len(pred["probabilidades"]):
                    cruce["cnn_probabilidad"] = pred["probabilidades"][i]
                    cruce["cnn_prediccion"] = "INCONSISTENTE" if pred["predicciones"][i] == 1 else "CONSISTENTE"
        except Exception as e:
            resultado_cnn = {"modelo": "CNN MobileNetV2", "disponible": True, "error": str(e)}

    # 10. Ejecutar modelo NVIDIA Nemotron (si seleccionado)
    resultado_nemotron = None
    if modelo_selector in ("nemotron_externo", "ambos") and NVIDIA_API_KEY:
        resultado_nemotron = _analizar_con_nemotron(
            paciente_info=paciente_info,
            diagnostico=diagnostico,
            items_pf=pf_items,
            items_hc=items_hc_encontrados,
            cruces=cruces,
        )

    # 11. Armar respuesta final con jerarquia de errores
    # ── CLASIFICACION: distinguir entre inconsistencias clinicas y de datos ──
    # Solo SIN_SOPORTE_CLINICO justifica RECHAZAR.
    # CODIGO_NO_COINCIDE y CANTIDAD_DISCORDANTE son advertencias (REVISAR).
    n_consistentes = sum(1 for c in cruces if c["resultado"] == "CONSISTENTE")
    n_inconsistentes = sum(1 for c in cruces if c["resultado"] == "INCONSISTENTE")

    # Contar por tipo de alerta (jerarquia de errores)
    alertas_por_tipo = {}
    for c in cruces:
        ta = c.get("tipo_alerta", "CONSISTENTE")
        alertas_por_tipo[ta] = alertas_por_tipo.get(ta, 0) + 1

    n_sin_soporte = alertas_por_tipo.get("SIN_SOPORTE_CLINICO", 0)  # FALTA SOPORTE CLINICO -> puede RECHAZAR
    n_codigo_no_coincide = alertas_por_tipo.get("CODIGO_NO_COINCIDE", 0)  # Discrepancia de datos -> solo REVISAR
    n_cantidad_discordante = alertas_por_tipo.get("CANTIDAD_DISCORDANTE", 0)  # Discrepancia de datos -> solo REVISAR
    n_advertencias_datos = n_codigo_no_coincide + n_cantidad_discordante  # Solo advertencias, no rechazo

    valor_total_pf = sum(c.get("valor_total_pf", 0) or 0 for c in cruces)
    valor_inconsistencias_clinicas = sum(
        c.get("valor_total_pf", 0) or 0 for c in cruces if c.get("tipo_alerta") == "SIN_SOPORTE_CLINICO"
    )
    valor_inconsistencias_datos = sum(
        c.get("valor_total_pf", 0) or 0 for c in cruces if c.get("tipo_alerta") in ("CODIGO_NO_COINCIDE", "CANTIDAD_DISCORDANTE")
    )

    # ── LOGICA DE RECOMENDACION (jerarquia flexible) ──
    # RECHAZAR: Solo si items sin soporte clinico (falta justificación clínica)
    # REVISAR: Si discrepancias de datos (CUPS/cantidad)
    # APROBAR: Si todo es consistente
    
    if n_sin_soporte > 0:
        # Falta de soporte clínico es el único motivo de rechazo
        recomendacion = "RECHAZAR"
        motivo_recomendacion = f"{n_sin_soporte} item(es) facturado(s) sin soporte clinico en la Historia Clinica"
    elif n_advertencias_datos > 0:
        recomendacion = "REVISAR"
        motivo_recomendacion = f"{n_advertencias_datos} discrepancia(s) en datos (CUPS/cantidad) - requiere revisión"
    else:
        recomendacion = "APROBAR"
        motivo_recomendacion = "Todos los items tienen soporte clinico y datos consistentes"

    return {
        "resumen": {
            "total_items": len(cruces),
            "consistentes": n_consistentes,
            "inconsistentes": n_inconsistentes,
            # ── Desglose por jerarquia de errores ──
            "inconsistencias_clinicas": n_sin_soporte,  # FALTA SOPORTE CLINICO (puede rechazar)
            "inconsistencias_datos": n_advertencias_datos,  # Discrepancias de datos (solo advertencia)
            "detalles": {
                "sin_soporte_clinico": n_sin_soporte,
                "codigo_no_coincide": n_codigo_no_coincide,
                "cantidad_discordante": n_cantidad_discordante,
            },
            # ── Fugas ──
            "fugas_encontradas": len(fugas),
            # ── Valores ──
            "valor_total_prefactura": round(valor_total_pf, 2),
            "valor_en_inconsistencias": round(valor_inconsistencias_clinicas + valor_inconsistencias_datos, 2),
            "valor_inconsistencias_clinicas": round(valor_inconsistencias_clinicas, 2),
            "valor_inconsistencias_datos": round(valor_inconsistencias_datos, 2),
            "porcentaje_inconsistente": round(
                (n_inconsistentes / len(cruces) * 100) if cruces else 0, 1
            ),
            # ── Recomendacion con jerarquia ──
            "recomendacion": recomendacion,
            "motivo_recomendacion": motivo_recomendacion,
        },
        "verificaciones": verificaciones,  # Agregar verificaciones con indicadores visuales
        "paciente": {
            "id": paciente_info.get("id_paciente", ""),
            "tipo_documento": paciente_info.get("tipo_documento", tipo_doc),
            "eps": paciente_info.get("eps", ""),
            "eps_adres": eps_adres_valor,  # EPS de ADRES
            "tipo_afiliacion": paciente_info.get("tipo_afiliacion", ""),
            "encontrado_db_local": bool(paciente_info),
        },
        "atencion": {
            "id": atencion_id,
            "fecha": _s(atencion_info.get("fecha_atencion", "")),
            "tipo": _s(atencion_info.get("tipo_atencion", "")),
            "diagnostico": diagnostico,
        },
        "cruces": cruces,
        "fugas": fugas,
        "modelos": {
            "cnn_local": resultado_cnn,
            "xgboost_local": resultado_xgboost,
            "nemotron_externo": resultado_nemotron,
        },
    }


# ── Endpoints existentes (sin cambios) ──────────────────────────────

@app.get("/api/pacientes")
def listar_pacientes(q: str = Query("", description="Busqueda por numero de documento (id_paciente)")):
    """
    Busca pacientes exclusivamente por numero de documento (id_paciente).
    El nombre NO se usa para busqueda - solo el documento.
    """
    if q:
        # Normalizar el documento de busqueda
        doc_normalizado = _normalizar_documento(q)
        rows = _query(
            """SELECT id_paciente, tipo_documento, edad, sexo, eps_paciente as eps,
               tipo_afiliacion, ciudad FROM pacientes
               WHERE id_paciente LIKE ?
               LIMIT 20""",
            (f"%{doc_normalizado}%",),
        )
    else:
        rows = _query(
            "SELECT id_paciente, tipo_documento, edad, sexo, eps_paciente as eps, tipo_afiliacion, ciudad FROM pacientes WHERE id_paciente IS NOT NULL LIMIT 50"
        )
    return {"results": rows, "total": len(rows)}


@app.get("/api/paciente/{pac_id}")
def detalle_paciente(pac_id: str):
    pac = _row("SELECT * FROM pacientes WHERE id_paciente=?", (pac_id,))
    if not pac:
        raise HTTPException(404, "Paciente no encontrado")
    atenciones = _query(
        """SELECT DISTINCT id_atencion, fecha_atencion, tipo_atencion, diagnostico_principal_cie10
           FROM atenciones WHERE id_paciente=? ORDER BY fecha_atencion DESC""",
        (pac_id,),
    )
    pac["atenciones"] = atenciones
    pac["n_atenciones"] = len(atenciones)
    return pac


@app.post("/api/paciente/verificar-adres")
def verificar_adres(data: dict):
    """
    Consulta afiliacion en ADRES/BDUA mediante web scraping de la
    consulta ciudadana (https://www.adres.gov.co/consulte-su-eps).

    USO ACADEMICO - Samsung Innovation Campus Capstone.
    Si el scraper falla (403, captcha, timeout), retorna
    fuente='adres_no_disponible' y la auditoria procede
    con datos locales.
    """
    tipo_doc = str(data.get("tipo_documento", "cc")).upper().strip()
    num_doc = str(data.get("numero_documento", "")).strip()

    if not num_doc:
        raise HTTPException(400, "numero_documento requerido")

    # Normalizar tipos de documento (mapeo completo desde el scraper)
    DOC_MAP = {"CC": "CC", "TI": "TI", "CE": "CE", "RC": "RC",
               "PA": "PA", "NU": "NU", "AS": "AS", "MS": "MS",
               "CD": "CD", "CN": "CN"}
    tipo_normalizado = DOC_MAP.get(tipo_doc, "CC")

    # Consultar via scraper
    resultado = consultar_afiliacion(tipo_normalizado, num_doc)

    if not resultado.get("encontrado"):
        # Scraper no pudo obtener datos (BDUA_NO_DISPONIBLE, timeout, etc.)
        return {
            "fuente": resultado.get("fuente", "adres_no_disponible"),
            "mensaje": resultado.get(
                "mensaje",
                "BDUA no disponible en este momento. La auditoria procede con datos locales."
            ),
            "datos_sugeridos": {
                "tipo_identificacion": tipo_normalizado,
                "numero_identificacion": num_doc,
            },
        }

    # Normalizar EPS para facilitar comparaciones en frontend
    eps_original = resultado.get("eps", "")
    entidad_normalizada = _normalizar_eps(eps_original)
    
    # Transformar al formato que espera el frontend
    return {
        "fuente": "adres_bdua",
        "origen": "web_scraping",
        "data": {
            "nombres": resultado.get("nombres", ""),
            "apellidos": resultado.get("apellidos", ""),
            "tipo_de_identificacion": resultado.get("tipo_documento", tipo_normalizado),
            "numero_de_identificacion": resultado.get("numero_documento", num_doc),
            "fecha_de_nacimiento": resultado.get("fecha_nacimiento", ""),
            "departamento": resultado.get("departamento", ""),
            "municipio": resultado.get("municipio", ""),
            "estado_afiliacion": {
                "estado": resultado.get("estado_afiliacion", "ACTIVO"),
                "entidad": eps_original,
                "entidad_normalizada": entidad_normalizada,
                "regimen": resultado.get("regimen", ""),
                "fecha_afiliacion": resultado.get("fecha_afiliacion", ""),
                "fecha_finalizacion": resultado.get("fecha_finalizacion", ""),
            },
        },
    }


@app.get("/api/atenciones")
def listar_atenciones(pac_id: str = Query("")):
    if pac_id:
        rows = _query(
            """SELECT DISTINCT id_atencion, fecha_atencion, tipo_atencion,
               diagnostico_principal_cie10, descripcion_diagnostico
               FROM atenciones WHERE id_paciente=? ORDER BY fecha_atencion DESC""",
            (pac_id,),
        )
    else:
        rows = _query(
            "SELECT DISTINCT id_atencion, fecha_atencion, tipo_atencion FROM atenciones LIMIT 50"
        )
    return {"results": rows}


@app.get("/api/cruces-atencion/{id_atencion}")
def cruces_por_atencion(id_atencion: str):
    rows = _query(
        "SELECT id_cruce, resultado, tipo_alerta, severidad, codigo_cups, codigo_cups_facturado FROM cruce_maestro WHERE id_atencion=? LIMIT 30",
        (id_atencion,),
    )
    return {"id_atencion": id_atencion, "results": rows, "total": len(rows)}


@app.get("/api/auditar/{id_cruce}")
def auditar_cruce(id_cruce: str):
    cruce_row = _row("SELECT * FROM cruce_maestro WHERE id_cruce=?", (id_cruce,))
    if not cruce_row:
        raise HTTPException(404, f"Cruce {id_cruce} no encontrado")

    df_input = pd.DataFrame([cruce_row])
    alerta_reglas = _calcular_reglas(df_input.iloc[0])

    if modelo_cargado:
        try:
            pred = predecir_inconsistencia(df_input)
            prob = pred["probabilidades"][0]
            es_inconsistente = prob > cargar_artefactos()["threshold"]
            resultado_ia = {
                "modelo": "MobileNetV2",
                "probabilidad_inconsistencia": round(float(prob), 4),
                "prediccion": "INCONSISTENTE" if es_inconsistente else "CONSISTENTE",
                "threshold": float(cargar_artefactos()["threshold"]),
            }
        except Exception as e:
            resultado_ia = {"error": str(e), "prediccion": "ERROR"}
    else:
        resultado_ia = {"modelo": "no_cargado", "prediccion": "NO_DISPONIBLE"}

    tipo_final = (
        alerta_reglas.get("tipo_alerta", "CONSISTENTE")
        if alerta_reglas.get("inconsistente")
        else "CONSISTENTE"
    )

    return {
        "id_cruce": id_cruce,
        "id_atencion": _s(cruce_row.get("id_atencion")),
        "paciente": {
            "id": _s(cruce_row.get("id_paciente")),
            "edad": float(cruce_row.get("edad", 0) or 0),
            "sexo": _s(cruce_row.get("sexo")),
            "eps": _s(cruce_row.get("eps_atencion")),
        },
        "diagnostico": f"{_s(cruce_row.get('diagnostico_principal_cie10'))} - {_s(cruce_row.get('descripcion_diagnostico'))}",
        "fecha_atencion": _s(cruce_row.get("fecha_atencion")),
        "fecha_facturacion": _s(cruce_row.get("fecha_facturacion")),
        "resultado_ia": resultado_ia,
        "resultado_reglas": alerta_reglas,
        "tipo_alerta_final": tipo_final,
        "modo": "ia+reglas" if modelo_cargado else "solo_reglas",
        "hc_vs_pf": {
            "codigo_cups_hc": _s(cruce_row.get("codigo_cups")),
            "descripcion_hc": _s(cruce_row.get("descripcion")),
            "cantidad_hc": float(cruce_row.get("cantidad_realizada", 0) or 0),
            "codigo_cups_pf": _s(cruce_row.get("codigo_cups_facturado")),
            "descripcion_pf": _s(cruce_row.get("descripcion_servicio_facturado")),
            "cantidad_pf": float(cruce_row.get("cantidad_facturada", 0) or 0),
            "valor_total_pf": float(cruce_row.get("valor_total", 0) or 0),
        },
    }


def _calcular_reglas(row) -> dict:
    cups_hc = str(row.get("codigo_cups", "") or "").strip()
    cups_pf = str(row.get("codigo_cups_facturado", "") or "").strip()
    cant_hc = float(row.get("cantidad_realizada", 0) or 0)
    cant_pf = float(row.get("cantidad_facturada", 0) or 0)
    tiene_hc = cups_hc != "" and cups_hc != "nan"
    tiene_pf = cups_pf != "" and cups_pf != "nan"
    alertas = []

    if tiene_hc and not tiene_pf:
        alertas.append(
            {
                "tipo": "NO_FACTURADO",
                "severidad": "ALTA",
                "descripcion": f"Procedimiento {cups_hc} realizado pero NO facturado (fuga de ingreso).",
            }
        )
    if tiene_pf and not tiene_hc:
        alertas.append(
            {
                "tipo": "SIN_SOPORTE_CLINICO",
                "severidad": "ALTA",
                "descripcion": f"Servicio {cups_pf} facturado sin soporte en historia clinica.",
            }
        )
    if tiene_hc and tiene_pf:
        if cups_hc.upper() != cups_pf.upper():
            alertas.append(
                {
                    "tipo": "CODIGO_NO_COINCIDE",
                    "severidad": "ALTA",
                    "descripcion": f"CUPS HC={cups_hc} vs PF={cups_pf} no coinciden.",
                }
            )
        if abs(cant_hc - cant_pf) > 1e-6:
            alertas.append(
                {
                    "tipo": "CANTIDAD_DISCORDANTE",
                    "severidad": "MEDIA",
                    "descripcion": f"Cantidad HC={cant_hc} vs PF={cant_pf} difieren.",
                }
            )

    inconsistente = len(alertas) > 0
    return {
        "inconsistente": inconsistente,
        "alertas": alertas,
        "tipo_alerta": alertas[0]["tipo"] if alertas else "CONSISTENTE",
        "severidad": alertas[0]["severidad"] if alertas else "NINGUNA",
        "n_alertas": len(alertas),
    }


# ── Endpoint: Analizar Lote de Prefacturas (Importación Masiva) ──

@app.post("/api/prefactura/analizar-lote")
async def analizar_lote(
    file: UploadFile = File(...),
    modelo_selector: str = Form("cnn_local"),
    chunk_size: int = Form(1000),
):
    """
    Procesa un archivo CSV con múltiples prefacturas (100-20,000 registros)
    y las compara masivamente contra la historia clínica.

    El CSV debe tener columnas para agrupar por prefactura (id_prefactura)
    y las columnas estándar de items facturados.

    NOTA: por ahora el lote se evalúa SOLO con el motor de reglas (set de
    CUPS por atención). Los parámetros modelo_selector y chunk_size se
    aceptan para compatibilidad con el frontend pero aún no ejecutan
    modelos de IA por registro.
    """
    # 1. Leer archivo CSV
    try:
        content = await file.read()
        df_lote = pd.read_csv(io.StringIO(content.decode("utf-8-sig")))
    except Exception as e:
        raise HTTPException(400, f"Error al leer CSV: {e}")

    if df_lote.empty:
        raise HTTPException(400, "El archivo CSV está vacío")

    # 2. Validar columnas mínimas
    col_mapping = {
        "codigo_cups_facturado": ["codigo_cups_facturado", "codigo_cups", "cups", "codigo"],
        "descripcion_servicio_facturado": ["descripcion_servicio_facturado", "descripcion", "servicio"],
        "cantidad_facturada": ["cantidad_facturada", "cantidad", "cant"],
        "valor_total": ["valor_total", "valor", "total"],
        "id_prefactura": ["id_prefactura", "prefactura", "id"],
        "id_atencion": ["id_atencion", "atencion"],
        "numero_documento": ["numero_documento", "num_doc", "documento", "cedula"],
        "eps": ["eps", "eps_paciente"],
    }

    def _find_col(df, possible_names):
        for name in possible_names:
            for col in df.columns:
                if col.strip().lower() == name.lower():
                    return col
        return None

    col_cups = _find_col(df_lote, col_mapping["codigo_cups_facturado"])
    col_prefactura = _find_col(df_lote, col_mapping["id_prefactura"])
    col_documento = _find_col(df_lote, col_mapping["numero_documento"])
    col_eps = _find_col(df_lote, col_mapping["eps"])

    if not col_cups:
        raise HTTPException(400, f"CSV debe contener columna 'codigo_cups_facturado'. Columnas: {list(df_lote.columns)}")

    # 3. Agrupar por prefactura (si no hay columna id_prefactura, tratar todo como una sola)
    if col_prefactura:
        grupos = df_lote.groupby(col_prefactura)
    else:
        # Si no hay id_prefactura, crear uno único para todo el lote
        df_lote["_temp_prefactura"] = "LOTE-UNICO"
        grupos = df_lote.groupby("_temp_prefactura")

    # 4. Procesar cada grupo (prefactura)
    resultados_por_prefactura = []
    resumen_global = {
        "total_registros": len(df_lote),
        "procesados": 0,
        "aprobados": 0,
        "rechazados": 0,
        "revision": 0,
        "valor_total": 0,
        "valor_rechazado": 0,
    }

    for id_prefactura, grupo_df in grupos:
        # Extraer datos del paciente del grupo
        pac_doc = ""
        pac_eps = ""
        if col_documento:
            pac_doc = str(grupo_df[col_documento].iloc[0]).strip() if len(grupo_df) > 0 else ""
        if col_eps:
            pac_eps = str(grupo_df[col_eps].iloc[0]).strip() if len(grupo_df) > 0 else ""

        # Normalizar documento
        doc_normalizado = _normalizar_documento(pac_doc)

        # Buscar paciente en BD local
        paciente_info = {}
        if doc_normalizado:
            pac_rows = _query(
                "SELECT id_paciente, tipo_documento, eps_paciente as eps, tipo_afiliacion FROM pacientes WHERE id_paciente=? LIMIT 1",
                (doc_normalizado,),
            )
            if pac_rows:
                paciente_info = pac_rows[0]

        # Procesar items de esta prefactura
        pf_items = []
        for idx, row in grupo_df.iterrows():
            item = {
                "codigo_cups_facturado": _s(row.get(col_cups, "")).strip(),
                "descripcion_servicio_facturado": _s(row.get(_find_col(grupo_df, col_mapping["descripcion_servicio_facturado"]), "")).strip(),
                "cantidad_facturada": _num(row.get(_find_col(grupo_df, col_mapping["cantidad_facturada"]), 1), default=1.0),
                "valor_total": _num(row.get(_find_col(grupo_df, col_mapping["valor_total"]), 0)),
                "id_prefactura": id_prefactura,
                "id_atencion": _s(row.get(_find_col(grupo_df, col_mapping["id_atencion"]), "")).strip(),
            }
            pf_items.append(item)

        # Cruzar con HC usando lógica corregida de set de CUPS por atención
        cruces = []
        
        # Agrupar items por atención para aplicar lógica de set
        atenciones_en_prefactura = {}
        for pf_item in pf_items:
            atn_id = pf_item["id_atencion"]
            if atn_id not in atenciones_en_prefactura:
                atenciones_en_prefactura[atn_id] = []
            atenciones_en_prefactura[atn_id].append(pf_item)
        
        # Para cada atención, obtener sets de CUPS
        for atn_id, items_atencion in atenciones_en_prefactura.items():
            # Set de CUPS facturados en esta atención
            cups_facturados_set = set(item["codigo_cups_facturado"] for item in items_atencion)
            
            # Obtener set de CUPS con soporte clínico de esta atención
            cups_soporte_set = set()
            hc_items_atencion = []
            
            if hc_detalle_df is not None and len(hc_detalle_df) > 0 and atn_id:
                mask_atn = hc_detalle_df["id_atencion"].astype(str).str.contains(atn_id, na=False, regex=False)
                hc_atencion = hc_detalle_df[mask_atn]
                if not hc_atencion.empty:
                    # Filtrar solo los que tienen soporte clínico
                    hc_con_soporte = hc_atencion[hc_atencion["soporte_clinico"].astype(str).str.upper() == "SI"]
                    cups_soporte_set = set(hc_con_soporte["codigo_cups"].astype(str).str.strip())
                    hc_items_atencion = hc_atencion.to_dict('records')
            
            # Comparar sets para cada item de la atención
            for pf_item in items_atencion:
                cups_pf = pf_item["codigo_cups_facturado"]
                
                # Lógica corregida: el código facturado es válido si está en el set de códigos con soporte
                tiene_soporte_en_atencion = cups_pf in cups_soporte_set if cups_soporte_set else False
                
                # Buscar match específico para obtener datos HC
                hc_match = None
                if hc_items_atencion:
                    for hc_item in hc_items_atencion:
                        if str(hc_item.get("codigo_cups", "")).strip() == cups_pf:
                            hc_match = hc_item
                            break
                
                # Determinar resultado con lógica corregida
                if not tiene_soporte_en_atencion:
                    resultado = "INCONSISTENTE"
                    tipo_alerta = "SIN_SOPORTE_CLINICO"
                elif hc_match:
                    cups_hc = str(hc_match.get("codigo_cups", "")).strip()
                    cant_hc = float(hc_match.get("cantidad_realizada", 0) or 0)
                    cant_pf = pf_item["cantidad_facturada"]
                    
                    if abs(cant_hc - cant_pf) > 1e-6:
                        resultado = "INCONSISTENTE"
                        tipo_alerta = "CANTIDAD_DISCORDANTE"
                    else:
                        resultado = "CONSISTENTE"
                        tipo_alerta = "CONSISTENTE"
                else:
                    resultado = "INCONSISTENTE"
                    tipo_alerta = "SIN_SOPORTE_CLINICO"
                
                cruce = {
                    "codigo_cups_pf": cups_pf,
                    "cantidad_pf": pf_item["cantidad_facturada"],
                    "valor_total_pf": pf_item["valor_total"],
                    "resultado": resultado,
                    "tipo_alerta": tipo_alerta,
                    "tiene_soporte_en_atencion": tiene_soporte_en_atencion,
                }
                cruces.append(cruce)
        
        # Detectar fugas de ingreso (CUPS con soporte que no fueron facturados)
        fugas = []
        for atn_id, items_atencion in atenciones_en_prefactura.items():
            if hc_detalle_df is not None and len(hc_detalle_df) > 0 and atn_id:
                mask_atn = hc_detalle_df["id_atencion"].astype(str).str.contains(atn_id, na=False, regex=False)
                hc_atencion = hc_detalle_df[mask_atn]
                if not hc_atencion.empty:
                    hc_con_soporte = hc_atencion[hc_atencion["soporte_clinico"].astype(str).str.upper() == "SI"]
                    cups_facturados_set = set(item["codigo_cups_facturado"] for item in items_atencion)

                    for _, hc_row in hc_con_soporte.iterrows():
                        cups_hc = _s(hc_row["codigo_cups"]).strip()
                        if cups_hc not in cups_facturados_set:
                            fugas.append({
                                "codigo_cups": cups_hc,
                                "descripcion": _s(hc_row.get("descripcion", "")),
                                "cantidad_realizada": _num(hc_row.get("cantidad_realizada", 0)),
                            })

        # Calcular estadísticas de esta prefactura
        n_consistentes = sum(1 for c in cruces if c["resultado"] == "CONSISTENTE")
        n_inconsistentes = sum(1 for c in cruces if c["resultado"] == "INCONSISTENTE")
        n_sin_soporte = sum(1 for c in cruces if c["tipo_alerta"] == "SIN_SOPORTE_CLINICO")
        valor_total_pf = sum(c.get("valor_total_pf", 0) for c in cruces)
        valor_inconsistente = sum(c.get("valor_total_pf", 0) for c in cruces if c["resultado"] == "INCONSISTENTE")

        # Determinar recomendación
        if n_sin_soporte > 0:
            recomendacion = "RECHAZAR"
        elif n_inconsistentes > 0:
            recomendacion = "REVISAR"
        else:
            recomendacion = "APROBAR"

        # Actualizar resumen global
        resumen_global["procesados"] += len(cruces)
        if recomendacion == "APROBAR":
            resumen_global["aprobados"] += 1
        elif recomendacion == "RECHAZAR":
            resumen_global["rechazados"] += 1
        else:
            resumen_global["revision"] += 1
        resumen_global["valor_total"] += valor_total_pf
        resumen_global["valor_rechazado"] += valor_inconsistente

        # Guardar resultado de esta prefactura
        resultados_por_prefactura.append({
            "id_prefactura": id_prefactura,
            "id_paciente": paciente_info.get("id_paciente", pac_doc),
            "recomendacion": recomendacion,
            "total_items": len(cruces),
            "inconsistentes": n_inconsistentes,
            "valor_total": valor_total_pf,
        })

    # 5. Generar archivo de exportación
    timestamp = _os.environ.get("TIMESTAMP", time.strftime("%Y%m%d_%H%M%S"))
    export_filename = f"resultados_lote_{timestamp}.csv"
    export_path = BASE / "data" / "datos_prueba" / "prefacturas" / export_filename

    # Crear DataFrame de resultados
    df_export = pd.DataFrame(resultados_por_prefactura)
    df_export.to_csv(str(export_path), index=False)

    return {
        "resumen_global": resumen_global,
        "resultados_por_prefactura": resultados_por_prefactura,
        "archivo_exportacion": export_filename,
        "ruta_exportacion": str(export_path),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
