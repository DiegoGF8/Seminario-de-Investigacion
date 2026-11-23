
from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib
import json

import pandas as pd

# ==========================================
# T30 - CONSOLIDACION DE VALIDACION T29
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
EVIDENCIAS = BASE / "evidencias"

EXCEL = EVIDENCIAS / "29_revision_controles.xlsx"
ORIGEN = EVIDENCIAS / "29_validacion_generador.json"
PROTOCOLO = EVIDENCIAS / "28_seleccion_protocolo.json"

SALIDA_CSV = EVIDENCIAS / "30_resultados_validacion.csv"
SALIDA_JSON = EVIDENCIAS / "30_consolidacion_t29.json"
SALIDA_TXT = EVIDENCIAS / "30_informe_validacion.txt"

# ==========================================
# 1. VERIFICAR ARCHIVOS
# ==========================================

for ruta in [EXCEL, ORIGEN, PROTOCOLO]:
    if not ruta.is_file():
        raise SystemExit(
            f"ERROR: No existe {ruta}"
        )

for ruta in [SALIDA_CSV, SALIDA_JSON, SALIDA_TXT]:
    if ruta.exists():
        raise SystemExit(
            f"Ya existe {ruta.name}. "
            "No se sobrescribieron evidencias."
        )

df = pd.read_excel(
    EXCEL,
    dtype=str,
    keep_default_na=False
)

datos_t29 = json.loads(
    ORIGEN.read_text(encoding="utf-8")
)

protocolo = json.loads(
    PROTOCOLO.read_text(encoding="utf-8")
)

columnas = {
    "id_control",
    "foco_prueba",
    "texto_original",
    "texto_generado",
    "alertas",
    "conserva_significado",
    "reformulacion_real",
    "decision_manual",
    "observaciones"
}

if not columnas.issubset(df.columns):
    raise SystemExit(
        "ERROR: Faltan columnas obligatorias."
    )

if len(df) != 12:
    raise SystemExit(
        "ERROR: Se esperaban 12 controles."
    )

if df["id_control"].duplicated().any():
    raise SystemExit(
        "ERROR: Existen controles duplicados."
    )

if protocolo["configuracion_seleccionada"] != "B_CON_EJEMPLOS":
    raise SystemExit(
        "ERROR: Configuracion diferente de T28."
    )

if datos_t29["modelo"] != protocolo["modelo"]:
    raise SystemExit(
        "ERROR: El modelo no coincide."
    )

if datos_t29["digest"] != protocolo["digest_modelo"]:
    raise SystemExit(
        "ERROR: El digest del modelo no coincide."
    )

# ==========================================
# 2. VALIDAR CORRESPONDENCIA
# ==========================================

originales = {
    item["id"]: item
    for item in datos_t29["resultados"]
}

if len(originales) != 12:
    raise SystemExit(
        "ERROR: Evidencia T29 incompleta."
    )

resultados = []

for _, fila in df.iterrows():

    ident = fila["id_control"].strip()

    if ident not in originales:
        raise SystemExit(
            f"ERROR: ID desconocido: {ident}"
        )

    referencia = originales[ident]

    if fila["texto_original"] != referencia["original"]:
        raise SystemExit(
            f"Texto original modificado: {ident}"
        )

    if fila["texto_generado"] != referencia["generado"]:
        raise SystemExit(
            f"Texto generado modificado: {ident}"
        )

    significado = (
        fila["conserva_significado"].strip().upper()
    )

    reformulacion = (
        fila["reformulacion_real"].strip().upper()
    )

    decision = (
        fila["decision_manual"].strip().upper()
    )

    observacion = fila["observaciones"].strip()

    if significado not in {"SI", "NO"}:
        raise SystemExit(
            f"Significado sin evaluar: {ident}"
        )

    if reformulacion not in {"SI", "NO"}:
        raise SystemExit(
            f"Reformulacion sin evaluar: {ident}"
        )

    if decision not in {"APROBADO", "RECHAZADO"}:
        raise SystemExit(
            f"Decision incorrecta: {ident}"
        )

    if not observacion:
        raise SystemExit(
            f"Falta observacion: {ident}"
        )

    # Comprobar que las aprobaciones cumplan
    # ambos criterios de revision humana.
    if decision == "APROBADO":
        if significado != "SI" or reformulacion != "SI":
            raise SystemExit(
                f"Aprobacion inconsistente: {ident}"
            )

    alertas = referencia["alertas"]

    if decision == "APROBADO" and alertas:
        raise SystemExit(
            f"Aprobado con alerta automatica: {ident}"
        )

    resultados.append({
        "id_control": ident,
        "foco_prueba": referencia["foco"],
        "conserva_significado": significado,
        "reformulacion_real": reformulacion,
        "decision_manual": decision,
        "alertas_automaticas": "; ".join(alertas),
        "cantidad_alertas": len(alertas),
        "observaciones": observacion
    })

if set(df["id_control"].str.strip()) != set(originales):
    raise SystemExit(
        "Existen controles sin correspondencia."
    )

# ==========================================
# 3. CALCULAR RESULTADOS
# ==========================================

tabla = pd.DataFrame(resultados)

conteo = Counter(tabla["decision_manual"])

aprobados = conteo["APROBADO"]
rechazados = conteo["RECHAZADO"]
total = len(tabla)

alertados = int(
    (tabla["cantidad_alertas"] > 0).sum()
)

rechazados_sin_alerta = tabla[
    (tabla["decision_manual"] == "RECHAZADO")
    & (tabla["cantidad_alertas"] == 0)
]

sin_alertas_ids = (
    rechazados_sin_alerta["id_control"].tolist()
)

tasa_aprobacion = aprobados / total
tasa_rechazo = rechazados / total

# Verificacion de la revision registrada
if aprobados != 7 or rechazados != 5:
    raise SystemExit(
        "Los resultados difieren de la "
        "revision manual documentada."
    )

# ==========================================
# 4. REGISTRAR HALLAZGOS
# ==========================================

hallazgos = [
    {
        "id": "CONTROL_009",
        "tipo": "ALTERACION_TEMPORAL",
        "descripcion": (
            "El generador sustituyo 'despues del viernes' "
            "por 'antes del viernes', invirtiendo "
            "la condicion temporal."
        ),
        "deteccion_automatica": False
    },
    {
        "id": "CONTROL_007",
        "tipo": "AUSENCIA_DE_REFORMULACION",
        "descripcion": (
            "El texto generado reproduce el original."
        ),
        "deteccion_automatica": True
    },
    {
        "id": "CONTROL_010",
        "tipo": "SIN_RESPUESTA_REFORMULADA",
        "descripcion": (
            "El modelo respondio NO_REFORMULABLE."
        ),
        "deteccion_automatica": True
    }
]

# ==========================================
# 5. GENERAR ARCHIVOS
# ==========================================

def sha_archivo(ruta):
    return hashlib.sha256(
        ruta.read_bytes()
    ).hexdigest()

registro = {
    "fecha": datetime.now().astimezone().isoformat(),
    "fase": "Consolidacion de validacion adicional",
    "modelo": datos_t29["modelo"],
    "configuracion": datos_t29["configuracion"],
    "controles_evaluados": total,
    "aprobados": aprobados,
    "rechazados": rechazados,
    "tasa_aprobacion": round(tasa_aprobacion, 4),
    "tasa_rechazo": round(tasa_rechazo, 4),
    "respuestas_con_alertas": alertados,
    "rechazados_sin_alerta": len(
        rechazados_sin_alerta
    ),
    "ids_rechazados_sin_alerta": sin_alertas_ids,
    "hallazgos": hallazgos,
    "sha256_excel": sha_archivo(EXCEL),
    "sha256_t29": sha_archivo(ORIGEN),
    "seleccion_generador": "PROVISIONAL",
    "protocolo_congelado": False,
    "variantes_dataset_generadas": 0,
    "prueba_final_utilizada": False,
    "limitaciones": [
        "Muestra pequena de 12 controles",
        "Datos administrativos sinteticos",
        "No demuestra rendimiento sobre phishing",
        "Revision semantica con criterios conservadores",
        "No se realizaron pruebas independientes finales"
    ]
}

tabla.to_csv(
    SALIDA_CSV,
    index=False,
    encoding="utf-8-sig"
)

SALIDA_JSON.write_text(
    json.dumps(
        registro,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)

reporte = [
    "T30 - CONSOLIDACION DE VALIDACION T29",
    "====================================",
    f"Fecha: {registro['fecha']}",
    f"Modelo: {registro['modelo']}",
    f"Configuracion: {registro['configuracion']}",
    "",
    f"Controles evaluados: {total}",
    f"Aprobados: {aprobados}",
    f"Rechazados: {rechazados}",
    f"Tasa de aprobacion: {tasa_aprobacion:.1%}",
    f"Tasa de rechazo: {tasa_rechazo:.1%}",
    f"Controles con alertas automaticas: {alertados}",
    (
        "Rechazados sin alertas automaticas: "
        f"{len(rechazados_sin_alerta)}"
    ),
    "",
    "CONTROLES RECHAZADOS SIN ALERTA:"
]

reporte.extend(
    sin_alertas_ids or ["Ninguno"]
)

reporte.extend([
    "",
    "HALLAZGOS PRINCIPALES:",
    "CONTROL_009: inversion de condicion temporal.",
    "CONTROL_007: ausencia de reformulacion.",
    "CONTROL_010: respuesta NO_REFORMULABLE.",
    "",
    "CONCLUSION:",
    "El generador funciona, pero presenta",
    "limitaciones de fidelidad semantica.",
    "La revision humana sigue siendo necesaria.",
    "La configuracion B permanece provisional.",
    "",
    "Variantes del dataset: 0",
    "Clasificadores: SIN MODIFICACIONES",
    "Prueba final: NO UTILIZADA",
    "Protocolo congelado: NO",
    "",
    "T30 FINALIZADO."
])

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
