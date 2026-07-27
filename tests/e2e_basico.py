# -*- coding: utf-8 -*-
"""
Prueba basica de extremo a extremo del aplicativo LINE:
  1. Arranque del backend (uvicorn via server.py) en un puerto de prueba.
  2. GET /api/health   -> estado y modelos cargados.
  3. GET /api/modelos  -> listado de modelos.
  4. POST /api/prefactura/analizar con un CSV real de data/datos_prueba/
     (modelo_selector=ambos: ejercita CNN corregido + XGBoost), pasando un
     adres_result de contingencia para NO tocar el scraper externo.

Ejecucion (Python con los requirements de LINE, incl. TensorFlow):

    cd <raiz de LINE>
    python tests/e2e_basico.py [puerto]

Sale con codigo 0 si todo pasa. No modifica datos ni modelos.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
BASE = f"http://127.0.0.1:{PUERTO}"

# Unico paciente de prueba cuyo documento existe como id_paciente en linea.db
# (el resto de la tabla usa ids sinteticos PAC-xxxxx, y la validacion estricta
# del endpoint exige encontrar el documento en la BD local). Su prefactura de
# prueba factura exactamente los 2 items de HC de la atencion ATN-JEF-000001.
DOCUMENTO = "1005711681"
ID_ATENCION = "ATN-JEF-000001"
CSV_PRUEBA = RAIZ / "data" / "datos_prueba" / "prefacturas" / DOCUMENTO / "prefactura_ATN-JEF-000001.csv"

fallos = []


def check(nombre, cond, detalle=""):
    print(f"  [{'OK ' if cond else 'FALLO'}] {nombre}" + (f" — {detalle}" if detalle else ""))
    if not cond:
        fallos.append(nombre)


def main():
    assert CSV_PRUEBA.exists(), f"No existe el CSV de prueba: {CSV_PRUEBA}"

    print(f"1) Arrancando backend (uvicorn) en :{PUERTO} ...")
    env = dict(os.environ, LINE_E2E="1")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1",
         "--port", str(PUERTO), "--log-level", "warning"],
        cwd=str(RAIZ), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
    )
    try:
        # El primer arranque carga TensorFlow: dar tiempo generoso
        salud = None
        for _ in range(180):
            if proc.poll() is not None:
                print(proc.stdout.read()[-4000:])
                raise RuntimeError("El servidor termino antes de estar listo")
            try:
                salud = requests.get(f"{BASE}/api/health", timeout=2).json()
                break
            except requests.RequestException:
                time.sleep(2)
        check("arranque: /api/health responde", salud is not None)
        if salud is None:
            return

        print(f"2) /api/health -> {json.dumps(salud, ensure_ascii=False)}")
        check("health.status presente", "status" in salud, salud.get("status", ""))
        check("health.n_filas_cruce > 0", salud.get("n_filas_cruce", 0) > 0,
              f"n_filas_cruce={salud.get('n_filas_cruce')}")
        check("algun modelo local cargado (CNN o XGBoost)",
              bool(salud.get("modelo_cargado") or salud.get("xgboost_cargado")),
              f"cnn={salud.get('modelo_cargado')} xgb={salud.get('xgboost_cargado')}")

        print("3) /api/modelos ...")
        modelos = requests.get(f"{BASE}/api/modelos", timeout=10).json()
        ids = [m.get("id") for m in modelos.get("modelos", [])]
        check("listado de modelos con cnn_local y xgboost_local",
              {"cnn_local", "xgboost_local"} <= set(ids), f"ids={ids}")

        print(f"4) POST /api/prefactura/analizar ({CSV_PRUEBA.name}, modelo_selector=ambos) ...")
        adres_stub = json.dumps({"fuente": "no_disponible", "error": "BDUA_NO_DISPONIBLE",
                                 "mensaje": "stub e2e: sin consulta externa"})
        with open(CSV_PRUEBA, "rb") as f:
            resp = requests.post(
                f"{BASE}/api/prefactura/analizar",
                files={"file": (CSV_PRUEBA.name, f, "text/csv")},
                data={"tipo_doc": "CC", "num_doc": DOCUMENTO, "eps": "",
                      "id_atencion": ID_ATENCION, "modelo_selector": "ambos",
                      "adres_result": adres_stub},
                timeout=300,
            )
        check("analizar responde 200", resp.status_code == 200, f"status={resp.status_code}")
        if resp.status_code != 200:
            print(resp.text[:1500])
            return
        r = resp.json()

        resumen = r.get("resumen", {})
        check("resumen con recomendacion valida",
              resumen.get("recomendacion") in ("APROBAR", "REVISAR", "RECHAZAR"),
              f"recomendacion={resumen.get('recomendacion')} — {str(resumen.get('motivo_recomendacion'))[:90]}")
        check("validacion estricta aprobada (paciente demo en BD local)",
              r.get("paciente", {}).get("encontrado_db_local") is True)

        cruces = r.get("cruces", [])
        check("hay cruces analizados", len(cruces) > 0, f"n_cruces={len(cruces)}")

        modelos_r = r.get("modelos", {})
        rx = modelos_r.get("xgboost_local") or {}
        check("XGBoost disponible en la respuesta", rx.get("disponible") is True,
              str(rx.get("error", ""))[:120])
        if rx.get("disponible"):
            check("XGBoost: threshold del artefacto (~0.8964)",
                  abs(rx.get("threshold", 0) - 0.8964321608040201) < 1e-6,
                  f"threshold={rx.get('threshold')}")
            check("XGBoost: una probabilidad por cruce",
                  len(rx.get("probabilidades", [])) == len(cruces))

        rc = modelos_r.get("cnn_local") or {}
        cnn_ok = rc.get("disponible") is True and not rc.get("error")
        check("CNN ejecuto sin error (fix R1 en accion)", cnn_ok, str(rc.get("error", ""))[:120])
        if cnn_ok:
            probs = rc.get("probabilidades", [])
            check("CNN: una probabilidad por cruce", len(probs) == len(cruces))
            check("CNN: probabilidades en [0,1]",
                  all(0.0 <= p <= 1.0 for p in probs), str([round(p, 3) for p in probs]))
            check("CNN: threshold del artefacto presente", 0.0 < rc.get("threshold", 0) < 1.0,
                  f"threshold={rc.get('threshold')}")

        con_probs = [c for c in cruces if "cnn_probabilidad" in c or "xgb_probabilidad" in c]
        check("los cruces traen probabilidades por modelo", len(con_probs) == len(cruces),
              f"{len(con_probs)}/{len(cruces)}")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("5) Backend detenido.")

    print()
    if fallos:
        print(f"E2E: {len(fallos)} verificacion(es) fallida(s): {fallos}")
        sys.exit(1)
    print("E2E: TODAS las verificaciones pasaron.")
    sys.exit(0)


if __name__ == "__main__":
    main()
