
from pathlib import Path
from datetime import datetime
import hashlib
import json
import pandas as pd

# ==========================================
# T20 - PROTOCOLO EXPERIMENTAL DEL PILOTO
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent

PILOTO = BASE / "data" / "piloto_privado"
PROCESSED = BASE / "data" / "processed"
EVIDENCIAS = BASE / "evidencias"

EXCEL = PILOTO / "Revision_Neutralizacion_Piloto_V3.xlsx"
PARTICIONES = PROCESSED / "manifiesto_particiones.csv"

EVIDENCIAS.mkdir(parents=True, exist_ok=True)

SEMILLA = 20261121

# ==========================================
# 1. LEER ARCHIVOS
# ==========================================

for ruta in [EXCEL, PARTICIONES]:
    if not ruta.is_file():
        raise SystemExit(f"Archivo no encontrado: {ruta}")

df = pd.read_excel(
    EXCEL, dtype=str, keep_default_na=False
)

particiones = pd.read_csv(
    PARTICIONES,
    dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

requeridas = {
    "id_par", "row_id", "texto_v3_borrador",
    "revision_v3", "apto_para_IA"
}

if not requeridas.issubset(df.columns):
    raise SystemExit("Faltan columnas del piloto.")

if len(df) != 30:
    raise SystemExit("Se esperaban 30 registros.")

if df["id_par"].duplicated().any():
    raise SystemExit("Existen ID duplicados.")

if df["row_id"].duplicated().any():
    raise SystemExit("Existen row_id duplicados.")

# ==========================================
# 2. VALIDAR ESTADOS
# ==========================================

df["estado_control"] = (
    df["revision_v3"].str.strip().str.upper()
)

df["apto_control"] = (
    df["apto_para_IA"].str.strip().str.upper()
)

estados_validos = {"APROBADO", "EXCLUIR_PILOTO"}

if not df["estado_control"].isin(estados_validos).all():
    raise SystemExit("Existen estados pendientes.")

aprobados = df[
    df["estado_control"] == "APROBADO"
].copy()

excluidos = df[
    df["estado_control"] == "EXCLUIR_PILOTO"
].copy()

if not aprobados["apto_control"].eq("SI").all():
    raise SystemExit("Aprobacion inconsistente.")

if not excluidos["apto_control"].eq("NO").all():
    raise SystemExit("Exclusion inconsistente.")

if len(aprobados) != 26 or len(excluidos) != 4:
    raise SystemExit("Distribucion inesperada.")

if aprobados["texto_v3_borrador"].str.strip().eq("").any():
    raise SystemExit("Hay textos aprobados vacios.")

# ==========================================
# 3. CONFIRMAR PROCEDENCIA
# ==========================================

columnas_particiones = {
    "row_id", "particion", "Label"
}

if not columnas_particiones.issubset(
    particiones.columns
):
    raise SystemExit(
        "El manifiesto no tiene columnas requeridas."
    )

verificacion = df[["id_par", "row_id"]].merge(
    particiones[[
        "row_id", "particion", "Label"
    ]],
    on="row_id",
    how="left",
    validate="one_to_one",
    indicator=True
)

if not verificacion["_merge"].eq("both").all():
    raise SystemExit(
        "Existen registros sin particion."
    )

if not verificacion["particion"].eq(
    "entrenamiento"
).all():
    raise SystemExit(
        "Se encontraron datos fuera de entrenamiento."
    )

if not verificacion["Label"].eq("1").all():
    raise SystemExit(
        "Se encontraron etiquetas distintas de phishing."
    )

# ==========================================
# 4. CREAR MANIFIESTO DE APROBADOS
# SIN EXPORTAR LOS TEXTOS
# ==========================================

def sha256_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


manifiesto = aprobados[[
    "id_par", "row_id"
]].copy()

manifiesto["sha256_texto_v3"] = [
    sha256_texto(t)
    for t in aprobados["texto_v3_borrador"]
]

manifiesto["estado"] = "APROBADO_PILOTO"

ruta_manifiesto = (
    PILOTO / "manifiesto_piloto_aprobado.csv"
)

manifiesto.to_csv(
    ruta_manifiesto,
    index=False,
    encoding="utf-8-sig"
)

# ==========================================
# 5. DOCUMENTAR PROTOCOLO
# ==========================================

protocolo = {
    "proyecto": "Seminario de Investigacion 2",
    "fase": "Piloto exploratorio",
    "estado": "BORRADOR_PREVIO_A_GENERACION",
    "fecha": datetime.now().astimezone().isoformat(),
    "semilla": SEMILLA,
    "fuente": "SpaPhish",
    "mensajes_iniciales": 30,
    "mensajes_aprobados": len(aprobados),
    "mensajes_excluidos": len(excluidos),
    "procedencia": "Entrenamiento",
    "etiqueta_original": 1,
    "neutralizacion_piloto": "V3",
    "modelos_candidatos": [
        "detector_clasico_v2.joblib",
        "detector_semantico_v2.joblib"
    ],
    "generador_IA": "PENDIENTE_DE_SELECCION",
    "parametros_generacion": "PENDIENTES",
    "variantes_generadas": 0,
    "criterios_piloto": [
        "Conservar correspondencia de cada par",
        "No incluir identificadores reales",
        "No incluir enlaces operativos",
        "No generar solicitudes funcionales de credenciales",
        "Registrar las decisiones de aceptacion",
        "Conservar los textos de referencia",
        "Utilizar ejemplos sinteticos inofensivos"
    ],
    "decisiones_pendientes": [
        "Comprobar la aptitud para el generador elegido",
        "Definir y congelar los parametros de generacion",
        "Resolver el tratamiento equivalente V2 y V3",
        "Definir el procedimiento de evaluacion",
        "Mantener la prueba final reservada"
    ],
    "limitaciones": [
        "Piloto compuesto por mensajes de entrenamiento",
        "Exclusiones aplicadas solo al piloto",
        "La auditoria no certifica anonimizacion",
        "El encoder semantico tiene limite de 128 tokens"
    ],
    "prueba_final_utilizada": False
}

ruta_json = (
    EVIDENCIAS / "20_protocolo_piloto.json"
)

ruta_json.write_text(
    json.dumps(
        protocolo,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

# ==========================================
# 6. GENERAR EVIDENCIA
# ==========================================

def sha256_archivo(ruta):
    return hashlib.sha256(
        ruta.read_bytes()
    ).hexdigest()


reporte = [
    "T20 - PREPARACION DEL PROTOCOLO",
    "================================",
    f"Fecha: {protocolo['fecha']}",
    f"Semilla: {SEMILLA}",
    f"Registros iniciales: {len(df)}",
    f"Aprobados registrados: {len(aprobados)}",
    f"Excluidos: {len(excluidos)}",
    "Origen: entrenamiento",
    "Etiqueta: phishing",
    "Neutralizacion piloto: V3",
    "",
    f"SHA256 Excel: {sha256_archivo(EXCEL)}",
    f"SHA256 manifiesto: {sha256_archivo(ruta_manifiesto)}",
    "",
    "Generacion IA: NO EJECUTADA",
    "Modelos: SIN MODIFICACIONES",
    "Prueba final: NO UTILIZADA",
    "",
    "Protocolo en estado de borrador.",
    "Pendiente definir la equivalencia V2/V3.",
    "Pendiente seleccionar generador y parametros.",
    "No se exportaron textos al manifiesto."
]

resultado = "\n".join(reporte)
print(resultado)

ruta_reporte = (
    EVIDENCIAS / "20_preparacion_piloto.txt"
)

ruta_reporte.write_text(
    resultado,
    encoding="utf-8"
)

print("\nARCHIVOS GENERADOS:")
print(ruta_manifiesto)
print(ruta_json)
print(ruta_reporte)
print("\nT20 FINALIZADO.")
