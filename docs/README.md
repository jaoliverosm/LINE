
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
| Despliegue | Windows (.bat) / Linux/macOS (.sh) |

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

Para ver el diagrama visual completo del flujo de trabajo del sistema, abre el archivo **[workflow.html](workflow.html)** en tu navegador.

Este diagrama interactivo muestra:
- Flujo completo de entrada de datos
- Verificación y cruce HC vs PF
- Reglas de auditoría y alertas
- Pipeline CNN detallado
- Tabla de alertas del sistema
- Estructura del proyecto

**Ver el diagrama:** [workflow.html](workflow.html)

---

## Flujo de Trabajo

### 1. Entrada
Usuario completa formulario con datos del paciente y sube un archivo:
- **CSV** de prefactura con columnas: `codigo_cups_facturado`, `descripcion_servicio_facturado`, `cantidad_facturada` (y opcionalmente `valor_total`, `id_atencion`, etc.)
- **PDF** de factura (solo para modo Nemotron)

### 2. Verificación BDUA (ADRES)
Consulta la API de Apitude para verificar afiliación activa del paciente en la BD Única de Afiliados. Si no hay API key, procede con datos locales.

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
chmod +x start.sh
./start.sh
```

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
├── start.bat / start.sh              Scripts de inicio
├── linea.db                          Base SQLite (3126 cruces, 294 pacientes)
├── data/
│   ├── dataset_maestro.csv           Datos etiquetados HC vs PF
│   ├── 03_historia_clinica_detalle.csv Historia clínica detalle (datos de prueba)
│   ├── 04_prefactura.csv             Prefacturas (datos de prueba)
│   ├── db_meta.json                  Metadatos de la BD
│   └── datos_prueba/                 Archivos de prueba adicionales
├── models/
│   ├── auditor_medico_cnn.keras      CNN MobileNetV2 entrenado
│   └── artefactos_preprocesamiento.pkl  Parámetros del pipeline
├── frontend/
│   ├── index.html                    Interfaz de usuario
│   └── app.js                        Lógica del frontend
├── docs/
│   ├── README.md                     Documentación técnica
│   ├── MIGRATION.md                  Guía de migración a producción
│   └── workflow.html                 Diagrama visual del flujo
└── venv/                             Entorno virtual Python
```

---

## Modelo CNN en detalle

El modelo `auditor_medico_cnn.keras` es una **MobileNetV2** que recibe imágenes de **32×32×3** píxeles.

### Pipeline de preprocesamiento (`preprocesamiento.py`)

```
CSV / JSON
    │
    ▼
Imputación de nulos (numéricos → 0, categóricos → "SIN_DATO")
    │
    ▼
Escalado numérico (6 columnas: edad, cantidades, valor, mes)
    │
    ▼
One-Hot Encoding (13 columnas categóricas → 111 features)
    │
    ▼
Posicionamiento t-SNE → grid 32×32 (cada feature cae en una celda)
    │
    ▼
Normalización global min-max (usando mín/max del train)
    │
    ▼
CNN MobileNetV2 → probabilidad [0, 1]
    │
    ▼
Threshold (guardado en .pkl) → 0: CONSISTENTE / 1: INCONSISTENTE
```

### Columnas usadas

**Numéricas** (6): `edad`, `cantidad_realizada`, `cantidad_facturada`, `valor_unitario`, `valor_total`, `mes_atencion`

**Categóricas** (13 → 111 dummies): `sexo`, `eps_atencion`, `tipo_afiliacion`, `ciudad`, `tipo_documento`, `tipo_atencion`, `sede`, `tipo_item`, `soporte_clinico`, `grupo_etario`, `diagnostico_principal_cie10`, `medico_tratante`, `profesional_responsable`

---

## Dataset

| Métrica | Valor |
|---------|-------|
| Total cruces | 3,126 |
| Pacientes únicos | 294 |
| Atenciones únicas | 1,200 |
| Consistentes | 2,477 (79.2%) |
| Inconsistentes | 649 (20.8%) |

---

## Variables de Entorno

| Variable | Descripción |
|----------|-------------|
| `NVIDIA_API_KEY` | API key para NVIDIA Nemotron |
| `NVIDIA_MODEL` | Model ID de NVIDIA (default: `nvidia/nemotron-3-nano-8b-v1`) |

La API key de **Apitude** (BDUA) se configura directamente en `server.py` (`APITUDE_KEY`).

---

## Migración a Producción

El proyecto está configurado para usar SQLite por defecto en desarrollo. Para migrar a un servidor de base de datos en producción (SQL Server o MySQL), siga la guía detallada en `docs/MIGRATION.md`.

### Cambios rápidos necesarios:

1. **Configurar .env**: Copiar `.env.example` a `.env` y configurar las variables de base de datos
2. **Modificar server.py**: Adaptar la función `_query()` para usar el motor de BD deseado
3. **Cambiar rutas de archivos**: Actualizar las rutas de CSV en `server.py` y `build_db.py` para producción
4. **Configurar frontend**: Cambiar la URL de API en `frontend/app.js`

### Instrucciones para cambiar el motor de base de datos:

#### SQLite (por defecto - desarrollo)
- No requiere configuración adicional
- Archivo: `linea.db` en el directorio raíz

#### SQL Server (producción)
1. Instalar dependencia: `pip install pyodbc`
2. Configurar `.env`:
   ```
   DB_ENGINE=sqlserver
   DB_SERVER=your_server_name
   DB_DATABASE=your_database_name
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_DRIVER=ODBC Driver 17 for SQL Server
   ```
3. Modificar `server.py` función `_query()` para usar `pyodbc`
4. Crear tablas en SQL Server usando el script en `docs/MIGRATION.md`

#### MySQL (producción)
1. Instalar dependencia: `pip install mysql-connector-python`
2. Configurar `.env`:
   ```
   DB_ENGINE=mysql
   DB_HOST=localhost
   DB_PORT=3306
   DB_DATABASE=your_database_name
   DB_USER=your_username
   DB_PASSWORD=your_password
   ```
3. Modificar `server.py` función `_query()` para usar `mysql-connector-python`
4. Crear tablas en MySQL usando el script en `docs/MIGRATION.md`

### Cambio de rutas de archivos en producción:

Los siguientes archivos tienen rutas que deben actualizarse para producción:

- **server.py** (líneas 84-85): `HC_DETALLE_PATH` y `PF_ORIGINAL_PATH` - rutas a CSV externos
- **build_db.py** (líneas 22-23): `CSV_PATH` y `DB_PATH` - rutas de dataset y base de datos
- **preprocesamiento.py** (líneas 28-29): `ARTIFACTS_PATH` y `MODEL_PATH` - rutas de modelos
- **frontend/app.js** (línea 6): `API` - URL del servidor backend

Consulte `docs/MIGRATION.md` para instrucciones detalladas paso a paso.

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
