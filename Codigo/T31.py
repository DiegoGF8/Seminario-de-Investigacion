
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re

import pandas as pd

# ============================================
# T31 - AUDITORIA METODOLOGICA V2 / V3
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

INVENTARIO = EVIDENCIAS / "21_insumos_piloto.json"
PROTOCOLO = EVIDENCIAS / "28_seleccion_protocolo.json"
RESULTADOS_T30 = EVIDENCIAS / "30_consolidacion_t29.json"

ARCHIVOS_MODELOS = [
    MODELOS / "detector_clasico_v2.joblib",
    MODELOS / "detector_semantico_v2.joblib"
]

SALIDA_CSV = EVIDENCIAS / "31_diferencias_v2_v3.csv"
SALIDA_JSON = EVIDENCIAS / "31_diagnostico_v2_v3.json"
SALIDA_TXT = EVIDENCIAS / "31_resumen_metodologico.txt"

# ============================================
# 1. FUNCIONES
# ============================================

def sha_archivo(ruta):
    return hashlib.sha256(
        ruta.read_bytes()
    ).hexdigest()


def sha_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def normalizar(texto):
    return re.sub(
        r"\s+", " ", str(texto)
    ).strip()


# ============================================
# 2. VERIFICAR ARCHIVOS
# ============================================

requeridos = [
    EXCEL, MANIFIESTO, PARTICIONES,
    INVENTARIO, PROTOCOLO, RESULTADOS_T30,
    *ARCHIVOS_MODELOS
]

for ruta in requeridos:
    if not ruta.is_file():
        raise SystemExit(
            f"ERROR: Archivo no encontrado: {ruta}"
        )

for ruta in [SALIDA_CSV, SALIDA_JSON, SALIDA_TXT]:
    if ruta.exists():
        raise SystemExit(
            f"Ya existe {ruta.name}. "
            "No se sobrescribieron evidencias."
        )

# ============================================
# 3. CARGAR REGISTROS
# ============================================

df = pd.read_excel(
    EXCEL,
    dtype=str,
    keep_default_na=False
)

manifest = pd.read_csv(
    MANIFIESTO,
    dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

particiones = pd.read_csv(
    PARTICIONES,
    dtype=str,
    encoding="utf-8-sig",
    keep_default_na=False
)

inventario = json.loads(
    INVENTARIO.read_text(encoding="utf-8")
)

protocolo = json.loads(
    PROTOCOLO.read_text(encoding="utf-8")
)

t30 = json.loads(
    RESULTADOS_T30.read_text(encoding="utf-8")
)

columnas = {
    "id_par", "row_id",
    "texto_v2_referencia",
    "texto_v3_borrador",
    "revision_v3",
    "apto_para_IA"
}

if not columnas.issubset(df.columns):
    raise SystemExit(
        "ERROR: Faltan columnas del piloto."
    )

if len(df) != 30:
    raise SystemExit(
        "ERROR: Se esperaban 30 registros."
    )

if df["id_par"].duplicated().any():
    raise SystemExit(
        "ERROR: Identificadores duplicados."
    )

# ============================================
# 4. VERIFICAR SELECCION DEL PILOTO
# ============================================

estados = df["revision_v3"].str.strip().str.upper()
aptitudes = df["apto_para_IA"].str.strip().str.upper()

aprobados = df[
    (estados == "APROBADO")
    & (aptitudes == "SI")
].copy()

excluidos = df[
    (estados == "EXCLUIR_PILOTO")
    & (aptitudes == "NO")
].copy()

if len(aprobados) != 26 or len(excluidos) != 4:
    raise SystemExit(
        "ERROR: Distribucion del piloto incorrecta."
    )

if len(manifest) != 26:
    raise SystemExit(
        "ERROR: Manifiesto de aprobados incorrecto."
    )

verificados = aprobados.merge(
    manifest[
        ["id_par", "row_id", "sha256_texto_v3"]
    ],
    on=["id_par", "row_id"],
    how="outer",
    indicator=True,
    validate="one_to_one"
)

if len(verificados) != 26:
    raise SystemExit(
        "ERROR: Correspondencia incompleta."
    )

if not verificados["_merge"].eq("both").all():
    raise SystemExit(
        "ERROR: Identificadores no coincidentes."
    )

hashes_t21 = {
    item["id_par"]: item["sha256"]
    for item in inventario["mensajes"]
}

# ============================================
# 5. ANALIZAR DIFERENCIAS V2/V3
# ============================================

comparaciones = []

for _, fila in verificados.iterrows():

    ident = fila["id_par"]

    v2 = fila["texto_v2_referencia"]
    v3 = fila["texto_v3_borrador"]

    hash_v3 = sha_texto(v3)

    if hash_v3 != fila["sha256_texto_v3"]:
        raise SystemExit(
            f"Hash V3 incorrecto: {ident}"
        )

    if hashes_t21.get(ident) != hash_v3:
        raise SystemExit(
            f"Insumo modificado desde T21: {ident}"
        )

    diferente = normalizar(v2) != normalizar(v3)

    comparaciones.append({
        "id_par": ident,
        "row_id": fila["row_id"],
        "longitud_v2": len(v2),
        "longitud_v3": len(v3),
        "cambio_textual": "SI" if diferente else "NO",
        "sha256_v2": sha_texto(v2),
        "sha256_v3": hash_v3
    })

tabla = pd.DataFrame(comparaciones)

modificados = int(
    tabla["cambio_textual"].eq("SI").sum()
)

sin_cambios = int(
    tabla["cambio_textual"].eq("NO").sum()
)

# ============================================
# 6. CONFIRMAR PROCEDENCIA
# ============================================

requeridas_part = {"row_id", "particion", "Label"}

if not requeridas_part.issubset(particiones.columns):
    raise SystemExit(
        "ERROR: Manifiesto de particiones incompleto."
    )

if particiones["row_id"].duplicated().any():
    raise SystemExit(
        "ERROR: row_id duplicados en particiones."
    )

origen = aprobados[["id_par", "row_id"]].merge(
    particiones[[
        "row_id", "particion", "Label"
    ]],
    on="row_id",
    how="left",
    validate="one_to_one"
)

if len(origen) != 26:
    raise SystemExit(
        "ERROR: Procedencia incompleta."
    )

if not origen["particion"].eq("entrenamiento").all():
    raise SystemExit(
        "ERROR: Hay registros fuera de entrenamiento."
    )

if not origen["Label"].eq("1").all():
    raise SystemExit(
        "ERROR: Hay registros con otra etiqueta."
    )

# ============================================
# 7. VERIFICAR MODELOS Y CODIGO
# ============================================

hashes_modelos = {}

for ruta in ARCHIVOS_MODELOS:
    hash_actual = sha_archivo(ruta)

    hash_anterior = inventario[
        "modelos"
    ].get(ruta.name)

    if hash_actual != hash_anterior:
        raise SystemExit(
            f"ERROR: Modelo modificado: {ruta.name}"
        )

    hashes_modelos[ruta.name] = hash_actual

scripts = [
    BASE / "T13.py",
    BASE / "T14.py",
    BASE / "neutralizacion_v2.py"
]

archivos_codigo = {}

for ruta in scripts:
    archivos_codigo[ruta.name] = (
        sha_archivo(ruta)
        if ruta.is_file()
        else "NO_ENCONTRADO"
    )

# ============================================
# 8. VERIFICAR EVIDENCIAS DEL GENERADOR
# ============================================

if protocolo["configuracion_seleccionada"] != "B_CON_EJEMPLOS":
    raise SystemExit(
        "ERROR: Configuracion T28 inesperada."
    )

if t30["configuracion"] != "B_CON_EJEMPLOS":
    raise SystemExit(
        "ERROR: Configuracion T30 diferente."
    )

# ============================================
# 9. GENERAR DIAGNOSTICO
# ============================================

fecha = datetime.now().astimezone().isoformat()

diagnostico = {
    "fecha": fecha,
    "fase": "Auditoria metodologica V2/V3",
    "mensajes_iniciales": 30,
    "mensajes_aprobados": 26,
    "mensajes_excluidos": 4,
    "mensajes_v2_v3_diferentes": modificados,
    "mensajes_v2_v3_iguales": sin_cambios,
    "procedencia": "entrenamiento",
    "etiqueta": "phishing",
    "integridad_t21": "VERIFICADA",
    "integridad_modelos": "VERIFICADA",
    "hashes_modelos": hashes_modelos,
    "hashes_codigo": archivos_codigo,
    "configuracion_generador": "B_CON_EJEMPLOS",
    "estado_configuracion": "PROVISIONAL",
    "equivalencia_preprocesamiento": "NO_DEMOSTRADA",
    "protocolo_congelado": False,
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False,
    "decisiones_pendientes": [
        "Inspeccionar tratamiento de entrada del clasico",
        "Inspeccionar tratamiento del encoder semantico",
        "Determinar efecto de neutralizacion V2/V3",
        "Definir tratamiento identico para cada pareja",
        "Documentar limites de truncamiento",
        "Congelar protocolo antes de prueba final"
    ]
}

# ============================================
# 10. EXPORTAR EVIDENCIAS
# ============================================

tabla.to_csv(
    SALIDA_CSV,
    index=False,
    encoding="utf-8-sig"
)

SALIDA_JSON.write_text(
    json.dumps(
        diagnostico,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

reporte = [
    "T31 - AUDITORIA METODOLOGICA V2/V3",
    "=================================",
    f"Fecha: {fecha}",
    "",
    "PILOTO:",
    "Registros originales seleccionados: 30",
    "Registros aprobados: 26",
    "Registros excluidos: 4",
    f"Referencias V2/V3 diferentes: {modificados}",
    f"Referencias V2/V3 iguales: {sin_cambios}",
    "",
    "INTEGRIDAD:",
    "Hashes de mensajes T21: VERIFICADOS",
    "Hashes de modelos V2: VERIFICADOS",
    "Procedencia: ENTRENAMIENTO",
    "Etiqueta: PHISHING",
    "",
    "PREPROCESAMIENTO:",
    "Equivalencia V2/V3: NO DEMOSTRADA",
    "Inspeccion del codigo: PENDIENTE",
    "Tratamiento de pares: PENDIENTE",
    "",
    "GENERADOR:",
    "Modelo: llama3.2:3b",
    "Configuracion: B_CON_EJEMPLOS",
    "Seleccion: PROVISIONAL",
    "",
    "Prueba final: NO UTILIZADA",
    "Clasificadores: SIN MODIFICACIONES",
    "Protocolo congelado: NO",
    "",
    "CONCLUSION:",
    "La integridad de los insumos esta verificada.",
    "La equivalencia metodologica requiere",
    "inspeccionar el preprocesamiento real.",
    "No se ejecutaron predicciones nuevas.",
    "",
    "T31 FINALIZADO."
]

texto = "\n".join(reporte)

SALIDA_TXT.write_text(
    texto,
    encoding="utf-8"
)

print(texto)

print("\nARCHIVOS GENERADOS:")
print(SALIDA_CSV)
print(SALIDA_JSON)
print(SALIDA_TXT)
