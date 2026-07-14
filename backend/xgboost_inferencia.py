"""
xgboost_inferencia.py
=====================
Modulo de inferencia para el modelo XGBoost de auditoria medica.
Carga el modelo entrenado (modelo_xgboost.pkl) y los artefactos
(artefactos_xgboost.pkl) para predecir inconsistencias.

Alineado con 01_entrenamiento_xgboost.py:
  - Features numericas: diferencia_cantidad, ratio_cantidad, coincide_codigo_cups,
    tiene_soporte_clinico, cantidad_facturada, cantidad_realizada,
    valor_unitario, valor_total, edad, dias_diferencia
  - Features categoricas: tipo_atencion, sede, eps_atencion, tipo_afiliacion,
    tipo_item, grupo_etario, sexo, diag_encoded
  - LabelEncoder + StandardScaler desde artefactos
  - Diagnostico top-N + OTRO

LINE - Auditor Medico Digital - Capstone SIC 2025
"""
from __future__ import annotations

import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE / "models"
MODEL_PATH = MODELS_DIR / "modelo_xgboost.pkl"
ARTIFACTS_PATH = MODELS_DIR / "artefactos_xgboost.pkl"

_modelo = None
_artefactos = None


def modelo_xgboost_disponible() -> bool:
    """Verifica si el modelo XGBoost esta entrenado y disponible."""
    return MODEL_PATH.exists() and ARTIFACTS_PATH.exists()


def cargar_modelo_xgboost():
    """Carga el modelo XGBoost y artefactos desde disco."""
    global _modelo, _artefactos

    if _modelo is not None and _artefactos is not None:
        return _modelo, _artefactos

    if not modelo_xgboost_disponible():
        return None, None

    try:
        with open(MODEL_PATH, "rb") as f:
            _modelo = pickle.load(f)
        with open(ARTIFACTS_PATH, "rb") as f:
            _artefactos = pickle.load(f)
        print("[OK] Modelo XGBoost cargado")
        return _modelo, _artefactos
    except Exception as e:
        _modelo = None
        _artefactos = None
        print(f"[WARN] Modelo XGBoost NO cargado: {e}")
        return None, None


def predecir_xgboost(df_input: pd.DataFrame) -> dict:
    """
    Pipeline de prediccion XGBoost (replica exacta del entrenamiento):
    1. Crear features derivadas (ratio, coincide_cups, soporte, dias)
    2. Imputar nulos numericos
    3. Diagnostico top-N + OTRO
    4. LabelEncoder para categoricas
    5. StandardScaler para numericas
    6. Predecir

    Args:
        df_input: DataFrame con columnas del cruce HC vs PF

    Returns:
        dict con probabilidades, predicciones, threshold, etc.
    """
    modelo, artefactos = cargar_modelo_xgboost()

    if modelo is None or artefactos is None:
        return {
            "error": "Modelo XGBoost no disponible. Ejecute 01_entrenamiento_xgboost.py",
            "disponible": False,
        }

    threshold = artefactos.get("threshold", 0.5)
    scaler = artefactos.get("scaler")
    label_encoders = artefactos.get("label_encoders", {})
    # El script guarda como "feature_names" (no "features")
    features = artefactos.get("feature_names", artefactos.get("features", []))
    top_diag = list(artefactos.get("top_diag", []))
    num_features = artefactos.get("num_features", [])

    df = df_input.copy()

    # ── 1. Crear features derivadas (mismo orden que entrenamiento) ──
    if "cantidad_facturada" in df.columns and "cantidad_realizada" in df.columns:
        df["cantidad_facturada"] = pd.to_numeric(df["cantidad_facturada"], errors="coerce").fillna(0)
        df["cantidad_realizada"] = pd.to_numeric(df["cantidad_realizada"], errors="coerce").fillna(0)
        df["diferencia_cantidad"] = df["cantidad_facturada"] - df["cantidad_realizada"]
        df["ratio_cantidad"] = df["cantidad_facturada"] / (df["cantidad_realizada"] + 1)

    if "codigo_cups_facturado" in df.columns and "codigo_cups" in df.columns:
        cups_pf = df["codigo_cups_facturado"].fillna("").astype(str).str.strip()
        cups_hc = df["codigo_cups"].fillna("").astype(str).str.strip()
        df["coincide_codigo_cups"] = ((cups_pf != "") & (cups_hc != "") & (cups_pf == cups_hc)).astype(int)

    if "soporte_clinico" in df.columns:
        df["soporte_clinico"] = df["soporte_clinico"].fillna("NO").astype(str).str.upper()
        df["tiene_soporte_clinico"] = (df["soporte_clinico"] == "SI").astype(int)

    if "valor_unitario" not in df.columns:
        df["valor_unitario"] = 0
    if "valor_total" not in df.columns:
        df["valor_total"] = 0
    if "dias_diferencia" not in df.columns:
        df["dias_diferencia"] = 0
    if "edad" not in df.columns:
        df["edad"] = 30

    # ── 2. Imputar nulos numericos ──
    for col in num_features:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── 3. Diagnostico top-N + OTRO ──
    if "diagnostico_principal_cie10" in df.columns and top_diag:
        df["diag_encoded"] = df["diagnostico_principal_cie10"].fillna("SIN_DATO").astype(str).apply(
            lambda x: x if x in top_diag else "OTRO"
        )
    else:
        df["diag_encoded"] = "OTRO"

    # ── 4. Codificar categoricas con LabelEncoder ──
    for col, le in label_encoders.items():
        if col in df.columns:
            # Agregar categorias faltantes al encoder
            for val in ["SIN_DATO", "OTRO"]:
                if val not in le.classes_:
                    le.classes_ = np.append(le.classes_, val)
            df[col] = df[col].fillna("SIN_DATO").astype(str)
            df[col] = df[col].apply(lambda x: x if x in le.classes_ else "SIN_DATO")
            df[col] = le.transform(df[col])

    # ── 5. Seleccionar features en el orden correcto ──
    X = pd.DataFrame()
    for feat in features:
        if feat in df.columns:
            X[feat] = df[feat]
        else:
            X[feat] = 0

    # ── 6. Escalar numericas ──
    if scaler is not None:
        cols_a_escalar = [c for c in num_features if c in X.columns]
        if cols_a_escalar:
            X[cols_a_escalar] = scaler.transform(X[cols_a_escalar])

    # ── 7. Predecir ──
    try:
        probs = modelo.predict_proba(X)[:, 1]
    except Exception:
        probs = modelo.predict(X)
        if probs.max() > 1.0:
            probs = (probs - probs.min()) / (probs.max() - probs.min() + 1e-7)

    preds = (probs > threshold).astype(int)

    return {
        "probabilidades": probs.tolist(),
        "predicciones": preds.tolist(),
        "threshold": float(threshold),
        "consistentes": int((preds == 0).sum()),
        "inconsistentes": int((preds == 1).sum()),
        "disponible": True,
    }


if __name__ == "__main__":
    disp = modelo_xgboost_disponible()
    print(f"Modelo XGBoost disponible: {disp}")
    if disp:
        m, a = cargar_modelo_xgboost()
        print(f"  Feature names: {len(a.get('feature_names', a.get('features', [])))}")
        print(f"  Num features: {a.get('num_features', [])}")
        print(f"  Cat encoders: {list(a.get('label_encoders', {}).keys())}")
        print(f"  Top diag: {len(a.get('top_diag', []))}")
        print(f"  Threshold: {a.get('threshold', 'N/A')}")
