
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import pandas as pd

# ============================================
# T21 - CONTROL DE INSUMOS EXPERIMENTALES
# SEMINARIO DE INVESTIGACION 2
# ============================================

BASE = Path(__file__).resolve().parent
PILOTO = BASE / "data" / "piloto_privado"
PROCESSED = BASE / "data" / "processed"
MODELOS = BASE / "modelos"
EVIDENCIAS = BASE / "evidencias"

EXCEL = PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"
MANIFIESTO = PILOTO / "manifiesto_piloto_aprobado.csv"
PARTICIONES = PROCESSED / "manifiesto_particiones.csv"

SALIDA_JSON = EVIDENCIAS / "21_insumos_piloto.json"
SALIDA_TXT = EVIDENCIAS / "21_control_insumos.txt"

MODELOS_REQUERIDOS = [
    MODELOS / "detector_clasico_v2.joblib",
    MODELOS / "detector_semantico_v2.joblib"
]

def sha_archivo(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()

def sha_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()

# 1. Comprobar archivos
archivos = [
    EXCEL, MANIFIESTO, PARTICIONES,
    *MODELOS_REQUERIDOS
]

for archivo in archivos:
    if not archivo.is_file():
        raise SystemExit(
            f"ERROR: Archivo faltante: {archivo}"
        )

# 2. Leer documentos
df = pd.read_excel(
    EXCEL, dtype=str, keep_default_na=False
)

manifest = pd.read_csv(
    MANIFIESTO, dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

part = pd.read_csv(
    PARTICIONES, dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

# 3. Verificar seleccion
aprobados = df[
    (df["revision_v3"].str.strip().str.upper() == "APROBADO")
    & (df["apto_para_IA"].str.strip().str.upper() == "SI")
].copy()

if len(df) != 30 or len(aprobados) != 26:
    raise SystemExit("Distribucion del piloto inesperada.")

if len(manifest) != 26:
    raise SystemExit("Manifiesto incompleto.")

if aprobados["id_par"].duplicated().any():
    raise SystemExit("Identificadores duplicados.")

# 4. Comprobar hashes de cada mensaje
verificacion = aprobados.merge(
    manifest[
        ["id_par", "row_id", "sha256_texto_v3"]
    ],
    on=["id_par", "row_id"],
    how="outer",
    validate="one_to_one",
    indicator=True
)

if len(verificacion) != 26:
    raise SystemExit("Numero de pares inconsistente.")

if not verificacion["_merge"].eq("both").all():
    raise SystemExit("Inconsistencia del manifiesto.")

for _, fila in verificacion.iterrows():
    hash_actual = sha_texto(
        fila["texto_v3_borrador"]
    )
    if hash_actual != fila["sha256_texto_v3"]:
        raise SystemExit(
            f"Texto modificado: {fila['id_par']}"
        )

# 5. Verificar procedencia
origen = aprobados[["id_par", "row_id"]].merge(
    part[["row_id", "particion", "Label"]],
    on="row_id",
    validate="one_to_one"
)

if len(origen) != 26:
    raise SystemExit("Procedencia incompleta.")

if not origen["particion"].eq("entrenamiento").all():
    raise SystemExit("Se detectaron datos fuera de entrenamiento.")

if not origen["Label"].eq("1").all():
    raise SystemExit("Existen etiquetas distintas de phishing.")

# 6. Comprobaciones adicionales
patrones = [
    r"https?://",
    r"www\.",
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"
]

for _, fila in aprobados.iterrows():
    texto = fila["texto_v3_borrador"]

    if not texto.strip():
        raise SystemExit("Texto vacio.")

    for patron in patrones:
        if re.search(patron, texto, re.I):
            raise SystemExit(
                f"Posible identificador residual: {fila['id_par']}"
            )

# 7. Preparar inventario sin textos
inventario = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Control previo de insumos",
    "mensajes_iniciales": 30,
    "mensajes_aprobados_registrados": 26,
    "mensajes_excluidos": 4,
    "origen": "entrenamiento",
    "neutralizacion_entrada": "V3",
    "clasificadores_entrenados_con": "V2",
    "modelos": {
        ruta.name: sha_archivo(ruta)
        for ruta in MODELOS_REQUERIDOS
    },
    "sha256_manifiesto": sha_archivo(MANIFIESTO),
    "mensajes": [
        {
            "id_par": fila["id_par"],
            "row_id": fila["row_id"],
            "sha256": sha_texto(
                fila["texto_v3_borrador"]
            )
        }
        for _, fila in aprobados.iterrows()
    ],
    "variantes_ia_generadas": 0,
    "prueba_final_utilizada": False,
    "protocolo_generacion_congelado": False,
    "nota": (
        "El piloto no proporciona estimaciones "
        "independientes de rendimiento."
    )
}

# Evitar cambiar silenciosamente el inventario
if SALIDA_JSON.exists():
    anterior = json.loads(
        SALIDA_JSON.read_text(encoding="utf-8")
    )
    previo = dict(anterior)
    actual = dict(inventario)
    previo.pop("fecha", None)
    actual.pop("fecha", None)

    if previo != actual:
        raise SystemExit(
            "Los insumos difieren del inventario previo. "
            "Revisar los cambios antes de continuar."
        )
else:
    SALIDA_JSON.write_text(
        json.dumps(
            inventario, indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

reporte = [
    "T21 - CONTROL DE INSUMOS DEL PILOTO",
    "==================================",
    f"Fecha: {inventario['fecha']}",
    "Registros iniciales: 30",
    "Aprobados registrados: 26",
    "Excluidos: 4",
    "Hashes de mensajes: VERIFICADOS",
    "Procedencia: ENTRENAMIENTO",
    "Etiqueta: PHISHING",
    "Modelos V2: VERIFICADOS",
    "Prueba final: NO UTILIZADA",
    "Variantes IA: NO GENERADAS",
    "",
    "PENDIENTE:",
    "Definir el generador y parametros.",
    "Congelar el protocolo completo.",
    "Realizar las pruebas exploratorias.",
    "",
    "T21 FINALIZADO."
]

resultado = "\n".join(reporte)
SALIDA_TXT.write_text(resultado, encoding="utf-8")
print(resultado)
