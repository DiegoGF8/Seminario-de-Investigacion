
from pathlib import Path
from datetime import datetime
from time import perf_counter
import hashlib
import re

import joblib
import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score
)

# CONFIGURACION
BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"
MODELOS = BASE / "modelos"

MODELOS.mkdir(exist_ok=True)
EVIDENCIAS.mkdir(exist_ok=True)

SEMILLA = 20261121
UMBRAL = 0.50

# 1. CARGAR DATOS Y PARTICIONES
archivos = list(RAW.glob("*.csv"))

if len(archivos) != 1:
    raise SystemExit("Se requiere exactamente un CSV.")

df = pd.read_csv(
    archivos[0],
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

manifiesto = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

if len(df) != len(manifiesto):
    raise SystemExit("Cantidad de registros inconsistente.")

if not np.array_equal(
    manifiesto["row_id"].to_numpy(),
    np.arange(len(df))
):
    raise SystemExit("Orden de registros incorrecto.")

if not np.array_equal(
    df["hash"].astype(str).to_numpy(),
    manifiesto["hash"].astype(str).to_numpy()
):
    raise SystemExit("Hashes no coinciden.")

if not np.array_equal(
    df["Label"].to_numpy(),
    manifiesto["Label"].to_numpy()
):
    raise SystemExit("Etiquetas no coinciden.")

if (
    manifiesto.groupby("cluster_id")["particion"]
    .nunique().gt(1).any()
):
    raise SystemExit("Fuga entre particiones.")

# 2. NEUTRALIZACION INICIAL DEL TEXTO
# Las mismas reglas se aplicaran posteriormente
# a originales y variantes IA.

def neutralizar(texto):
    texto = str(texto)

    texto = re.sub(
        r"\b(?:https?://|www\.)[^\s<>\"']+",
        " URL_NEUTRALIZADA ",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        " EMAIL_NEUTRALIZADO ",
        texto
    )

    return re.sub(r"\s+", " ", texto).strip()

asuntos = df["subject"].fillna("").astype(str)
cuerpos = df["body"].fillna("").astype(str)

textos = (
    asuntos + " " + cuerpos
).map(neutralizar)

# 3. SEPARAR SOLO ENTRENAMIENTO Y VALIDACION
particiones = manifiesto["particion"]

train_mask = particiones.eq("entrenamiento")
val_mask = particiones.eq("validacion")

if train_mask.sum() != 476 or val_mask.sum() != 119:
    raise SystemExit("Tamano de desarrollo inesperado.")

if (
    textos[train_mask | val_mask]
    .str.strip().eq("").any()
):
    raise SystemExit("Hay textos vacios en desarrollo.")

X_train = textos[train_mask]
y_train = df.loc[train_mask, "Label"].astype(int)

X_val = textos[val_mask]
y_val = df.loc[val_mask, "Label"].astype(int)

if set(y_train.unique()) != {0, 1}:
    raise SystemExit("Faltan clases de entrenamiento.")

# 4. VERIFICAR DUPLICADOS TRAS NEUTRALIZAR
train_unicos = set(X_train)
val_unicos = set(X_val)

coincidencias = len(train_unicos & val_unicos)

if coincidencias:
    raise SystemExit(
        f"Se encontraron {coincidencias} textos "
        "iguales entre entrenamiento y validacion "
        "despues de neutralizar. Revisar particiones."
    )

# 5. CONSTRUIR MODELO CLASICO
modelo = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_features=30000,
            strip_accents="unicode",
            sublinear_tf=True
        )
    ),
    (
        "clasificador",
        LogisticRegression(
            penalty="l2",
            class_weight="balanced",
            max_iter=2000,
            random_state=SEMILLA
        )
    )
])

# 6. ENTRENAMIENTO
print("Entrenando clasificador TF-IDF...")

inicio = perf_counter()
modelo.fit(X_train, y_train)
tiempo_entrenamiento = perf_counter() - inicio

# 7. VALIDACION (SIN UTILIZAR PRUEBA FINAL)
inicio = perf_counter()
probabilidades = modelo.predict_proba(X_val)[:, 1]
tiempo_validacion = perf_counter() - inicio

predicciones = (
    probabilidades >= UMBRAL
).astype(int)

tn, fp, fn, tp = confusion_matrix(
    y_val, predicciones, labels=[0, 1]
).ravel()

fpr = fp / (fp + tn) if (fp + tn) else 0
fnr = fn / (fn + tp) if (fn + tp) else 0

# 8. CALCULAR METRICAS
reporte = [
    "DETECTOR CLASICO - VALIDACION",
    "============================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    "Modelo: TF-IDF + Regresion Logistica L2",
    "TF-IDF: unigramas y bigramas",
    "Neutralizacion: URLs y emails explicitos",
    f"Umbral: {UMBRAL}",
    "",
    f"Entrenamiento: {len(X_train)} correos",
    f"Validacion: {len(X_val)} correos",
    "Prueba final: NO UTILIZADA",
    "",
    f"Accuracy: {accuracy_score(y_val, predicciones):.4f}",
    f"Precision: {precision_score(y_val, predicciones, zero_division=0):.4f}",
    f"Recall: {recall_score(y_val, predicciones, zero_division=0):.4f}",
    f"F1: {f1_score(y_val, predicciones, zero_division=0):.4f}",
    f"FPR: {fpr:.4f}",
    f"FNR: {fnr:.4f}",
    "",
    f"TN: {tn}",
    f"FP: {fp}",
    f"FN: {fn}",
    f"TP: {tp}",
    "",
    f"Tiempo entrenamiento (s): {tiempo_entrenamiento:.4f}",
    f"Tiempo validacion lote (s): {tiempo_validacion:.4f}",
    f"Promedio por mensaje del lote (ms): {1000*tiempo_validacion/len(X_val):.4f}"
]

# 9. GUARDAR MODELO
ruta_modelo = MODELOS / "detector_clasico.joblib"
joblib.dump(modelo, ruta_modelo)

with ruta_modelo.open("rb") as f:
    hash_modelo = hashlib.file_digest(
        f, "sha256"
    ).hexdigest()

reporte.append(f"SHA256 modelo: {hash_modelo}")

# 10. GUARDAR PREDICCIONES DE VALIDACION
salida = pd.DataFrame({
    "row_id": manifiesto.loc[val_mask, "row_id"].to_numpy(),
    "etiqueta_real": y_val.to_numpy(),
    "prediccion": predicciones,
    "probabilidad_phishing": probabilidades
})

salida.to_csv(
    PROCESSED / "predicciones_validacion_clasico.csv",
    index=False
)

ruta_reporte = (
    EVIDENCIAS / "05_validacion_detector_clasico.txt"
)

ruta_reporte.write_text(
    "\n".join(reporte),
    encoding="utf-8"
)

print("\n".join(reporte))
print("\nModelo guardado:", ruta_modelo)
print("Evidencia guardada:", ruta_reporte)
