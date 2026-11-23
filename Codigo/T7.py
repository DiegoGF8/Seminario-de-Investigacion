
from pathlib import Path
from datetime import datetime
from time import perf_counter
import json
import re

import joblib
import numpy as np
import pandas as pd

from huggingface_hub import HfApi
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score
)

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"
MODELOS = BASE / "modelos"

MODELOS.mkdir(exist_ok=True)
EVIDENCIAS.mkdir(exist_ok=True)

SEMILLA = 20261121
UMBRAL = 0.50
MODELO = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# 1. VERIFICAR LOS DATOS
archivos = list(RAW.glob("*.csv"))
if len(archivos) != 1:
    raise SystemExit("Se requiere exactamente un CSV.")

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

if manifest.groupby("cluster_id")["particion"].nunique().gt(1).any():
    raise SystemExit("Hay fuga entre particiones.")

# 2. MISMA NEUTRALIZACION DE T6
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

textos = (
    df["subject"].fillna("").astype(str)
    + " "
    + df["body"].fillna("").astype(str)
).map(neutralizar)

train = manifest["particion"].eq("entrenamiento")
val = manifest["particion"].eq("validacion")

if train.sum() != 476 or val.sum() != 119:
    raise SystemExit("Particiones inesperadas.")

X_train = textos[train].tolist()
X_val = textos[val].tolist()
y_train = df.loc[train, "Label"].astype(int)
y_val = df.loc[val, "Label"].astype(int)

if any(not x for x in X_train + X_val):
    raise SystemExit("Hay textos vacios.")

if set(X_train) & set(X_val):
    raise SystemExit("Textos repetidos entre particiones.")

# 3. DESCARGAR ENCODER CON REVISION REGISTRADA
print("Consultando revision del modelo...")

revision = HfApi().model_info(MODELO).sha

print("Revision:", revision)
print("Cargando modelo multilingue...")

encoder = SentenceTransformer(
    MODELO,
    revision=revision,
    device="cpu"
)

longitud_maxima = encoder.get_max_seq_length()
tokenizer = encoder._first_module().tokenizer

def contar_excesos(lista):
    if longitud_maxima is None:
        return 0
    return sum(
        len(tokenizer.encode(
            t,
            add_special_tokens=True,
            truncation=False
        )) > longitud_maxima
        for t in lista
    )

excesos_train = contar_excesos(X_train)
excesos_val = contar_excesos(X_val)

# 4. EXTRAER EMBEDDINGS CON ENCODER CONGELADO
print("Generando embeddings de entrenamiento...")

inicio = perf_counter()

emb_train = encoder.encode(
    X_train,
    batch_size=8,
    show_progress_bar=True,
    convert_to_numpy=True
)

tiempo_embeddings_train = perf_counter() - inicio

# 5. ENTRENAR CLASIFICADOR LIGERO
clasificador = LogisticRegression(
    class_weight="balanced",
    max_iter=2000,
    random_state=SEMILLA
)

inicio = perf_counter()
clasificador.fit(emb_train, y_train)
tiempo_ajuste = perf_counter() - inicio

# 6. VALIDAR SIN ABRIR PRUEBA FINAL
print("Validando detector semantico...")

inicio = perf_counter()

emb_val = encoder.encode(
    X_val,
    batch_size=8,
    show_progress_bar=True,
    convert_to_numpy=True
)

probabilidades = clasificador.predict_proba(emb_val)[:, 1]
predicciones = (probabilidades >= UMBRAL).astype(int)

tiempo_validacion = perf_counter() - inicio

tn, fp, fn, tp = confusion_matrix(
    y_val, predicciones, labels=[0, 1]
).ravel()

fpr = fp / (fp + tn)
fnr = fn / (fn + tp)

# 7. DOCUMENTAR RESULTADOS
reporte = [
    "DETECTOR SEMANTICO - VALIDACION",
    "================================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    f"Encoder: {MODELO}",
    f"Revision: {revision}",
    f"Longitud maxima tokens: {longitud_maxima}",
    f"Mensajes truncables entrenamiento: {excesos_train}",
    f"Mensajes truncables validacion: {excesos_val}",
    f"Dimensiones embedding: {emb_train.shape[1]}",
    f"Umbral: {UMBRAL}",
    "",
    f"Entrenamiento: {len(X_train)}",
    f"Validacion: {len(X_val)}",
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
    f"Tiempo embeddings entrenamiento (s): {tiempo_embeddings_train:.4f}",
    f"Tiempo ajuste clasificador (s): {tiempo_ajuste:.4f}",
    f"Tiempo validacion lote (s): {tiempo_validacion:.4f}"
]

print("\n".join(reporte))

# 8. GUARDAR MODELO Y EVIDENCIAS
joblib.dump(
    clasificador,
    MODELOS / "detector_semantico.joblib"
)

configuracion = {
    "modelo_encoder": MODELO,
    "revision": revision,
    "longitud_maxima": longitud_maxima,
    "umbral": UMBRAL,
    "semilla": SEMILLA,
    "dispositivo": "cpu",
    "batch_size": 8,
    "neutralizacion": "Misma funcion de T6.py",
    "entrenamiento": len(X_train),
    "validacion": len(X_val),
    "truncables_train": excesos_train,
    "truncables_val": excesos_val
}

(MODELOS / "config_semantico.json").write_text(
    json.dumps(configuracion, indent=2),
    encoding="utf-8"
)

pd.DataFrame({
    "row_id": manifest.loc[val, "row_id"].to_numpy(),
    "etiqueta_real": y_val.to_numpy(),
    "prediccion": predicciones,
    "probabilidad_phishing": probabilidades
}).to_csv(
    PROCESSED / "predicciones_validacion_semantico.csv",
    index=False
)

(EVIDENCIAS / "06_validacion_detector_semantico.txt").write_text(
    "\n".join(reporte),
    encoding="utf-8"
)

print("\nDETECTOR SEMANTICO GUARDADO")
print("Evidencias generadas correctamente")
