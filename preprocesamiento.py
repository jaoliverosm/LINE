"""
preprocesamiento.py
====================
Pipeline tabular-to-image para inferencia con auditor_medico_cnn.keras.
Replica EXACTAMENTE el pipeline de entrenamiento del notebook LINE:
  imputacion -> [numericas escaladas | dummies por top_categories] ->
  feature_positions en grid -> normalizacion global -> imagen NxNx3

El vector de entrada al grid es el MISMO del entrenamiento: primero las
variables numericas escaladas con el StandardScaler del pickle y luego las
dummies categoricas, en el orden de `cat_columns`. `feature_positions` trae
una posicion por CADA feature de ese vector completo (numericas incluidas);
las longitudes se derivan SIEMPRE de los artefactos y se validan antes de
construir imagenes (ver _validar_artefactos).

Fix R1 (rama fix/r1-cnn-vector-completo): la version anterior construia el
grid solo con las dummies y las mapeaba contra las primeras posiciones del
entrenamiento — las numericas nunca entraban a la imagen y todas las dummies
caian en el pixel de otra feature (validado en la revision del 26-jul-2026).

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


def _validar_artefactos(artefactos):
    """
    Valida la coherencia dimensional de los artefactos y devuelve
    (n_num, n_dum, n_total). El contrato de entrenamiento es:

        len(feature_positions) == len(num_features) + len(cat_columns)

    (una posicion por cada feature del vector completo). Si no se cumple,
    los artefactos no corresponden a este pipeline y se aborta con un error
    explicito en vez de producir imagenes silenciosamente corruptas.
    """
    num_features = list(artefactos["num_features"])
    cat_columns = list(artefactos["cat_columns"])
    positions = artefactos["feature_positions"]

    n_num, n_dum, n_pos = len(num_features), len(cat_columns), len(positions)
    if n_num + n_dum != n_pos:
        raise ValueError(
            "Artefactos inconsistentes: num_features (%d) + cat_columns (%d) = %d "
            "features, pero feature_positions trae %d posiciones. El pickle no "
            "corresponde al contrato de entrenamiento [numericas | dummies]."
            % (n_num, n_dum, n_num + n_dum, n_pos)
        )
    if num_features != NUM_COLS:
        raise ValueError(
            "Artefactos inconsistentes: num_features del pickle %r no coincide "
            "con el orden esperado por este modulo %r." % (num_features, NUM_COLS)
        )
    return n_num, n_dum, n_num + n_dum


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
    Codifica UNA fila (Series) en el vector de dummies, exactamente en el
    mismo orden que cat_columns del pickle.
    top_cats: dict {col_orig: [categorias_validas]}
    """
    cat_cols_order = cargar_artefactos()["cat_columns"]
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


def _vector_completo(df, artefactos):
    """
    Construye la matriz (n_filas, n_total) del MISMO vector del entrenamiento:
    [numericas escaladas | dummies], con n_total derivado de los artefactos.

    Las numericas ausentes en el DataFrame se crean en 0 (equivalente al
    fillna(0) del entrenamiento) ANTES de escalar, para que el StandardScaler
    reciba siempre sus columnas completas y en orden.
    """
    n_num, n_dum, n_total = _validar_artefactos(artefactos)
    scaler = artefactos["scaler"]
    top_categories = artefactos["top_categories"]

    df = imputar_nulos(df)
    for c in NUM_COLS:
        if c not in df.columns:
            df[c] = 0.0
    num_scaled = scaler.transform(df[NUM_COLS].astype(float).fillna(0)).astype(np.float32)

    n_rows = len(df)
    X = np.zeros((n_rows, n_total), dtype=np.float32)
    X[:, :n_num] = num_scaled
    for row_idx in range(n_rows):
        X[row_idx, n_num:] = _codificar_fila(df.iloc[row_idx], top_categories)
    return X


def _build_image(vector, feature_positions, grid_size):
    """
    Coloca el vector COMPLETO de features en la grilla: la feature i va al
    pixel feature_positions[i], en orden ascendente de i (si dos features
    comparten pixel, gana la de mayor indice — igual que en entrenamiento).
    Exige que vector y posiciones tengan la misma longitud.
    """
    if len(vector) != len(feature_positions):
        raise ValueError(
            "Vector de %d features no coincide con %d posiciones: la imagen "
            "quedaria desalineada respecto al entrenamiento (bug R1)."
            % (len(vector), len(feature_positions))
        )
    img = np.zeros((grid_size, grid_size), dtype=np.float32)
    for feat_idx, (x, y) in enumerate(feature_positions):
        x, y = int(x), int(y)
        if 0 <= x < grid_size and 0 <= y < grid_size:
            img[y, x] = vector[feat_idx]
    return img


def construir_imagenes(df_input: pd.DataFrame) -> np.ndarray:
    """
    Pipeline determinista SIN modelo: imputacion -> vector completo
    [numericas escaladas | dummies] -> grilla via feature_positions ->
    normalizacion GLOBAL (min/max del train guardados en el pickle) ->
    imagenes (n, grid, grid, 3). Es lo que consume el CNN.
    """
    artefactos = cargar_artefactos()
    feature_positions = artefactos["feature_positions"]
    grid_size = artefactos["img_size"]
    global_min = artefactos["global_min"]
    global_max = artefactos["global_max"]

    X = _vector_completo(df_input, artefactos)
    n_rows = len(X)
    imgs = np.zeros((n_rows, grid_size, grid_size), dtype=np.float32)
    for i in range(n_rows):
        imgs[i] = _build_image(X[i], feature_positions, grid_size)

    imgs = np.clip((imgs - global_min) / (global_max - global_min + 1e-7), 0, 1)
    return np.stack([imgs, imgs, imgs], axis=-1)


def predecir_inconsistencia(df_input: pd.DataFrame) -> dict:
    """
    Pipeline completo: construir_imagenes() -> modelo CNN -> prediccion con el
    threshold del pickle.
    """
    artefactos = cargar_artefactos()
    threshold = artefactos["threshold"]

    images = construir_imagenes(df_input)

    modelo = _cargar_modelo()
    n_rows = len(images)
    probs = modelo.predict(images, verbose=0, batch_size=min(32, max(1, n_rows))).flatten()
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
    n_num, n_dum, n_total = _validar_artefactos(a)
    print(f"Artefactos cargados: {sorted(a.keys())}")
    print(f"  threshold = {a['threshold']:.4f}")
    print(f"  img_size = {a['img_size']}")
    print(f"  vector completo = {n_num} numericas + {n_dum} dummies = {n_total} features")
    print(f"  feature_positions shape = {a['feature_positions'].shape} (validado == {n_total})")
    print(f"  top_categories keys = {len(a['top_categories'])}")
    print(f"  scaler type = {type(a['scaler']).__name__}")
