"""
ADRES BDUA Web Scraper
======================
Extrae datos de afiliacion desde la consulta ciudadana de ADRES:
  https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/ConsultarAfiliadoWeb_2.aspx

USO ACADEMICO SOLAMENTE (Samsung Innovation Campus - Capstone).
- NO usar en produccion.
- NO consultar datos de terceros sin consentimiento.
- Respeta rate-limiting (3-5s entre consultas).
- User-Agent identificable (no se falsea como navegador).
- Para produccion real, usar SAT (Sistema de Afiliacion Transaccional):
  https://miseguridadsocial.gov.co

ADVERTENCIA: El robots.txt de aplicaciones.adres.gov.co bloquea acceso
automatizado. Este scraper es solo una prueba de concepto academica.
Si el sitio devuelve 403, captcha, o bloqueo, el scraper retorna
{encontrado: false, error: "BDUA_NO_DISPONIBLE"}.

Dependencias: requests, beautifulsoup4, lxml
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from typing import Optional

import requests
import urllib3
from bs4 import BeautifulSoup

# ── Silenciar warnings SSL (ADRES tiene certificado autofirmado) ──
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Constantes ──────────────────────────────────────────────────────
BASE_URL = "https://aplicaciones.adres.gov.co/BDUA_Internet/Pages"
FORM_URL = f"{BASE_URL}/ConsultarAfiliadoWeb_2.aspx"
RESPONSE_URL = f"{BASE_URL}/RespuestaConsulta.aspx"

# Mapeo tipos de documento del sistema LINE -> formulario ADRES
TIPO_DOC_MAP = {
    "CC": "CC",
    "TI": "TI",
    "CE": "CE",
    "RC": "RC",
    "PA": "PA",
    "NU": "NU",
    "AS": "AS",
    "MS": "MS",
    "CD": "CD",
    "CN": "CN",
}

# Headers con User-Agent identificable (NO falsea navegador comun)
HEADERS = {
    "User-Agent": "LINE-Auditor-Medico/2.0 (Academic Capstone Samsung Innovation Campus; +https://github.com/line-project)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Referer": "https://www.adres.gov.co/consulte-su-eps",
    "DNT": "1",
    "Connection": "keep-alive",
}

INTERVALO_MINIMO = 3.5  # segundos minimos entre consultas (rate limiting)

# ── Cache en memoria ────────────────────────────────────────────────
_cache: dict[str, dict] = {}
_ultima_consulta: float = 0.0


def _key(tipo_doc: str, num_doc: str) -> str:
    return hashlib.md5(f"{tipo_doc}_{num_doc}".encode()).hexdigest()


def _rate_limit():
    global _ultima_consulta
    ahora = time.time()
    diff = ahora - _ultima_consulta
    if diff < INTERVALO_MINIMO:
        time.sleep(INTERVALO_MINIMO - diff)
    _ultima_consulta = time.time()


def _extraer_viewstates(html: str) -> dict:
    """Extrae los tokens ASP.NET necesarios para el POST."""
    soup = BeautifulSoup(html, "lxml")
    vs = soup.find("input", {"name": "__VIEWSTATE"})
    vg = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})
    ev = soup.find("input", {"name": "__EVENTVALIDATION"})
    et = soup.find("input", {"name": "__EVENTTARGET"})
    ea = soup.find("input", {"name": "__EVENTARGUMENT"})

    return {
        "__VIEWSTATE": vs.get("value", "") if vs else "",
        "__VIEWSTATEGENERATOR": vg.get("value", "") if vg else "",
        "__EVENTVALIDATION": ev.get("value", "") if ev else "",
        "__EVENTTARGET": et.get("value", "") if et else "",
        "__EVENTARGUMENT": ea.get("value", "") if ea else "",
    }


def _parsear_respuesta_adres(html: str) -> dict:
    """
    Parsea el HTML de RespuestaConsulta.aspx para extraer los datos
    de afiliacion del ciudadano.

    Returns:
        dict con keys: encontrado, nombres, apellidos, tipo_documento,
                       numero_documento, eps, regimen, estado_afiliacion,
                       fecha_nacimiento, departamento, municipio,
                       fecha_afiliacion, fecha_finalizacion
    """
    soup = BeautifulSoup(html, "lxml")

    # Buscar la tabla de resultados. ADRES usa ASP.NET WebForms con
    # tablas anidadas. Buscamos la tabla principal de datos.
    # Estrategia: buscar por texto "Nombre" o "Documento" en labels
    resultado = {"encontrado": False}

    # 1. Buscar mensajes de error ("no existe", "no encontrado", etc.)
    texto_completo = soup.get_text(separator=" ", strip=True)
    
    if any(p in texto_completo.upper() for p in [
        "NO EXISTEN DATOS ACTIVOS",
        "NO EXISTE",
        "NO ENCONTRADO",
        "SIN REGISTRO",
        "DATOS NO ENCONTRADOS",
        "NO SE ENCONTRARON",
        "NO POSEE REGISTRO",
    ]):
        return {"encontrado": False, "mensaje": "No existen datos activos en la BDUA para ese documento"}

    # 2. Buscar tabla de resultados. ADRES tipicamente usa:
    #    <table> con rows de label:valor
    #    Buscar por patrones conocidos
    tabla_datos = None

    # Estrategia A: Buscar tabla que contenga "Nombre" o "Tipo de identificacion"
    for table in soup.find_all("table"):
        texto_tabla = table.get_text(separator=" ", strip=True)
        if any(p in texto_tabla.upper() for p in [
            "NOMBRE", "TIPO DE IDENTIFICACION", "NUMERO DE IDENTIFICACION",
            "FECHA DE NACIMIENTO", "EPS", "REGIMEN", "ESTADO DE AFILIACION"
        ]):
            tabla_datos = table
            break

    if tabla_datos is None:
        # Estrategia B: Buscar divs con clases especificas de ADRES
        for div in soup.find_all("div", class_=re.compile(r"(result|datos|info|contenido)", re.I)):
            texto_div = div.get_text(separator=" ", strip=True)
            if any(p in texto_div.upper() for p in [
                "NOMBRE", "IDENTIFICACION", "AFILIACION"
            ]):
                tabla_datos = div
                break

    if tabla_datos is None:
        # Estrategia C: Extraer por labels en spans o labels
        # Buscar pares label:valor en todo el documento
        # ADRES a veces usa <span class="label">...</span> <span class="valor">...</span>
        pares = _extraer_pares_label_valor(soup)
        if pares:
            resultado["encontrado"] = True
            resultado.update(pares)
            return resultado

        # No se encontro estructura conocida
        return {
            "encontrado": False,
            "error": "ESTRUCTURA_NO_RECONOCIDA",
            "html_preview": texto_completo[:500],
        }

    # Extraer datos de la tabla
    resultado["encontrado"] = True
    rows = tabla_datos.find_all("tr")
    for row in rows:
        celdas = row.find_all(["td", "th"])
        if len(celdas) >= 2:
            label = celdas[0].get_text(strip=True).upper()
            valor = celdas[1].get_text(strip=True)
            _asignar_campo(resultado, label, valor)

    # Extraer datos de afiliación del texto plano (si no se encontró EPS en tabla)
    if not resultado.get("eps"):
        # Buscar la sección "Datos de afiliación"
        if "Datos de afiliación" in texto_completo:
            # Extraer el texto después de "Datos de afiliación"
            idx_afiliacion = texto_completo.find("Datos de afiliación")
            texto_afiliacion = texto_completo[idx_afiliacion:]
            
            # Usar regex para extraer los valores
            # Simplificar: buscar directamente los valores después de "TIPO DE AFILIADO"
            import re
            # Normalizar el texto para eliminar saltos de línea y espacios extra
            texto_afiliacion_normalizado = re.sub(r'\s+', ' ', texto_afiliacion).strip()
            
            # Buscar patrón simplificado: solo buscar después de "TIPO DE AFILIADO"
            match = re.search(r'TIPO DE AFILIADO\s+(.+?)(?=Fecha de Impresión|$)', texto_afiliacion_normalizado, re.IGNORECASE)
            if match:
                valores_texto = match.group(1)
                # Los valores están separados por espacios, pero algunos tienen múltiples palabras
                # Necesitamos identificar cuáles son los valores basándonos en el contexto
                # El primer valor es estado, segundo es entidad (EPS), tercero es régimen, etc.
                partes = valores_texto.split()
                if len(partes) >= 4:
                    # El estado suele ser corto (ACTIVO, INACTIVO)
                    estado = partes[0]
                    # La entidad (EPS) puede tener múltiples palabras
                    # Buscamos el régimen que suele ser CONTRIBUTIVO o SUBSIDIADO
                    regimen_idx = -1
                    for i, parte in enumerate(partes):
                        if parte.upper() in ["CONTRIBUTIVO", "SUBSIDIADO"]:
                            regimen_idx = i
                            break
                    
                    if regimen_idx > 1:
                        # La EPS está entre el estado y el régimen
                        eps_parts = partes[1:regimen_idx]
                        eps = " ".join(eps_parts)
                        resultado["eps"] = eps
                        resultado["regimen"] = partes[regimen_idx]
                        resultado["estado_afiliacion"] = estado

    # Si no se encontraron datos por tabla, intentar pares label:valor
    if not any(k in resultado for k in ["nombres", "eps", "tipo_documento"]):
        pares = _extraer_pares_label_valor(soup)
        if pares:
            resultado.update(pares)

    # Validar que los datos extraídos sean válidos
    # Si no tiene nombre o EPS válidos, probablemente es un falso positivo
    if resultado.get("encontrado"):
        nombre = resultado.get("nombres", "").strip()
        eps = resultado.get("eps", "").strip()
        
        # Validar que no sean textos genéricos del formulario
        invalidos = ["fecha", "actualizacion", "actualización", "seleccione", "consultar", "actualización"]
        eps_lower = eps.lower().replace(":", "").replace(" ", "")
        nombre_lower = nombre.lower().replace(":", "").replace(" ", "")
        
        # Si tiene nombre válido, considerar encontrado (EPS puede estar vacío)
        if len(nombre) >= 3 and not any(inv in nombre_lower for inv in invalidos):
            # Datos válidos - mantener encontrado=True
            pass
        elif any(inv in eps_lower for inv in invalidos) or len(eps) < 3:
            resultado["encontrado"] = False
            resultado["error"] = "DATOS_INVALIDOS"
            resultado["mensaje"] = "Datos extraídos no válidos (probablemente estructura de formulario)"
        elif len(nombre) < 3 or any(inv in nombre_lower for inv in invalidos):
            resultado["encontrado"] = False
            resultado["error"] = "DATOS_INVALIDOS"
            resultado["mensaje"] = "Nombre extraído no válido"

    return resultado


def _extraer_pares_label_valor(soup: BeautifulSoup) -> dict:
    """
    Intenta extraer pares label:valor del HTML de ADRES.
    Busca por spans, divs, o td con patrones de texto.
    """
    datos = {}

    # Buscar todos los textos relevantes
    texto = soup.get_text(separator="\n", strip=True)
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]

    mapeo_labels = {
        "NOMBRE": "nombres",
        "APELLIDO": "apellidos",
        "TIPO DE IDENTIFICACION": "tipo_documento",
        "NUMERO DE IDENTIFICACION": "numero_documento",
        "FECHA DE NACIMIENTO": "fecha_nacimiento",
        "DEPARTAMENTO": "departamento",
        "MUNICIPIO": "municipio",
        "EPS": "eps",
        "REGIMEN": "regimen",
        "ESTADO DE AFILIACION": "estado_afiliacion",
        "FECHA DE AFILIACION": "fecha_afiliacion",
        "FECHA DE FINALIZACION": "fecha_finalizacion",
    }

    for i, linea in enumerate(lineas):
        linea_upper = linea.upper()
        for label, campo in mapeo_labels.items():
            if label in linea_upper and campo not in datos:
                # El valor suele estar en la siguiente linea
                if i + 1 < len(lineas):
                    valor = lineas[i + 1]
                    # Limpiar: si el valor tambien contiene un label, saltar
                    if not any(l in valor.upper() for l in mapeo_labels):
                        datos[campo] = valor

    return datos


def _asignar_campo(resultado: dict, label: str, valor: str):
    """Asigna un valor al campo correcto segun el label de ADRES."""
    # Normalizar label: quitar tildes y caracteres especiales
    import unicodedata
    label_normalizado = unicodedata.normalize('NFKD', label).encode('ASCII', 'ignore').decode('ASCII').upper()
    
    if "NOMBRE" in label_normalizado and "nombres" not in resultado:
        resultado["nombres"] = valor
    elif "APELLIDO" in label_normalizado and "apellidos" not in resultado:
        resultado["apellidos"] = valor
    elif "TIPO DE IDENTIFICACION" in label_normalizado:
        resultado["tipo_documento"] = valor
    elif "NUMERO DE IDENTIFICACION" in label_normalizado:
        resultado["numero_documento"] = valor
    elif "FECHA DE NACIMIENTO" in label_normalizado:
        resultado["fecha_nacimiento"] = valor
    elif "DEPARTAMENTO" in label_normalizado:
        resultado["departamento"] = valor
    elif "MUNICIPIO" in label_normalizado:
        resultado["municipio"] = valor
    elif label_normalizado == "EPS" or "EPS" in label_normalizado:
        resultado["eps"] = valor
    elif "REGIMEN" in label_normalizado:
        resultado["regimen"] = valor
    elif "ESTADO DE AFILIACION" in label or "ESTADO" in label:
        resultado["estado_afiliacion"] = valor
    elif "FECHA DE AFILIACION EFECTIVA" in label:
        resultado["fecha_afiliacion"] = valor
    elif "FECHA DE FINALIZACION" in label:
        resultado["fecha_finalizacion"] = valor


def consultar_afiliacion(
    tipo_documento: str,
    numero_documento: str,
) -> dict:
    """
    Consulta la afiliacion de un ciudadano en ADRES/BDUA mediante
    web scraping de la consulta ciudadana.

    Args:
        tipo_documento: Codigo del tipo de documento (CC, TI, CE, RC, etc.)
        numero_documento: Numero de identificacion (solo digitos)

    Returns:
        dict con:
          - encontrado (bool): True si se encontraron datos
          - fuente (str): "adres_bdua" si se obtuvieron datos, 
                         "adres_no_disponible" si no se pudo consultar
          - datos del afiliado si encontrado es True
          - error: codigo de error si aplica
          - mensaje: mensaje descriptivo

    Posibles errores:
      - BDUA_NO_DISPONIBLE: Sitio bloquea (403), timeout, o error de red
      - CAPTCHA_REQUERIDO: El sitio requiere resolver captcha
      - ESTRUCTURA_NO_RECONOCIDA: El HTML cambio y no se pudo parsear
      - DOCUMENTO_INVALIDO: Tipo de documento no soportado
    """
    tipo_normalizado = tipo_documento.upper().strip()
    num_limpio = numero_documento.strip()

    if not num_limpio:
        return {
            "encontrado": False,
            "fuente": "adres_no_disponible",
            "error": "DOCUMENTO_INVALIDO",
            "mensaje": "Numero de documento requerido",
        }

    adres_tipo = TIPO_DOC_MAP.get(tipo_normalizado)
    if not adres_tipo:
        return {
            "encontrado": False,
            "fuente": "adres_no_disponible",
            "error": "DOCUMENTO_INVALIDO",
            "mensaje": f"Tipo de documento '{tipo_documento}' no soportado por ADRES",
        }

    # ── Verificar cache ──
    cache_key = _key(adres_tipo, num_limpio)
    cached = _cache.get(cache_key)
    if cached is not None:
        # Cache valido por 5 minutos
        if time.time() - cached.get("_timestamp", 0) < 300:
            result = dict(cached)
            result.pop("_timestamp", None)
            return result

    # ── Rate limiting ──
    _rate_limit()

    session = requests.Session()
    session.verify = False
    session.headers.update(HEADERS)

    try:
        # ── PASO 1: GET al formulario ──
        resp_form = session.get(FORM_URL, timeout=20)
        if resp_form.status_code == 403:
            entry = {
                "_timestamp": time.time(),
                "encontrado": False,
                "fuente": "adres_no_disponible",
                "error": "BDUA_NO_DISPONIBLE",
                "mensaje": "ADRES bloquea consultas automatizadas (403). La auditoria procede con datos locales.",
            }
            _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
            # Devolver copia sin _timestamp
            entry.pop("_timestamp")
            return entry

        if resp_form.status_code != 200:
            entry = {
                "_timestamp": time.time(),
                "encontrado": False,
                "fuente": "adres_no_disponible",
                "error": "BDUA_NO_DISPONIBLE",
                "mensaje": f"ADRES respondio {resp_form.status_code}. Usando datos locales.",
            }
            _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
            entry.pop("_timestamp")
            return entry

        # ── PASO 2: Extraer VIEWSTATE tokens ──
        viewstates = _extraer_viewstates(resp_form.text)

        # Verificar si hay CAPTCHA (reCAPTCHA)
        if "recaptcha" in resp_form.text.lower() or "g-recaptcha" in resp_form.text:
            # Intentar de todas formas - a veces el captcha es opcional
            pass

        # ── PASO 3: POST con datos del formulario ──
        form_data = {
            "tipoDoc": adres_tipo,
            "txtNumDoc": num_limpio,
            "btnConsultar": "Consultar",
            **viewstates,
        }

        resp_post = session.post(
            FORM_URL,
            data=form_data,
            timeout=25,
            allow_redirects=False,  # No seguir redirect para capturar token
        )

        # ── PASO 4: Detectar redirect JavaScript (window.open) ──
        # ADRES usa window.open para abrir la respuesta en nueva ventana
        window_open_match = re.search(r"window\.open\(['\"]([^'\"]+)['\"]", resp_post.text)
        if window_open_match:
            redirect_url = window_open_match.group(1)
            
            if redirect_url.startswith("/"):
                redirect_url = f"https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/{redirect_url.lstrip('/')}"
            elif not redirect_url.startswith("http"):
                redirect_url = f"{BASE_URL}/{redirect_url.lstrip('/')}"
            
            resp_result = session.get(redirect_url, timeout=20)
            
            # ── PASO 5: Parsear respuesta ──
            resultado = _parsear_respuesta_adres(resp_result.text)
            resultado["fuente"] = "adres_bdua" if resultado.get("encontrado") else "adres_sin_datos"
            resultado["url_consulta"] = redirect_url

            # Cachear
            cache_entry = dict(resultado, _timestamp=time.time())
            _cache[cache_key] = cache_entry

            return resultado

        # Si no hubo redirect, revisar si el POST mismo devolvio la respuesta
        if resp_post.status_code == 200:
            resultado = _parsear_respuesta_adres(resp_post.text)
            resultado["fuente"] = "adres_bdua" if resultado.get("encontrado") else "adres_sin_datos"

            cache_entry = dict(resultado, _timestamp=time.time())
            _cache[cache_key] = cache_entry
            return resultado

        # Otro codigo
        entry = {
            "_timestamp": time.time(),
            "encontrado": False,
            "fuente": "adres_no_disponible",
            "error": "BDUA_NO_DISPONIBLE",
            "mensaje": f"ADRES respondio {resp_post.status_code} inesperado.",
        }
        _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
        entry.pop("_timestamp")
        return entry

    except requests.exceptions.Timeout:
        entry = {
            "_timestamp": time.time(),
            "encontrado": False,
            "fuente": "adres_no_disponible",
            "error": "BDUA_NO_DISPONIBLE",
            "mensaje": "Timeout en consulta ADRES. La auditoria procede con datos locales.",
        }
        _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
        entry.pop("_timestamp")
        return entry

    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        if "SSL" in error_msg or "certificate" in error_msg:
            entry = {
                "_timestamp": time.time(),
                "encontrado": False,
                "fuente": "adres_no_disponible",
                "error": "BDUA_NO_DISPONIBLE",
                "mensaje": "Error SSL al conectar con ADRES. La auditoria procede con datos locales.",
            }
        else:
            entry = {
                "_timestamp": time.time(),
                "encontrado": False,
                "fuente": "adres_no_disponible",
                "error": "BDUA_NO_DISPONIBLE",
                "mensaje": "Error de conexion con ADRES. La auditoria procede con datos locales.",
            }
        _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
        entry.pop("_timestamp")
        return entry

    except Exception as e:
        entry = {
            "_timestamp": time.time(),
            "encontrado": False,
            "fuente": "adres_no_disponible",
            "error": "BDUA_NO_DISPONIBLE",
            "mensaje": f"Error inesperado consultando ADRES: {e}",
        }
        _cache[cache_key] = dict(entry)  # copia: el pop de abajo no debe vaciar el timestamp cacheado
        entry.pop("_timestamp")
        return entry


def limpiar_cache():
    """Limpia la cache de consultas."""
    global _cache
    _cache = {}


# ── Test directo ────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ADRES BDUA Scraper - Test")
    print("=" * 60)

    # Test 1: Documento sin registro
    print("\n[Test 1] Documento ficticio (CC 0000000000):")
    r1 = consultar_afiliacion("CC", "0000000000")
    print(f"  {json.dumps(r1, indent=2, ensure_ascii=False)}")

    # Test 2: Documento invalido
    print("\n[Test 2] Tipo documento invalido (XX):")
    r2 = consultar_afiliacion("XX", "12345")
    print(f"  {json.dumps(r2, indent=2, ensure_ascii=False)}")

    print("\nFIN")
