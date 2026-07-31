# LINE — Auditor Médico Digital

**Sistema de auditoría de prefacturas** para **Health & Life IPS SAS**.  
Capstone SIC 2025 — Valida que los servicios facturados tengan soporte clínico real en la Historia Clínica.

---

## 📑 Índice

- [Stack Tecnológico](#stack-tecnológico)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Diagrama Visual del Flujo](#-diagrama-visual-del-flujo)
- [Flujo de Trabajo](#flujo-de-trabajo)
- [Instalación y Ejecución](#instalación-y-ejecución)
- [API Endpoints](#api-endpoints)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Variables de Entorno](#variables-de-entorno)
- [Documentación Adicional](#documentación-adicional)
- [Notas para el Equipo](#notas-para-el-equipo)
- [Cumplimiento Normativo](#cumplimiento-normativo)
- [Relación con el Módulo Capstone](#relación-con-el-módulo-capstone)

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Frontend | HTML, Tailwind CSS, JavaScript vanilla |
| Base de Datos | SQLite (linea.db) |
| Modelo IA Local | TensorFlow / Keras — MobileNetV2 sobre imágenes 32×32×3 |
| Modelo IA Externo | NVIDIA Nemotron-3-nano-8B via API |
| Preprocesamiento | pandas, numpy, scikit-learn (StandardScaler, t-SNE) |
| Despliegue | Windows (`start.bat`) / multiplataforma (`start.py`) |

---

## Arquitectura del Sistema

```
                    ┌─────────────────────┐
                    │   Frontend HTML/JS   │
                    │  localhost:8000/docs │
                    └──────────┬──────────┘
                               │ API REST (JSON)
                               ▼
                    ┌─────────────────────┐
                    │  FastAPI Backend     │
                    │   server.py          │
                    └──┬──────┬───────┬───┘
                       │      │       │
              ┌────────▼─┐ ┌──▼────┐ ┌▼──────────┐
              │ SQLite   │ │ Model │ │ NVIDIA     │
              │ linea.db │ │ CNN   │ │ Nemotron   │
              │          │ │ Local │ │ (API ext.) │
              └──────────┘ └───────┘ └────────────┘
```

---

## 📊 Diagrama Visual del Flujo

Para ver el diagrama visual completo del flujo de trabajo del sistema, abre el archivo **[docs/workflow.html](docs/workflow.html)** en tu navegador.

Este diagrama interactivo muestra:
- Flujo completo de entrada de datos
- Verificación y cruce HC vs PF
- Reglas de auditoría y alertas
- Pipeline CNN detallado
- Tabla de alertas del sistema
- Estructura del proyecto

**Ver el diagrama:** [docs/workflow.html](docs/workflow.html)

---

## Flujo de Trabajo

### 1. Entrada
Usuario completa formulario con datos del paciente y sube un archivo:
- **CSV** de prefactura con columnas: `codigo_cups_facturado`, `descripcion_servicio_facturado`, `cantidad_facturada` (y opcionalmente `valor_total`, `id_atencion`, etc.)
- **PDF** de factura (solo para modo Nemotron)

### 2. Verificación BDUA (ADRES)
Consulta la afiliación del paciente en la BDUA mediante web scraping de la consulta ciudadana de ADRES (`backend/adres_scraper.py`, uso académico). Si ADRES no responde (403, captcha, timeout), la auditoría procede en modo contingencia con la base de datos local.

### 3. Cruce HC vs PF
Por cada item facturado, busca en la Historia Clínica (desde `linea.db` o CSV original) un registro con el mismo código CUPS y atención. Detecta:

| Alerta | Significado |
|--------|-------------|
| `SIN_SOPORTE_CLINICO` | Servicio facturado sin registro en HC |
| `CODIGO_NO_COINCIDE` | CUPS facturado ≠ CUPS en HC |
| `CANTIDAD_DISCORDANTE` | Cantidad facturada ≠ cantidad realizada |
| `CONSISTENTE` | Coinciden CUPS, cantidad y hay soporte |
| `NO_FACTURADO` | Procedimiento en HC que no aparece en PF (fuga de ingreso) |

### 4. Modelos de IA (opcionales)

#### CNN MobileNetV2 (Local)
Pipeline tabular → imagen:
1. Imputación de nulos
2. Escalado numérico (StandardScaler)
3. One-Hot Encoding → 111 features dummy
4. Mapeo a grid 32×32 vía t-SNE
5. Normalización global min-max
6. CNN MobileNetV2 → probabilidad de inconsistencia

#### NVIDIA Nemotron-3 (Externo)
LLM que recibe contexto clínico completo (diagnóstico, items PF, items HC, cruces) y genera análisis detallado con recomendación.

### 5. Resultado
- **Resumen**: total items, consistentes, inconsistentes, fugas, valor total, % inconsistencia
- **Recomendación** (jerarquía clínica):
  - **RECHAZAR** si hay items `SIN_SOPORTE_CLINICO` (sin justificación clínica)
  - **REVISAR** si hay discrepancias de datos (`CODIGO_NO_COINCIDE`, `CANTIDAD_DISCORDANTE`)
  - **APROBAR** si todo es consistente
- **Detalle por cruce**: alertas, severidad, soporte clínico
- **Modelos**: predicciones CNN, XGBoost y/o análisis Nemotron

---

## Instalación y Ejecución

### Requisitos
- Python 3.10+
- Git (opcional)

### Windows
```batch
start.bat
```
El script:
1. Detecta Python
2. Verifica modelos (`models/auditor_medico_cnn.keras`, `models/artefactos_preprocesamiento.pkl`)
3. Crea/activa entorno virtual
4. Instala dependencias
5. Crea `linea.db` desde `data/dataset_maestro.csv` (si no existe)
6. Inicia FastAPI en puerto 8000
7. Abre `frontend/index.html`

### Linux / macOS
```bash
python3 start.py
```
(`start.py` es multiplataforma; en Windows también puede usarse `python start.py` en lugar de `start.bat`.)

### Manual
```bash
pip install -r requirements.txt
python build_db.py
uvicorn server:app --host 0.0.0.0 --port 8000
```
Abrir `frontend/index.html` en el navegador.

---

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del servidor y modelo |
| GET | `/api/modelos` | Lista modelos IA disponibles |
| GET | `/api/pacientes?q=` | Buscar pacientes |
| GET | `/api/paciente/{id}` | Detalle paciente + atenciones |
| POST | `/api/paciente/verificar-adres` | Consultar BDUA |
| GET | `/api/atenciones?pac_id=` | Listar atenciones |
| GET | `/api/cruces-atencion/{id}` | Cruces de una atención |
| GET | `/api/auditar/{id_cruce}` | Auditoría detallada de un cruce |
| POST | `/api/prefactura/analizar` | **Principal** — subir CSV/PDF y analizar una prefactura |
| POST | `/api/prefactura/analizar-lote` | **Importación masiva** — analizar múltiples prefacturas en lote |

Documentación interactiva en `http://localhost:8000/docs`

---

## Estructura del Proyecto

```
LINE/
├── server.py                         Backend FastAPI
├── preprocesamiento.py               Pipeline tabular → imagen para CNN
├── build_db.py                       Construye SQLite desde CSV maestro
├── requirements.txt
├── start.bat / start.py              Scripts de inicio
├── .env.example                      Ejemplo de variables de entorno
├── linea.db                          Base SQLite (3126 cruces, 294 pacientes)
├── data/
│   ├── dataset_maestro.csv           Datos etiquetados HC vs PF
│   ├── 03_historia_clinica_detalle.csv  HC detalle (datos de prueba)
│   ├── 04_prefactura.csv             Prefacturas (datos de prueba)
│   ├── db_meta.json                  Metadatos de la BD
│   └── datos_prueba/                 Archivos de prueba adicionales
├── models/
│   ├── modelo_xgboost.pkl            XGBoost entrenado (modelo en producción)
│   ├── artefactos_xgboost.pkl        Artefactos XGBoost (scaler, encoders)
│   ├── auditor_medico_cnn.keras      CNN MobileNetV2 entrenado (referencia)
│   └── artefactos_preprocesamiento.pkl  Parámetros del pipeline CNN
├── backend/
│   ├── adres_scraper.py              Web scraping BDUA ADRES
│   └── xgboost_inferencia.py         Inferencia XGBoost
├── frontend/
│   ├── index.html                    Interfaz de usuario
│   └── app.js                        Lógica del frontend
├── tests/
│   ├── test_r1_preprocesamiento.py   Tests de preprocesamiento
│   └── e2e_basico.py                 Test end-to-end básico
├── docs/
│   ├── README.md                     Documentación detallada
│   ├── MIGRATION.md                  Guía de migración a producción
│   └── workflow.html                 Diagrama visual del flujo
└── venv/                             Entorno virtual Python
```

---

## Variables de Entorno

| Variable | Descripción |
|----------|-------------|
| `NVIDIA_API_KEY` | API key para NVIDIA Nemotron |
| `NVIDIA_MODEL` | Model ID de NVIDIA (default en `server.py`: `nvidia/nemotron-3-nano-30b-a3b`; `.env.example` trae `nvidia/nemotron-3-nano-8b-v1`) |

La verificación BDUA no requiere API key: se realiza por web scraping de la consulta ciudadana de ADRES (`backend/adres_scraper.py`).

---

## Documentación Adicional

- **[docs/README.md](docs/README.md)** - Documentación técnica detallada
- **[docs/MIGRATION.md](docs/MIGRATION.md)** - Guía de migración a producción (SQL Server, MySQL)
- **[docs/workflow.html](docs/workflow.html)** - Diagrama visual interactivo del flujo

---

## Notas para el Equipo

- **CUPS**: Código Único de Procedimientos en Salud — clasificación oficial colombiana de procedimientos médicos.
- **HC**: Historia Clínica (lo que realmente se realizó al paciente).
- **PF**: Prefactura (lo que la IPS pretende cobrar).
- **BDUA**: Base de Datos Única de Afiliados — administrada por ADRES, entidad gubernamental colombiana.
- **Nemotron**: Modelo de lenguaje de NVIDIA, se usa como alternativa al modelo CNN local para análisis con razonamiento clínico.
- **Fuga de Ingreso**: Procedimiento realizado y registrado en HC que no aparece facturado en la prefactura — representa pérdida económica para la IPS.

---

## Cumplimiento Normativo

| Normativa | Estado | Documento |
|-----------|--------|----------|
| **Ley 1581 de 2012** (Protección de Datos Personales) | ⚠️ Parcial (documentación lista, controles técnicos en progreso) | [docs/AVISO_PRIVACIDAD.md](docs/AVISO_PRIVACIDAD.md) |
| **ISO/IEC 27001:2022** (Seguridad de la Información) | ⚠️ Parcial (Fase 1 en implementación) | [docs/POLITICA_SEGURIDAD.md](docs/POLITICA_SEGURIDAD.md) |

> **⚠️ Aviso legal:** Este proyecto utiliza **datos sintéticos** para fines académicos y de demostración (Capstone SIC 2025).
> No contiene datos reales de pacientes. Para producción con datos reales, se requiere implementar
> los controles descritos en [docs/ANALISIS_RIESGOS.md](docs/ANALISIS_RIESGOS.md) y cumplir con la
> [Ley 1581 de 2012](https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=37481)
> e [ISO/IEC 27001:2022](https://www.iso.org/standard/27001).

---

---

## Relación con el Módulo Capstone

Este repositorio (**LINE**) es la **aplicación funcional** del proyecto; el análisis de datos, el entrenamiento de los modelos y las figuras de resultados viven en el repositorio hermano **Capstone** ([github.com/jaoliverosm/Capstone-](https://github.com/jaoliverosm/Capstone-)).

| Módulo | Rol | Contenido clave |
|--------|-----|-----------------|
| **LINE** (este repo) | Aplicación: FastAPI + frontend + inferencia | `server.py`, `frontend/`, `models/` |
| **Capstone** (repo hermano) | Ciencia de datos: notebooks 01–08, métricas oficiales | `Capstone/outputs/reports/metrics.json`, `Capstone/documentacion/metricas_oficiales.md` |

---

*Proyecto desarrollado para Health & Life IPS SAS — Capstone Sistemas Inteligentes y Computacionales 2025*