# Guía de Migración a Producción

Esta guía detalla los pasos necesarios para migrar el proyecto LINE desde el entorno de desarrollo (SQLite, datos de prueba) a un entorno de producción (SQL Server o MySQL, datos reales).

---

## Tabla de Contenidos

1. [Requisitos Previos](#requisitos-previos)
2. [Migración a SQL Server](#migración-a-sql-server)
3. [Migración a MySQL](#migración-a-mysql)
4. [Cambio de Rutas de Archivos](#cambio-de-rutas-de-archivos)
5. [Configuración del Frontend](#configuración-del-frontend)
6. [Verificación](#verificación)
7. [Rollback](#rollback)
8. [Actualizaciones Recientes (v2.0)](#actualizaciones-recientes-v20)

---

## Requisitos Previos

### Para SQL Server
- Python 3.10+
- pyodbc: `pip install pyodbc`
- ODBC Driver 17 for SQL Server instalado en el servidor
- Acceso al servidor SQL Server

### Para MySQL
- Python 3.10+
- mysql-connector-python: `pip install mysql-connector-python`
- Acceso al servidor MySQL

### General
- Acceso a los archivos de datos reales (historia clínica, prefacturas)
- Acceso a los modelos entrenados (si están en servidor diferente)

---

## Migración a SQL Server

### Paso 1: Instalar dependencias

```bash
pip install pyodbc
```

### Paso 2: Configurar .env

Copiar `.env.example` a `.env` y configurar:

```env
DB_ENGINE=sqlserver
DB_SERVER=tu_servidor_sql
DB_DATABASE=tu_base_datos
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
DB_DRIVER=ODBC Driver 17 for SQL Server
```

### Paso 3: Modificar server.py

Reemplazar la función `_query()` en `server.py` (línea ~169):

```python
# ── FUNCIÓN DE CONSULTA A BASE DE DATOS (SQL Server) ─────────────────────
import pyodbc

def _query(sql: str, params=()) -> list[dict]:
    conn_str = (
        f"DRIVER={_os.environ.get('DB_DRIVER', 'ODBC Driver 17 for SQL Server')};"
        f"SERVER={_os.environ.get('DB_SERVER')};"
        f"DATABASE={_os.environ.get('DB_DATABASE')};"
        f"UID={_os.environ.get('DB_USER')};"
        f"PWD={_os.environ.get('DB_PASSWORD')}"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]
```

### Paso 4: Crear tablas en SQL Server

Ejecutar este script SQL en SQL Server:

```sql
-- Tabla pacientes
CREATE TABLE pacientes (
    id_paciente NVARCHAR(50) PRIMARY KEY,
    tipo_documento NVARCHAR(10),
    nombres NVARCHAR(100),
    apellidos NVARCHAR(100),
    edad INT,
    sexo NVARCHAR(10),
    eps_paciente NVARCHAR(100),
    tipo_afiliacion NVARCHAR(50),
    ciudad NVARCHAR(100)
);

-- Tabla atenciones
CREATE TABLE atenciones (
    id_atencion NVARCHAR(50) PRIMARY KEY,
    id_paciente_aten NVARCHAR(50),
    fecha_atencion DATE,
    tipo_atencion NVARCHAR(50),
    diagnostico_principal_cie10 NVARCHAR(20),
    descripcion_diagnostico NVARCHAR(200),
    medico_tratante NVARCHAR(100),
    sede NVARCHAR(50),
    eps_atencion NVARCHAR(100),
    FOREIGN KEY (id_paciente_aten) REFERENCES pacientes(id_paciente)
);

-- Tabla cruce_maestro
CREATE TABLE cruce_maestro (
    id_cruce NVARCHAR(50) PRIMARY KEY,
    id_atencion NVARCHAR(50),
    id_paciente NVARCHAR(50),
    edad INT,
    sexo NVARCHAR(10),
    eps_atencion NVARCHAR(100),
    tipo_afiliacion NVARCHAR(50),
    ciudad NVARCHAR(50),
    tipo_documento NVARCHAR(10),
    tipo_atencion NVARCHAR(50),
    sede NVARCHAR(50),
    tipo_item NVARCHAR(50),
    codigo_cups NVARCHAR(20),
    descripcion NVARCHAR(200),
    cantidad_realizada FLOAT,
    cantidad_facturada FLOAT,
    valor_unitario FLOAT,
    valor_total FLOAT,
    mes_atencion INT,
    soporte_clinico NVARCHAR(20),
    grupo_etario NVARCHAR(50),
    diagnostico_principal_cie10 NVARCHAR(20),
    medico_tratante NVARCHAR(100),
    profesional_responsable NVARCHAR(100),
    resultado NVARCHAR(20),
    FOREIGN KEY (id_atencion) REFERENCES atenciones(id_atencion)
);

-- Crear índices
CREATE INDEX idx_cruce_id ON cruce_maestro(id_cruce);
CREATE INDEX idx_cruce_at ON cruce_maestro(id_atencion);
CREATE INDEX idx_pac_id ON pacientes(id_paciente);
CREATE INDEX idx_ate_id ON atenciones(id_atencion);
CREATE INDEX idx_ate_pac ON atenciones(id_paciente_aten);
```

### Paso 5: Importar datos

Usar SQL Server Management Studio (SSMS) o herramienta similar para importar los datos desde `data/dataset_maestro.csv` a las tablas creadas.

---

## Migración a MySQL

### Paso 1: Instalar dependencias

```bash
pip install mysql-connector-python
```

### Paso 2: Configurar .env

Copiar `.env.example` a `.env` y configurar:

```env
DB_ENGINE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_DATABASE=tu_base_datos
DB_USER=tu_usuario
DB_PASSWORD=tu_contraseña
```

### Paso 3: Modificar server.py

Reemplazar la función `_query()` en `server.py` (línea ~169):

```python
# ── FUNCIÓN DE CONSULTA A BASE DE DATOS (MySQL) ─────────────────────────
import mysql.connector

def _query(sql: str, params=()) -> list[dict]:
    conn = mysql.connector.connect(
        host=_os.environ.get('DB_HOST', 'localhost'),
        port=int(_os.environ.get('DB_PORT', 3306)),
        database=_os.environ.get('DB_DATABASE'),
        user=_os.environ.get('DB_USER'),
        password=_os.environ.get('DB_PASSWORD')
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return rows
```

### Paso 4: Crear tablas en MySQL

Ejecutar este script SQL en MySQL:

```sql
-- Tabla pacientes
CREATE TABLE pacientes (
    id_paciente VARCHAR(50) PRIMARY KEY,
    tipo_documento VARCHAR(10),
    nombres VARCHAR(100),
    apellidos VARCHAR(100),
    edad INT,
    sexo VARCHAR(10),
    eps_paciente VARCHAR(100),
    tipo_afiliacion VARCHAR(50),
    ciudad VARCHAR(100)
);

-- Tabla atenciones
CREATE TABLE atenciones (
    id_atencion VARCHAR(50) PRIMARY KEY,
    id_paciente_aten VARCHAR(50),
    fecha_atencion DATE,
    tipo_atencion VARCHAR(50),
    diagnostico_principal_cie10 VARCHAR(20),
    descripcion_diagnostico VARCHAR(200),
    medico_tratante VARCHAR(100),
    sede VARCHAR(50),
    eps_atencion VARCHAR(100),
    FOREIGN KEY (id_paciente_aten) REFERENCES pacientes(id_paciente)
);

-- Tabla cruce_maestro
CREATE TABLE cruce_maestro (
    id_cruce VARCHAR(50) PRIMARY KEY,
    id_atencion VARCHAR(50),
    id_paciente VARCHAR(50),
    edad INT,
    sexo VARCHAR(10),
    eps_atencion VARCHAR(100),
    tipo_afiliacion VARCHAR(50),
    ciudad VARCHAR(50),
    tipo_documento VARCHAR(10),
    tipo_atencion VARCHAR(50),
    sede VARCHAR(50),
    tipo_item VARCHAR(50),
    codigo_cups VARCHAR(20),
    descripcion VARCHAR(200),
    cantidad_realizada FLOAT,
    cantidad_facturada FLOAT,
    valor_unitario FLOAT,
    valor_total FLOAT,
    mes_atencion INT,
    soporte_clinico VARCHAR(20),
    grupo_etario VARCHAR(50),
    diagnostico_principal_cie10 VARCHAR(20),
    medico_tratante VARCHAR(100),
    profesional_responsable VARCHAR(100),
    resultado VARCHAR(20),
    FOREIGN KEY (id_atencion) REFERENCES atenciones(id_atencion)
);

-- Crear índices
CREATE INDEX idx_cruce_id ON cruce_maestro(id_cruce);
CREATE INDEX idx_cruce_at ON cruce_maestro(id_atencion);
CREATE INDEX idx_pac_id ON pacientes(id_paciente);
CREATE INDEX idx_ate_id ON atenciones(id_atencion);
CREATE INDEX idx_ate_pac ON atenciones(id_paciente_aten);
```

### Paso 5: Importar datos

Usar MySQL Workbench o herramienta similar para importar los datos desde `data/dataset_maestro.csv` a las tablas creadas.

---

## Cambio de Rutas de Archivos

### Archivos que necesitan cambios de rutas:

1. **server.py** (líneas 84-85):
   - `HC_DETALLE_PATH`: Actualmente `BASE / "data" / "03_historia_clinica_detalle.csv"` - Cambiar a ruta real del archivo de historia clínica en producción
   - `PF_ORIGINAL_PATH`: Actualmente `BASE / "data" / "04_prefactura.csv"` - Cambiar a ruta real del archivo de prefactura en producción

2. **build_db.py** (líneas 22-23):
   - `CSV_PATH`: Actualmente usa `data/dataset_maestro.csv` - Cambiar a ruta real del dataset maestro en producción
   - `DB_PATH`: Cambiar si se usa servidor de BD remoto

3. **preprocesamiento.py** (líneas 28-29):
   - `ARTIFACTS_PATH`: Cambiar si los modelos están en servidor diferente
   - `MODEL_PATH`: Cambiar si el modelo está en servidor diferente

### Ejemplo de cambio en server.py:

```python
# Cambiar de (desarrollo):
HC_DETALLE_PATH = BASE / "data" / "03_historia_clinica_detalle.csv"

# A (producción):
HC_DETALLE_PATH = Path("C:/ruta/produccion/historia_clinica_detalle.csv")
# O usar variable de entorno:
HC_DETALLE_PATH = Path(_os.environ.get("HC_DETALLE_PATH", "data/03_historia_clinica_detalle.csv"))
```

---

## Configuración del Frontend

### Cambiar URL de API en frontend/app.js (línea 6):

```javascript
// Cambiar de:
const API = "http://127.0.0.1:8000/api";

// A la URL del servidor de producción:
const API = "https://api.tudominio.com/api";
```

---

## Verificación

### 1. Verificar conexión a base de datos

```bash
python -c "from server import _query; print(_query('SELECT COUNT(*) as c FROM pacientes'))"
```

### 2. Verificar carga de modelos

Iniciar el servidor y verificar el endpoint `/api/health`:

```bash
curl http://localhost:8000/api/health
```

Debería retornar:
```json
{
  "status": "ok",
  "modelo_cargado": true,
  "xgboost_cargado": true,
  "modo": "ia",
  "db_path": "./linea.db",
  "n_filas_cruce": 3126,
  "hc_detalle_disponible": true
}
```

### 3. Verificar análisis de prefactura

Probar el endpoint `/api/prefactura/analizar` con un archivo CSV de prueba.

---

## Rollback

Si hay problemas con la migración, para volver a SQLite:

1. **Restaurar .env**:
   ```env
   DB_ENGINE=sqlite
   DB_PATH=./linea.db
   ```

2. **Restaurar server.py**:
   Revertir la función `_query()` a la versión original con sqlite3.

3. **Restaurar rutas de archivos**:
   Volver a las rutas originales en server.py, build_db.py, preprocesamiento.py.

4. **Restaurar frontend**:
   Volver a la URL de desarrollo en frontend/app.js.

5. **Reconstruir base de datos SQLite**:
   ```bash
   python build_db.py
   ```

---

## Soporte

Para problemas durante la migración, consulte:
- Documentación principal: `docs/README.md`
- Issues en el repositorio del proyecto
- Contacto de soporte: canal oficial SIAU de la IPS — siau@hlips.com.co · PBX 300 912 1102

---

## Actualizaciones Recientes (v2.0)

### Cambios en el Motor de Reglas (v2.0)

**Nuevas reglas de negocio implementadas:**

1. **Comparación por set de CUPS por atención**
   - Antes: Comparación fila por fila de items
   - Ahora: Comparación de sets de códigos CUPS por atención
   - Beneficio: Detección más precisa de inconsistencias y fugas

2. **Validación de autorización EPS**
   - Verifica que los servicios facturados tengan autorización de la EPS
   - Alerta: `SIN_AUTORIZACION_EPS`

3. **Soporte médico diario completo**
   - Valida que haya soporte médico documentado para cada día de atención
   - Alerta: `SIN_SOPORTE_MEDICO_DIARIO`

4. **Detección de servicios de alto costo**
   - Identifica servicios de alto costo que requieren validación especial
   - Alerta: `SERVICIO_ALTO_COSTO_SIN_VALIDACION`

5. **Validación temporal (días)**
   - Verifica la coherencia temporal entre atención y facturación
   - Alerta: `FACTURACION_TARDIA`

6. **Detección mejorada de fugas de ingresos**
   - Identifica procedimientos realizados en HC pero no facturados
   - Alerta: `NO_FACTURADO`

### Cambios en Modelos de IA

**XGBoost (Modelo en producción):**
- Modelo entrenado en `notebooks/07_entrenamiento_xgboost_avanzado.ipynb`
- Métricas finales:
  - AUC-ROC: 0.8983
  - Precision: 0.9922 (99.22%)
  - Recall: 0.6513 (65.13%)
  - F1: 0.7864
  - CV 5-fold AUC: 0.8806 ± 0.0105
- Ubicación: `models/modelo_xgboost.pkl` y `models/artefactos_xgboost.pkl`

**CNN MobileNetV2:**
- **Nota**: Re-ejecutado con kernel limpio (notebook 08, 29-jul-2026). El CNN no es determinista en CPU: corridas sucesivas dan 0.6727, 0.6984 y 0.7104.
- **Métrica consolidada**: AUC-ROC **0.6727** (rango recomendado ~0.67–0.70)
  - Threshold óptimo: 0.4273 | Precisión: 0.34 | Recall: 0.56 | F1: 0.43
- **Cifra histórica**: 0.7487 (no reproducible con el notebook actual)
- Referencia: `notebooks/08_modelo_cnn_transfer_learning.ipynb`

**NVIDIA Nemotron-3:**
- LLM externo para análisis clínico detallado
- Aplica todas las nuevas reglas de negocio
- Genera explicaciones contextuales

### Cambios en Frontend

**Mejoras en modo factura por factura:**
- ✅ Corregido: Arrastrar documentos ahora funciona correctamente
- ✅ Agregado: Visualización de validaciones aplicadas en CNN y XGBoost
- ✅ Agregado: Indicador visual de lógica set CUPS activa

**Mejoras en modo importación masiva:**
- ✅ Implementada lógica set CUPS por atención
- ✅ Detección de fugas de ingresos mejorada
- ✅ Validaciones avanzadas en procesamiento por lotes

### Cambios en Documentación

**Actualizados:**
- `docs/workflow.html`: Motor de reglas v2.0 con nuevas alertas
- `docs/MIGRATION.md`: Esta sección de actualizaciones v2.0
- `docs/README.md`: Pendiente actualización

**Archivos de configuración:**
- `server.py`: Prompt Nemotron actualizado con nuevas reglas
- `frontend/app.js`: Validaciones visuales mejoradas
- `frontend/index.html`: Handler drag & drop corregido

### Rutas de Archivos Actualizadas

**Modelos:**
- XGBoost: `models/modelo_xgboost.pkl` (modelo en producción)
- Artefactos XGBoost: `models/artefactos_xgboost.pkl`
- CNN: `models/auditor_medico_cnn.keras`

**Datos:**
- Dataset maestro: `data/dataset_maestro.csv` (3,126 registros)
- Base de datos: `linea.db` (SQLite)

**Salidas:**
- Métricas: `outputs/reports/metrics.json`
- Reportes: `outputs/models/xgboost_avanzado/reporte_evaluacion.txt`

### Consideraciones para Migración

1. **Base de datos:**
   - Asegurar que el esquema soporte las nuevas columnas de validación
   - Verificar que los índices estén optimizados para consultas por atención

2. **Modelos:**
   - Usar el modelo XGBoost del notebook 07 (modelo en producción)
   - Verificar que los artefactos estén en la ruta correcta

3. **Frontend:**
   - Actualizar la URL de API según el entorno
   - Verificar que las nuevas validaciones se muestren correctamente

4. **Nemotron:**
   - Configurar API key de NVIDIA si se usa en producción
   - Verificar que el prompt incluya las nuevas reglas de negocio

### Notas de Versión

**Versión 2.0 - Julio 2026:**
- Motor de reglas actualizado a lógica set CUPS
- 6 nuevas alertas de negocio implementadas
- XGBoost establecido como modelo en producción
- Frontend mejorado con validaciones visuales
- Documentación actualizada con nuevos flujos

**Versión 1.0 - Versión anterior:**
- Motor de reglas básico (4 alertas)
- Comparación fila por fila
- CNN como modelo principal
- Frontend básico sin validaciones avanzadas
