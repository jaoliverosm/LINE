
# LINE — Auditor Médico Digital

**Sistema de auditoría de prefacturas** para **Health & Life IPS SAS**.  
Capstone SIC 2025 — Valida que los servicios facturados tengan soporte clínico real en la Historia Clínica.

**Versión 2.0 - Julio 2026** — Motor de reglas actualizado con lógica set CUPS y 6 nuevas alertas de negocio.

---

## 🆕 Novedades en v2.0

### Motor de Reglas v2.0
- **Comparación por set de CUPS por atención**: Detección más precisa de inconsistencias
- **6 nuevas alertas de negocio**: SIN_AUTORIZACION_EPS, SOPORTE_MEDICO_INSUFICIENTE, SERVICIO_ALTO_COSTO, TEMPORAL_DISCORDANTE
- **Detección mejorada de fugas de ingresos**: Identificación de procedimientos no facturados

### Modelos de IA Actualizados
- **XGBoost establecido como modelo en producción**: AUC-ROC 0.8983, Precision 99.22%
- **CNN MobileNetV2**: Modelo de referencia (AUC-ROC ~0.67–0.70, ver reporte completo en `Capstone/outputs/reports/metrics.json`)
- **NVIDIA Nemotron-3**: LLM con análisis clínico detallado y nuevas reglas

### Frontend Mejorado
- ✅ Arrastrar documentos corregido en modo factura por factura
- ✅ Visualización de validaciones aplicadas en CNN y XGBoost
- ✅ Indicador visual de lógica set CUPS activa

Consulte `docs/MIGRATION.md` para detalles completos de los cambios en v2.0.

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Frontend | HTML, Tailwind CSS, JavaScript vanilla |
| Base de Datos | SQLite (linea.db) |
| Modelo IA Local (Producción) | XGBoost — Gradient boosting tabular con SHAP |
| Modelo IA Local (Referencia) | TensorFlow / Keras — MobileNetV2 sobre imágenes 32×32×3 |
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
Consulta la afiliación del paciente en la BDUA mediante web scraping de la consulta ciudadana de ADRES (`backend/adres_scraper.py`, uso académico). Si ADRES no responde (403, captcha, timeout), la auditoría procede en modo contingencia con la base de datos local.

### 3. Cruce HC vs PF (Motor de Reglas v2.0)

El motor de reglas v2.0 compara **sets de códigos CUPS por atención** en lugar de comparar fila por fila. Esto permite una detección más precisa de inconsistencias y fugas de ingresos.

#### Cómo funciona la comparación:

```
Atención #12345
├── Prefactura (CUPS facturados): {890201, 890202, 890203, 890204}
├── Historia Clínica (CUPS realizados): {890201, 890202, 890203}
└── Resultado del cruce:
    ├── ✅ 890201, 890202, 890203 → CONSISTENTE (en ambos sets)
    ├── ⚠️ 890204 → SIN_SOPORTE_CLINICO (solo en prefactura)
    └── 🔍 Validaciones adicionales aplicadas:
        ├── ¿Tiene autorización EPS? → SÍ/NO
        ├── ¿Soporte médico diario completo? → SÍ/NO
        ├── ¿Es servicio de alto costo? → SÍ/NO
        └── ¿Coherencia temporal? → SÍ/NO
```

#### Alertas detectadas por el motor v2.0:

| Alerta | Significado | Severidad |
|--------|-------------|-----------|
| `SIN_SOPORTE_CLINICO` | Servicio facturado sin registro en HC | 🔴 ALTA |
| `CODIGO_NO_COINCIDE` | CUPS facturado ≠ CUPS en HC | 🔴 ALTA |
| `CANTIDAD_DISCORDANTE` | Cantidad facturada ≠ cantidad realizada | 🟠 MEDIA |
| `CONSISTENTE` | Coinciden CUPS, cantidad y hay soporte | 🟢 NINGUNA |
| `NO_FACTURADO` | Procedimiento en HC que no aparece en PF (fuga) | 🔴 ALTA |
| `SIN_AUTORIZACION_EPS` | Servicio sin autorización de la EPS | 🔴 ALTA |
| `SOPORTE_MEDICO_INSUFICIENTE` | Falta soporte médico documentado | 🟠 MEDIA |
| `SERVICIO_ALTO_COSTO` | Servicio de alto costo sin validación especial | 🔴 ALTA |
| `TEMPORAL_DISCORDANTE` | Incoherencia temporal atención-facturación | 🟠 MEDIA |

#### Ejemplo de validación completa:

```
Item: 890201 - Consulta médica general
├── Prefactura: 2 unidades, $50,000 total
├── Historia Clínica: 2 unidades realizadas
├── Validaciones v2.0:
│   ├── ✅ CUPS coincide
│   ├── ✅ Cantidad coincide
│   ├── ✅ Tiene soporte clínico
│   ├── ✅ Autorización EPS verificada
│   ├── ✅ Soporte médico diario completo
│   ├── ✅ No es servicio de alto costo
│   └── ✅ Coherencia temporal correcta
└── Resultado: CONSISTENTE
```

### 4. Modelos de IA (opcionales)

#### XGBoost (Modelo en Producción)
- **Métricas**: AUC-ROC 0.8983, Precision 99.22%, Recall 65.13%, F1 0.7864
- **Features**: 18 (10 numéricas, 8 categóricas)
- **Explicabilidad**: SHAP values para interpretación
- **Ubicación**: `models/modelo_xgboost.pkl` y `models/artefactos_xgboost.pkl`

#### CNN MobileNetV2 (Referencia)
Pipeline tabular → imagen:
1. Imputación de nulos
2. Escalado numérico (StandardScaler)
3. One-Hot Encoding → 111 features dummy
4. Mapeo a grid 32×32 vía t-SNE
5. Normalización global min-max
6. CNN MobileNetV2 → probabilidad de inconsistencia
- **Métricas**: AUC-ROC 0.6727 (consolidado, umbral óptimo 0.4273) — Precisión 0.34, Recall 0.56, F1 0.43
- **Nota**: El CNN no es determinista en CPU (corridas limpias sucesivas dieron 0.6727, 0.6984 y 0.7104). Rango recomendado: **~0.67–0.70**.
- **Ubicación del reporte**: `Capstone/outputs/models/cnn/metrics_fase2.json` y `Capstone/outputs/reports/metrics.json`

#### NVIDIA Nemotron-3 (Externo)
LLM que recibe contexto clínico completo (diagnóstico, items PF, items HC, cruces) y genera análisis detallado con recomendación. Aplica todas las nuevas reglas de negocio v2.0.

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
│   ├── 03_historia_clinica_detalle.csv Historia clínica detalle (datos de prueba)
│   ├── 04_prefactura.csv             Prefacturas (datos de prueba)
│   ├── db_meta.json                  Metadatos de la BD
│   └── datos_prueba/                 Archivos de prueba adicionales
├── models/
│   ├── modelo_xgboost.pkl              XGBoost entrenado (modelo en producción)
│   ├── artefactos_xgboost.pkl          Artefactos XGBoost (scaler, encoders, threshold)
│   ├── auditor_medico_cnn.keras        CNN MobileNetV2 entrenado (referencia)
│   └── artefactos_preprocesamiento.pkl Parámetros del pipeline CNN
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

## Modelo XGBoost en detalle (Producción)

El modelo `modelo_xgboost.pkl` es un **XGBoost Classifier** entrenado con 18 features (10 numéricas, 8 categóricas).

### Pipeline de entrenamiento (`notebooks/07_entrenamiento_xgboost_avanzado.ipynb`)

```
Dataset maestro (3,126 registros)
    │
    ▼
Feature Engineering
- diferencia_cantidad
- ratio_cantidad
- coincide_codigo_cups
- tiene_soporte_clinico
- dias_diferencia
    │
    ▼
Imputación de nulos (numéricos → 0, categóricos → "SIN_DATO")
    │
    ▼
Label Encoding (categóricas)
    │
    ▼
StandardScaler (numéricas)
    │
    ▼
GridSearchCV (5-fold estratificado)
- max_depth: 8
- learning_rate: 0.1
- n_estimators: 200
- scale_pos_weight: 3.82
    │
    ▼
XGBoost Classifier → probabilidad [0, 1]
    │
    ▼
Threshold óptimo (0.896) → 0: CONSISTENTE / 1: INCONSISTENTE
```

### Métricas finales
- **AUC-ROC**: 0.8983
- **Precision**: 0.9922 (99.22%)
- **Recall**: 0.6513 (65.13%)
- **F1-Score**: 0.7864
- **CV 5-fold AUC**: 0.8806 ± 0.0105

### Features más importantes
1. `coincide_codigo_cups` (65.66%)
2. `diferencia_cantidad` (20.37%)
3. `ratio_cantidad` (1.53%)
4. `eps_atencion` (1.21%)
5. `dias_diferencia` (1.21%)

### Columnas usadas

**Numéricas** (10): `diferencia_cantidad`, `ratio_cantidad`, `coincide_codigo_cups`, `tiene_soporte_clinico`, `cantidad_facturada`, `cantidad_realizada`, `valor_unitario`, `valor_total`, `edad`, `dias_diferencia`

**Categóricas** (8): `tipo_atencion`, `sede`, `eps_atencion`, `tipo_afiliacion`, `tipo_item`, `grupo_etario`, `sexo`, `diag_encoded` (Top-10 diagnósticos + OTRO)

---

## Modelo CNN en detalle (Referencia)

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
| `NVIDIA_MODEL` | Model ID de NVIDIA (default en `server.py`: `nvidia/nemotron-3-nano-30b-a3b`; `.env.example` trae `nvidia/nemotron-3-nano-8b-v1`) |

La verificación BDUA no requiere API key: se realiza por web scraping de la consulta ciudadana de ADRES (`backend/adres_scraper.py`).

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
