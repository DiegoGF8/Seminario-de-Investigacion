
from pathlib import Path
from datetime import datetime
import hashlib
import json

import joblib
import numpy as np
import pandas as pd

from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score,
    recall_score, f1_score, confusion_matrix
)

from neutralizacion_v2 import neutralizar_v2

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
MODELOS = BASE / "modelos"
EVIDENCIAS = BASE / "evidencias"

SEMILLA = 20261121
UMBRAL = 0.50

# 1. VERIFICAR ARCHIVOS
archivos = list(RAW.glob("*.csv"))
if len(archivos) != 1:
    raise SystemExit("Se requiere un unico CSV.")

df = pd.read_csv(
    archivos[0], sep=",",
    encoding="utf-8-sig", low_memory=False
)

m = pd.read_csv(
    PROCESSED / "manifiesto_particiones.csv"
)

assert len(df) == len(m) == 1395
assert np.array_equal(m["row_id"], np.arange(len(df)))
assert np.array_equal(
    df["hash"].astype(str),
    m["hash"].astype(str)
)
assert np.array_equal(df["Label"], m["Label"])
assert not m.groupby("cluster_id")["particion"].nunique().gt(1).any()

# 2. SOLO DESARROLLO
train = m["particion"].eq("entrenamiento")
val = m["particion"].eq("validacion")

assert train.sum() == 476
assert val.sum() == 119

desarrollo = df.loc[train | val]

textos = (
    desarrollo["subject"].fillna("").astype(str)
    + " " +
    desarrollo["body"].fillna("").astype(str)
).map(neutralizar_v2)

X_train = textos.loc[train].tolist()
X_val = textos.loc[val].tolist()

y_train = df.loc[train, "Label"].astype(int).to_numpy()
y_val = df.loc[val, "Label"].astype(int).to_numpy()

if any(not x for x in X_train + X_val):
    raise SystemExit("Se encontraron textos vacios.")

if set(X_train) & set(X_val):
    raise SystemExit("Textos repetidos entre particiones.")

# 3. CARGAR MISMO ENCODER DE T7
config = json.loads(
    (MODELOS / "config_semantico.json").read_text(
        encoding="utf-8"
    )
)

print("Cargando encoder multilingue...")
encoder = SentenceTransformer(
    config["modelo_encoder"],
    revision=config["revision"],
    device="cpu"
)

max_tokens = encoder.get_max_seq_length()
tokenizer = encoder._first_module().tokenizer

def contar_truncables(lista):
    return sum(
        len(tokenizer.encode(
            t, add_special_tokens=True,
            truncation=False
        )) > max_tokens
        for t in lista
    )

trunc_train = contar_truncables(X_train)
trunc_val = contar_truncables(X_val)

# 4. EXTRAER EMBEDDINGS
print("Procesando entrenamiento V2...")

emb_train = encoder.encode(
    X_train,
    batch_size=8,
    show_progress_bar=True,
    convert_to_numpy=True
)

print("Procesando validacion V2...")

emb_val = encoder.encode(
    X_val,
    batch_size=8,
    show_progress_bar=True,
    convert_to_numpy=True
)

# 5. ENTRENAR REGRESION LOGISTICA
modelo = LogisticRegression(
    class_weight="balanced",
    max_iter=2000,
    random_state=SEMILLA
)

modelo.fit(emb_train, y_train)

# 6. VALIDACION
prob = modelo.predict_proba(emb_val)[:, 1]
pred = (prob >= UMBRAL).astype(int)

tn, fp, fn, tp = confusion_matrix(
    y_val, pred, labels=[0, 1]
).ravel()

metricas = {
    "Accuracy": accuracy_score(y_val, pred),
    "Precision": precision_score(
        y_val, pred, zero_division=0
    ),
    "Recall": recall_score(
        y_val, pred, zero_division=0
    ),
    "F1": f1_score(y_val, pred, zero_division=0),
    "FPR": fp / (fp + tn),
    "FNR": fn / (fn + tp)
}

# 7. COMPARAR CON VERSION ORIGINAL
v1 = pd.read_csv(
    PROCESSED / "predicciones_validacion_semantico.csv"
)

v2 = pd.DataFrame({
    "row_id": m.loc[val, "row_id"].to_numpy(),
    "etiqueta_real": y_val,
    "prediccion": pred,
    "probabilidad_phishing": prob
})

comparacion = v2.merge(
    v1[["row_id", "etiqueta_real", "prediccion"]],
    on="row_id",
    suffixes=("_v2", "_v1"),
    validate="one_to_one"
)

if len(comparacion) != 119:
    raise SystemExit("Comparacion incompleta.")

if not (
    comparacion["etiqueta_real_v2"]
    == comparacion["etiqueta_real_v1"]
).all():
    raise SystemExit("Etiquetas inconsistentes.")

cambios = int((
    comparacion["prediccion_v2"]
    != comparacion["prediccion_v1"]
).sum())

# 8. GUARDAR MODELO V2 POR SEPARADO
ruta_modelo = MODELOS / "detector_semantico_v2.joblib"
joblib.dump(modelo, ruta_modelo)

hash_modelo = hashlib.sha256(
    ruta_modelo.read_bytes()
).hexdigest()

v2.to_csv(
    PROCESSED / "predicciones_validacion_semantico_v2.csv",
    index=False
)

config_v2 = {
    **config,
    "neutralizacion": "neutralizacion_v2.py",
    "modelo_clasificador": "detector_semantico_v2.joblib",
    "umbral": UMBRAL,
    "truncables_train": trunc_train,
    "truncables_val": trunc_val,
    "estado": "Validacion de desarrollo"
}

(MODELOS / "config_semantico_v2.json").write_text(
    json.dumps(config_v2, indent=2),
    encoding="utf-8"
)

# 9. GENERAR EVIDENCIA
reporte = [
    "T14 - DETECTOR SEMANTICO V2",
    "==========================",
    f"Fecha: {datetime.now().astimezone().isoformat()}",
    f"Semilla: {SEMILLA}",
    "Neutralizacion: V2",
    f"Encoder: {config['modelo_encoder']}",
    f"Revision: {config['revision']}",
    "",
    "Entrenamiento: 476",
    "Validacion: 119",
    "Prueba final: NO UTILIZADA",
    "",
    "METRICAS:"
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
    f"Limite de tokens: {max_tokens}",
    f"Truncables entrenamiento: {trunc_train}",
    f"Truncables validacion: {trunc_val}",
    f"SHA256 modelo V2: {hash_modelo}",
    "",
    "Modelo V1 conservado.",
    "Limitacion de truncamiento pendiente.",
    "Prueba final sin utilizar."
])

texto = "\n".join(reporte)
print("\n" + texto)

ruta = EVIDENCIAS / "13_validacion_semantico_v2.txt"
ruta.write_text(texto, encoding="utf-8")

print("\nModelo guardado:", ruta_modelo)
print("Evidencia guardada:", ruta)
