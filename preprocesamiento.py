"""
preprocesamiento.py
====================
Pipeline tabular-to-image para inferencia con auditor_medico_cnn.keras.
Replica EXACTAMENTE el pipeline del notebook LINE:
  imputacion -> OHE con top_categories -> StandardScaler ->
  feature_positions en grid 32x32 -> normalizacion global -> imagen 32x32x3

Los artefactos se cargan desde artefactos_preprocesamiento.pkl.

LINE - Auditor Medico Digital - Capstone SIC 2025
"""
import pickle, numpy as np, pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent

# ── RUTAS DE MODELOS (CAMBIAR SI ESTÁN EN OTRA UBICACIÓN) ─────────────
# ARTIFACTS_PATH: Archivo pickle con artefactos de preprocesamiento
# - Actualmente: models/artefactos_preprocesamiento.pkl
# - Producción: Cambiar si los modelos están en servidor diferente
#
# MODEL_PATH: Modelo CNN entrenado (.keras)
# - Actualmente: models/auditor_medico_cnn.keras
# - Producción: Cambiar si el modelo está en servidor diferente
ARTIFACTS_PATH = BASE / "models" / "artefactos_preprocesamiento.pkl"
MODEL_PATH = BASE / "models" / "auditor_medico_cnn.keras"

_artefactos = None
_modelo = None

def cargar_artefactos():
    global _artefactos
    if _artefactos is None:
        with open(ARTIFACTS_PATH, "rb") as f:
            _artefactos = pickle.load(f)
    return _artefactos

def _cargar_modelo():
    global _modelo
    if _modelo is None:
        from tensorflow import keras
        _modelo = keras.models.load_model(str(MODEL_PATH), compile=False)
    return _modelo

# Columnas numericas originales (se escalan con StandardScaler del pickle)
NUM_COLS = ["edad", "cantidad_realizada", "cantidad_facturada",
            "valor_unitario", "valor_total", "mes_atencion"]

# Columnas categoricas originales (se codifican con top_categories)
CAT_COLS_ORIG = ["sexo", "eps_atencion", "tipo_afiliacion", "ciudad",
                 "tipo_documento", "tipo_atencion", "sede", "tipo_item",
                 "soporte_clinico", "grupo_etario", "diagnostico_principal_cie10",
                 "medico_tratante", "profesional_responsable"]

def imputar_nulos(df):
    df = df.copy()
    for c in NUM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in CAT_COLS_ORIG:
        if c in df.columns:
            df[c] = df[c].fillna("SIN_DATO").astype(str)
    return df

def _codificar_fila(row, top_cats):
    """
    Codifica UNA fila (Series) en el vector de 111 features exactamente
    en el mismo orden que cat_columns del pickle.
    top_cats: dict {col_orig: [categorias_validas]}
    """
    cat_cols_order = cargar_artefactos()["cat_columns"]  # 111 columnas en orden
    vec = np.zeros(len(cat_cols_order), dtype=np.float32)

    for i, col_name in enumerate(cat_cols_order):
        # Cada columna dummy sigue la convencion de pd.get_dummies:
        # "<columna_original>_<valor>". Como varias columnas originales
        # contienen "_" (eps_atencion, soporte_clinico, ...), primero se
        # identifica la columna original y el valor es TODO lo que sigue.
        col_orig = None
        for c in CAT_COLS_ORIG:
            if col_name.startswith(c + "_"):
                col_orig = c
                break
        if col_orig is None:
            continue
        value = col_name[len(col_orig) + 1:]

        raw_val = str(row.get(col_orig, "SIN_DATO"))
        # Aplicar top_categories: si no esta en la lista, mapear a "OTRO_col"
        valid_cats = top_cats.get(col_orig, [])
        if valid_cats and raw_val not in valid_cats:
            raw_val = f"OTRO_{col_orig}"
        # Verificar si el valor matchea esta columna dummificada
        expected_dummy_val = raw_val  # ej: "F" -> columna "sexo_F"
        if value == expected_dummy_val:
            vec[i] = 1.0
    return vec

def _build_image(vector_111, feature_positions, grid_size=32):
    """
    Convierte un vector de 111 features en una imagen 32x32x3
    usando las coordenadas (x,y) del t-SNE.
    feature_positions: ndarray (111, 2) con coordenadas (x, y) para cada feature.
    """
    img = np.zeros((grid_size, grid_size, 3), dtype=np.float32)
    for feat_idx in range(min(len(vector_111), len(feature_positions))):
        x, y = feature_positions[feat_idx]
        x, y = int(x), int(y)
        if 0 <= x < grid_size and 0 <= y < grid_size:
            img[y, x, :] = vector_111[feat_idx]
    return img

def predecir_inconsistencia(df_input: pd.DataFrame) -> dict:
    """
    Pipeline completo: imputacion -> escalado -> OHE 111 features ->
    posicionamiento grid 32x32 -> normalizacion global -> modelo CNN -> prediccion.
    """
    artefactos = cargar_artefactos()
    threshold = artefactos["threshold"]
    scaler = artefactos["scaler"]
    global_min = artefactos["global_min"]
    global_max = artefactos["global_max"]
    feature_positions = artefactos["feature_positions"]   # ndarray (111, 2)
    top_categories = artefactos["top_categories"]         # dict
    cat_columns = artefactos["cat_columns"]               # list de 111 nombres

    # 1. Imputacion
    df = imputar_nulos(df_input)

    # 2. Escalar numericas (solo las que existen)
    num_present = [c for c in NUM_COLS if c in df.columns]
    if num_present:
        df[num_present] = scaler.transform(df[num_present].fillna(0))

    # 3. Construir vector de 111 features por fila
    n_rows = len(df)
    X_111 = np.zeros((n_rows, len(cat_columns)), dtype=np.float32)
    for row_idx in range(n_rows):
        X_111[row_idx] = _codificar_fila(df.iloc[row_idx], top_categories)

    # 4. Posicionar cada vector 111 en grid 32x32 -> imagen 32x32x3
    grid_size = artefactos["img_size"]
    images = np.zeros((n_rows, grid_size, grid_size, 3), dtype=np.float32)
    for i in range(n_rows):
        images[i] = _build_image(X_111[i], feature_positions, grid_size)

    # 5. Normalizacion GLOBAL (min/max del train set guardado en pickle)
    images = np.clip((images - global_min) / (global_max - global_min + 1e-7), 0, 1)

    # 6. Cargar modelo y predecir
    modelo = _cargar_modelo()
    probs = modelo.predict(images, verbose=0, batch_size=min(32, n_rows)).flatten()
    preds = (probs > threshold).astype(int)

    return {
        "probabilidades": probs.tolist(),
        "predicciones": preds.tolist(),
        "threshold": float(threshold),
        "consistentes": int((preds == 0).sum()),
        "inconsistentes": int((preds == 1).sum()),
        "imagen_shape": list(images.shape),
    }


if __name__ == "__main__":
    a = cargar_artefactos()
    print(f"Artefactos cargados: {sorted(a.keys())}")
    print(f"  threshold = {a['threshold']:.4f}")
    print(f"  img_size = {a['img_size']}")
    print(f"  feature_positions shape = {a['feature_positions'].shape}")
    print(f"  cat_columns count = {len(a['cat_columns'])}")
    print(f"  top_categories keys = {len(a['top_categories'])}")
    print(f"  num_features = {a['num_features']}")
    print(f"  scaler type = {type(a['scaler']).__name__}")