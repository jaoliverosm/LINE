"""
build_db.py
===========
Lee dataset_maestro.csv y crea linea.db SQLite con indices.
Ejecutar UNA sola vez: python build_db.py

LINE - Auditor Medico Digital - Capstone SIC 2025
"""
import sqlite3, pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ── RUTAS DE DATOS (CAMBIAR EN PRODUCCIÓN) ─────────────────────────────
# CSV_PATH: Dataset maestro para construir la base de datos
# - Actualmente: data/dataset_maestro.csv (datos de prueba)
# - Producción: Cambiar a ruta real del dataset maestro
#
# DB_PATH: Ruta donde se creará la base de datos SQLite
# - Actualmente: linea.db (local)
# - Producción: Cambiar si se usa un servidor de BD remoto
CSV_PATH = BASE / "data" / "dataset_maestro.csv"
DB_PATH = BASE / "linea.db"

def main():
    print(f"Leyendo {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"  {len(df)} filas, {len(df.columns)} columnas")

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    # Volcar el dataset maestro como tabla principal
    df.to_sql("cruce_maestro", conn, index=False, if_exists="replace")

    # Crear tabla pacientes (unicos)
    pac_cols = [c for c in df.columns if c in (
        "id_paciente","tipo_documento","edad","sexo","eps_paciente","tipo_afiliacion","ciudad")]
    df_pac = df[pac_cols].drop_duplicates(subset="id_paciente")
    df_pac.to_sql("pacientes", conn, index=False, if_exists="replace")

    # Tabla atenciones (ids unicos)
    ate_cols = [c for c in df.columns if c in (
        "id_atencion","id_paciente","fecha_atencion","tipo_atencion",
        "diagnostico_principal_cie10","descripcion_diagnostico","medico_tratante",
        "sede","eps_atencion")]
    df_ate = df[ate_cols].drop_duplicates(subset="id_atencion")
    df_ate.to_sql("atenciones", conn, index=False, if_exists="replace")

    # Indices
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cruce_id ON cruce_maestro(id_cruce)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cruce_at ON cruce_maestro(id_atencion)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pac_id ON pacientes(id_paciente)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ate_id ON atenciones(id_atencion)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ate_pac ON atenciones(id_paciente)")

    conn.commit()
    conn.close()
    print(f"linea.db creado: {DB_PATH}  ({DB_PATH.stat().st_size/1e6:.1f} MB)")

    # Guardar metadata
    meta = {
        "n_filas_cruce": int(len(df)),
        "n_columnas": int(len(df.columns)),
        "n_pacientes": int(len(df_pac)),
        "n_atenciones": int(len(df_ate)),
        "consistentes": int((df["resultado"]=="CONSISTENTE").sum()),
        "inconsistentes": int((df["resultado"]=="INCONSISTENTE").sum()),
    }
    import json
    (BASE/"data"/"db_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print("Metadatos guardados en data/db_meta.json")

if __name__ == "__main__":
    main()