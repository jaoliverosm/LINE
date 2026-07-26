# LINE — Auditor Médico Digital

**Sistema de auditoría de prefacturas** para **Health & Life IPS SAS**.  
Capstone SIC 2025 — Valida que los servicios facturados tengan soporte clínico real en la Historia Clínica.

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
- **Recomendación**: APROBAR (<30% inconsistencias), REVISAR (>0%), RECHAZAR (>30%)
- **Detalle por cruce**: alertas, severidad, soporte clínico
- **Modelos**: predicciones CNN y/o análisis Nemotron

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
| POST | `/api/prefactura/analizar` | **Principal** — subir CSV/PDF y analizar |

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
├── linea.db                          Base SQLite (3126 cruces, 294 pacientes)
├── data/
│   ├── dataset_maestro.csv           Datos etiquetados HC vs PF
│   └── db_meta.json                  Metadatos de la BD
├── models/
│   ├── auditor_medico_cnn.keras      CNN MobileNetV2 entrenado
│   └── artefactos_preprocesamiento.pkl  Parámetros del pipeline
├── frontend/
│   ├── index.html                    Interfaz de usuario
│   └── app.js                        Lógica del frontend
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

*Proyecto desarrollado para Health & Life IPS SAS — Capstone Sistemas Inteligentes y Computacionales 2025*