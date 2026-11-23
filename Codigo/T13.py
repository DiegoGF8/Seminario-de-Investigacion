
from pathlib import Path
from datetime import datetime
import hashlib

import joblib
import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

from neutralizacion_v2 import neutralizar_v2

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
MODELOS = BASE / "modelos"
EVIDENCIAS = BASE / "evidencias"

SEMILLA = 20261121
UMBRAL = 0.50

MODELOS.mkdir(exist_ok=True)
EVIDENCIAS.mkdir(exist_ok=True)

# 1. CARGAR DATOS
archivos = list(RAW.glob("*.csv"))
if len(archivos) != 1:
    raise SystemExit("Se requiere un unico CSV.")

df = pd.read_csv(
    archivos[0],
    sep=",",
    encoding="utf-8-sig",
    low_memory=False
)

manifest = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

if len(df) != len(manifest):
    raise SystemExit("Cantidad de registros diferente.")

if not np.array_equal(
    manifest["row_id"].to_numpy(),
    np.arange(len(df))
):
    raise SystemExit("Orden incorrecto.")

if not np.array_equal(
    df["hash"].astype(str).to_numpy(),
    manifest["hash"].astype(str).to_numpy()
):
    raise SystemExit("Hashes inconsistentes.")

if not np.array_equal(
    df["Label"].to_numpy(),
    manifest["Label"].to_numpy()
):
    raise SystemExit("Etiquetas inconsistentes.")

if manifest.groupby(
    "cluster_id"
)["particion"].nunique().gt(1).any():
    raise SystemExit("Fuga entre particiones.")

# 2. UTILIZAR SOLO DESARROLLO
train = manifest["particion"].eq("entrenamiento")
val = manifest["particion"].eq("validacion")

if train.sum() != 476 or val.sum() != 119:
    raise SystemExit("Particiones inesperadas.")

indices_desarrollo = train | val

# Evitar procesar textos de prueba final
datos = df.loc[indices_desarrollo].copy()

textos = (
    datos["subject"].fillna("").astype(str)
    + " " +
    datos["body"].fillna("").astype(str)
).map(neutralizar_v2)

X_train = textos.loc[train]
X_val = textos.loc[val]

y_train = df.loc[train, "Label"].astype(int)
y_val = df.loc[val, "Label"].astype(int)

if X_train.str.strip().eq("").any():
    raise SystemExit("Textos vacios en entrenamiento.")

if X_val.str.strip().eq("").any():
    raise SystemExit("Textos vacios en validacion.")

if set(X_train) & set(X_val):
    raise SystemExit("Textos repetidos entre particiones.")

# 3. ENTRENAR MODELO CON V2
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
            class_weight="balanced",
            max_iter=2000,
            random_state=SEMILLA
        )
    )
])

print("Entrenando detector clasico V2...")
modelo.fit(X_train, y_train)

# 4. VALIDACION
probabilidades = modelo.predict_proba(
    X_val
)[:, 1]

predicciones = (
    probabilidades >= UMBRAL
).astype(int)

tn, fp, fn, tp = confusion_matrix(
    y_val,
    predicciones,
    labels=[0, 1]
).ravel()

fpr = fp / (fp + tn)
fnr = fn / (fn + tp)

metricas = {
    "Accuracy": accuracy_score(y_val, predicciones),
    "Precision": precision_score(
        y_val, predicciones, zero_division=0
    ),
    "Recall": recall_score(
        y_val, predicciones, zero_division=0
    ),
    "F1": f1_score(
        y_val, predicciones, zero_division=0
    ),
    "FPR": fpr,
    "FNR": fnr
}

# 5. COMPARAR CON V1
ruta_v1 = (
    PROCESSED /
    "predicciones_validacion_clasico.csv"
)

v1 = pd.read_csv(ruta_v1)

resultado_v2 = pd.DataFrame({
    "row_id": manifest.loc[val, "row_id"].to_numpy(),
    "etiqueta_real": y_val.to_numpy(),
    "prediccion": predicciones,
    "probabilidad_phishing": probabilidades
})

comparacion = resultado_v2.merge(
    v1[["row_id", "etiqueta_real", "prediccion"]],
    on="row_id",
    suffixes=("_v2", "_v1"),
    validate="one_to_one"
)

if len(comparacion) != len(resultado_v2):
    raise SystemExit("Comparacion incompleta.")

if not (
    comparacion["etiqueta_real_v1"]
    == comparacion["etiqueta_real_v2"]
).all():
    raise SystemExit("Etiquetas inconsistentes entre V1 y V2.")

cambios = int(
    (
        comparacion["prediccion_v1"]
        != comparacion["prediccion_v2"]
    ).sum()
)

# 6. GUARDAR MODELO V2
ruta_modelo = MODELOS / "detector_clasico_v2.joblib"
joblib.dump(modelo, ruta_modelo)

with ruta_modelo.open("rb") as f:
    hash_modelo = hashlib.file_digest(
        f, "sha256"
    ).hexdigest()

resultado_v2.to_csv(
    PROCESSED /
    "predicciones_validacion_clasico_v2.csv",
    index=False
)

# 7. REPORTE
reporte = [
    "T13 - VALIDACION DEL DETECTOR CLASICO V2",
    "======================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    "Tratamiento: neutralizacion V2",
    "",
    f"Entrenamiento: {len(X_train)}",
    f"Validacion: {len(X_val)}",
    "Prueba final: NO UTILIZADA",
    "",
    "METRICAS V2:"
]

for nombre, valor in metricas.items():
    reporte.append(f"{nombre}: {valor:.4f}")

reporte.extend([
    "",
    f"TN: {tn}",
    f"FP: {fp}",
    f"FN: {fn}",
    f"TP: {tp}",
    "",
    f"Predicciones diferentes V1 vs V2: {cambios}",
    f"SHA256 modelo V2: {hash_modelo}",
    "",
    "Modelo original V1 conservado.",
    "Modelo V2 guardado por separado.",
    "Prueba final sin utilizar."
])

texto = "\n".join(reporte)

print("\n" + texto)

ruta_reporte = (
    EVIDENCIAS /
    "12_validacion_clasico_v2.txt"
)

ruta_reporte.write_text(
    texto, encoding="utf-8"
)

print("\nModelo:", ruta_modelo)
print("Reporte:", ruta_reporte)
