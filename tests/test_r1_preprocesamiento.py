# -*- coding: utf-8 -*-
"""
Pruebas del fix R1: la imagen de inferencia del CNN debe construirse con el
vector completo [numericas escaladas | dummies] mapeado contra
feature_positions, igual que en el entrenamiento (notebook 08 del Capstone).

Cubre:
  1. Equivalencia contra una REPLICA INDEPENDIENTE del preprocesamiento de
     entrenamiento (reimplementada aqui, sin reutilizar los internos del
     modulo para la codificacion).
  2. Numericas y muestra representativa de dummies en su pixel correcto
     (consciente de colisiones del t-SNE: se valida donde la feature es la
     "ultima escritora" del pixel, la misma semantica del entrenamiento).
  3. Regresion: la construccion ANTIGUA (solo dummies, posiciones corridas)
     habria sido detectada por estas mismas verificaciones.
  4. Inferencia real de extremo a extremo con los artefactos y el modelo
     actuales de LINE (models/*.pkl + .keras), sin reemplazarlos.

Ejecucion (requiere un Python con pandas, scikit-learn 1.5.x y TensorFlow,
p. ej. el venv 3.12 de la validacion o el entorno de requirements.txt):

    cd <raiz de LINE>
    python -m unittest tests.test_r1_preprocesamiento -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

import preprocesamiento as pre  # noqa: E402


def fila_extrema():
    """Fila con numericas extremas (escaladas quedan lejos de 0) y categorias del top."""
    return {
        "edad": 90, "cantidad_realizada": 5, "cantidad_facturada": 5,
        "valor_unitario": 900000, "valor_total": 4500000, "mes_atencion": 12,
        "sexo": "F", "eps_atencion": "Salud Total EPS", "tipo_afiliacion": "Contributivo",
        "ciudad": "Bogota", "tipo_documento": "CC", "tipo_atencion": "Ambulatoria",
        "sede": "Sede Norte", "tipo_item": "consulta", "soporte_clinico": "SI",
        "grupo_etario": "80+", "diagnostico_principal_cie10": "I10X",
        "medico_tratante": "MED-001", "profesional_responsable": "MED-001",
    }


def replica_entrenamiento(fila: dict, art: dict) -> tuple[np.ndarray, np.ndarray]:
    """
    Reimplementacion INDEPENDIENTE del preprocesamiento de entrenamiento
    (nb 08: fillna -> scaler -> pd.get_dummies alineado a cat_columns ->
    vector [num | dummies] -> grilla por feature_positions, ultimo indice gana).
    Devuelve (vector_completo, grilla_cruda).
    """
    num_cols = list(art["num_features"])
    cat_cols = list(art["cat_columns"])
    cat_orig = list(art["cat_features"])
    top_cats = art["top_categories"]
    positions = art["feature_positions"]
    grid = art["img_size"]

    num = art["scaler"].transform(
        pd.DataFrame([fila])[num_cols].astype(float).fillna(0))[0].astype(np.float32)

    dummies = np.zeros(len(cat_cols), dtype=np.float32)
    for i, dcol in enumerate(cat_cols):
        # columna original por prefijo MAS LARGO (independiente del modulo)
        candidatos = [c for c in cat_orig if dcol.startswith(c + "_")]
        if not candidatos:
            continue
        col = max(candidatos, key=len)
        valor_dummy = dcol[len(col) + 1:]
        crudo = str(fila.get(col, "SIN_DATO"))
        tops = top_cats.get(col, [])
        if tops and crudo not in tops:
            crudo = f"OTRO_{col}"
        if crudo == valor_dummy:
            dummies[i] = 1.0

    vector = np.concatenate([num, dummies])
    grilla = np.zeros((grid, grid), dtype=np.float32)
    for i, (x, y) in enumerate(positions):
        grilla[int(y), int(x)] = vector[i]
    return vector, grilla


def ultimo_escritor(positions) -> dict:
    """{(y, x): indice de la ultima feature que escribe ese pixel}."""
    quien = {}
    for i, (x, y) in enumerate(positions):
        quien[(int(y), int(x))] = i
    return quien


class TestR1Preprocesamiento(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.art = pre.cargar_artefactos()
        cls.n_num, cls.n_dum, cls.n_total = pre._validar_artefactos(cls.art)
        cls.fila = fila_extrema()
        cls.df = pd.DataFrame([cls.fila])
        cls.vector_rep, cls.grilla_rep = replica_entrenamiento(cls.fila, cls.art)
        cls.X_line = pre._vector_completo(cls.df, cls.art)
        cls.grilla_line = pre._build_image(cls.X_line[0], cls.art["feature_positions"],
                                           cls.art["img_size"])
        cls.escritor = ultimo_escritor(cls.art["feature_positions"])

    # ── 1. Coherencia de artefactos y equivalencia con la replica ──────────

    def test_01_artefactos_coherentes(self):
        self.assertEqual(self.n_num, len(self.art["num_features"]))
        self.assertEqual(self.n_dum, len(self.art["cat_columns"]))
        self.assertEqual(self.n_total, len(self.art["feature_positions"]),
                         "positions debe tener una entrada por CADA feature del vector completo")

    def test_02_vector_line_igual_a_replica(self):
        self.assertEqual(self.X_line.shape, (1, self.n_total))
        np.testing.assert_allclose(self.X_line[0], self.vector_rep, rtol=0, atol=1e-6,
                                   err_msg="El vector de LINE difiere de la replica de entrenamiento")

    def test_03_grilla_line_igual_a_replica(self):
        np.testing.assert_allclose(self.grilla_line, self.grilla_rep, rtol=0, atol=1e-6,
                                   err_msg="La grilla de LINE difiere de la replica de entrenamiento")

    def test_04_imagen_normalizada_igual_a_replica(self):
        imgs = pre.construir_imagenes(self.df)
        gmin, gmax = self.art["global_min"], self.art["global_max"]
        esperada = np.clip((self.grilla_rep - gmin) / (gmax - gmin + 1e-7), 0, 1)
        self.assertEqual(imgs.shape, (1, self.art["img_size"], self.art["img_size"], 3))
        for canal in range(3):
            np.testing.assert_allclose(imgs[0, :, :, canal], esperada, rtol=0, atol=1e-5)

    # ── 2. Numericas y dummies en su pixel ─────────────────────────────────

    def test_05_numericas_en_su_pixel(self):
        positions = self.art["feature_positions"]
        num_escaladas = self.vector_rep[:self.n_num]
        comprobadas = 0
        for i in range(self.n_num):
            y, x = int(positions[i][1]), int(positions[i][0])
            if self.escritor[(y, x)] == i:  # sin colision posterior en ese pixel
                self.assertAlmostEqual(float(self.grilla_line[y, x]), float(num_escaladas[i]),
                                       places=5, msg=f"numerica '{pre.NUM_COLS[i]}' fuera de su pixel")
                comprobadas += 1
        self.assertGreaterEqual(comprobadas, 4,
                                "muy pocas numericas verificables sin colision; revisar artefactos")

    def test_06_dummies_representativas_en_su_pixel(self):
        positions = self.art["feature_positions"]
        activas = [j for j in range(self.n_dum) if self.vector_rep[self.n_num + j] == 1.0]
        self.assertGreaterEqual(len(activas), 8, "la fila de prueba debe activar varias dummies")
        comprobadas = 0
        for j in activas:
            i = self.n_num + j
            y, x = int(positions[i][1]), int(positions[i][0])
            if self.escritor[(y, x)] == i:
                self.assertEqual(float(self.grilla_line[y, x]), 1.0,
                                 msg=f"dummy '{self.art['cat_columns'][j]}' fuera de su pixel")
                comprobadas += 1
        self.assertGreaterEqual(comprobadas, 5,
                                "muestra de dummies verificables demasiado pequena")

    # ── 3. El bug anterior habria sido detectado ───────────────────────────

    def test_07_construccion_antigua_es_detectada(self):
        """Reconstruye la grilla como el codigo previo al fix (solo dummies,
        pintadas en las primeras posiciones) y verifica que las mismas
        comprobaciones de esta suite la rechazan."""
        positions = self.art["feature_positions"]
        grid = self.art["img_size"]
        dummies = self.vector_rep[self.n_num:]

        vieja = np.zeros((grid, grid), dtype=np.float32)
        for j in range(min(len(dummies), len(positions))):  # comportamiento del bug
            x, y = int(positions[j][0]), int(positions[j][1])
            vieja[y, x] = dummies[j]

        # (a) difiere de la replica de entrenamiento
        self.assertFalse(np.allclose(vieja, self.grilla_rep, atol=1e-6),
                         "la construccion antigua NO deberia coincidir con el entrenamiento")
        # (b) ninguna numerica llega a su pixel
        num_ok = sum(
            abs(float(vieja[int(positions[i][1]), int(positions[i][0])])
                - float(self.vector_rep[i])) < 1e-6
            and self.vector_rep[i] != 0
            for i in range(self.n_num))
        self.assertEqual(num_ok, 0, "el bug antiguo dejaba las numericas fuera de la imagen")
        # (c) el guard dimensional del modulo la bloquea de raiz
        with self.assertRaises(ValueError):
            pre._build_image(dummies, positions, grid)

    def test_08_validacion_dimensiones_artefactos(self):
        falso = dict(self.art)
        falso["feature_positions"] = self.art["feature_positions"][:-1]  # 1 posicion menos
        with self.assertRaises(ValueError):
            pre._validar_artefactos(falso)

    # ── 4. Inferencia real con artefactos y modelo actuales ───────────────

    def test_09_inferencia_real(self):
        df = pd.DataFrame([
            self.fila,
            {**self.fila, "cantidad_facturada": 1, "cantidad_realizada": 1,
             "valor_unitario": 50000, "valor_total": 50000, "edad": 35,
             "grupo_etario": "18-39", "sexo": "M"},
            {**self.fila, "soporte_clinico": "NO"},
        ])
        r = pre.predecir_inconsistencia(df)
        self.assertTrue({"probabilidades", "predicciones", "threshold",
                         "consistentes", "inconsistentes"} <= set(r))
        self.assertEqual(len(r["probabilidades"]), 3)
        self.assertEqual(len(r["predicciones"]), 3)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in r["probabilidades"]))
        self.assertTrue(all(p in (0, 1) for p in r["predicciones"]))
        self.assertAlmostEqual(r["threshold"], float(self.art["threshold"]), places=6)
        self.assertEqual(r["consistentes"] + r["inconsistentes"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
