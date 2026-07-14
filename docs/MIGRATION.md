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
   - `HC_DETALLE_PATH`: Cambiar a ruta real del archivo de historia clínica
   - `PF_ORIGINAL_PATH`: Cambiar a ruta real del archivo de prefactura

2. **build_db.py** (líneas 22-23):
   - `CSV_PATH`: Cambiar a ruta real del dataset maestro
   - `DB_PATH`: Cambiar si se usa servidor de BD remoto

3. **preprocesamiento.py** (líneas 28-29):
   - `ARTIFACTS_PATH`: Cambiar si los modelos están en servidor diferente
   - `MODEL_PATH`: Cambiar si el modelo está en servidor diferente

### Ejemplo de cambio en server.py:

```python
# Cambiar de:
HC_DETALLE_PATH = BASE.parent / "CSV ORIGINAL" / "03_historia_clinica_detalle.csv"

# A:
HC_DETALLE_PATH = Path("C:/ruta/produccion/historia_clinica_detalle.csv")
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
  "modo": "ia"
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
- Contacto de soporte: soporte@hlsite.com.co
