
"""T32 - Auditoria de preprocesamiento V2/V3 (solo lectura).

No entrena, no predice y no utiliza la prueba final.
"""

from pathlib import Path
from datetime import datetime
import ast
import hashlib
import json

from neutralizacion_v2 import neutralizar_v2

# ==========================================
# T32 - AUDITORIA DE PREPROCESAMIENTO
# SEMINARIO DE INVESTIGACION 2
# ==========================================

BASE = Path(__file__).resolve().parent
MODELOS = BASE / "modelos"
EVIDENCIAS = BASE / "evidencias"

T13 = BASE / "T13.py"
T14 = BASE / "T14.py"
NEUTRALIZADOR = BASE / "neutralizacion_v2.py"

CONFIG = MODELOS / "config_semantico.json"
CONFIG_V2 = MODELOS / "config_semantico_v2.json"

MODELO_CLASICO = MODELOS / "detector_clasico_v2.joblib"
MODELO_SEMANTICO = MODELOS / "detector_semantico_v2.joblib"

INVENTARIO = EVIDENCIAS / "21_insumos_piloto.json"
DIAGNOSTICO = EVIDENCIAS / "31_diagnostico_v2_v3.json"

SALIDA_JSON = (
    EVIDENCIAS / "32_auditoria_preprocesamiento.json"
)

SALIDA_TXT = (
    EVIDENCIAS / "32_resumen_preprocesamiento.txt"
)

# ==========================================
# 1. FUNCIONES AUXILIARES
# ==========================================

def sha256_archivo(ruta):
    resultado = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(1024 * 1024), b""
        ):
            resultado.update(bloque)

    return resultado.hexdigest()


def cargar_json(ruta):
    with ruta.open(
        "r", encoding="utf-8-sig"
    ) as archivo:
        return json.load(archivo)


def analizar_python(ruta):
    codigo = ruta.read_text(
        encoding="utf-8-sig"
    )

    return ast.parse(
        codigo, filename=ruta.name
    )


def utiliza_neutralizacion(arbol):
    return any(
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "map"
        and any(
            isinstance(arg, ast.Name)
            and arg.id == "neutralizar_v2"
            for arg in nodo.args
        )
        for nodo in ast.walk(arbol)
    )


def usa_columna(arbol, columna):
    return any(
        isinstance(nodo, ast.Subscript)
        and isinstance(nodo.slice, ast.Constant)
        and nodo.slice.value == columna
        for nodo in ast.walk(arbol)
    )


def usa_funcion(arbol, nombre):
    return any(
        isinstance(nodo, ast.Call)
        and (
            (
                isinstance(nodo.func, ast.Name)
                and nodo.func.id == nombre
            )
            or (
                isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == nombre
            )
        )
        for nodo in ast.walk(arbol)
    )


# ==========================================
# 2. VERIFICAR ARCHIVOS NECESARIOS
# ==========================================

requeridos = [
    T13,
    T14,
    NEUTRALIZADOR,
    CONFIG,
    CONFIG_V2,
    MODELO_CLASICO,
    MODELO_SEMANTICO,
    INVENTARIO,
    DIAGNOSTICO
]

for ruta in requeridos:
    if not ruta.is_file():
        raise SystemExit(
            f"ERROR: No se encuentra {ruta}"
        )

# Evitar sobrescribir evidencias anteriores
if SALIDA_JSON.exists() or SALIDA_TXT.exists():
    raise SystemExit(
        "ERROR: Ya existen evidencias T32. "
        "No se sobrescribieron."
    )


# ==========================================
# 3. INSPECCION DEL CODIGO DE T13 Y T14
# ==========================================

arbol_t13 = analizar_python(T13)
arbol_t14 = analizar_python(T14)

analizar_python(NEUTRALIZADOR)

# Comprobar columnas utilizadas
for nombre, arbol in [
    ("T13", arbol_t13),
    ("T14", arbol_t14)
]:

    if not (
        usa_columna(arbol, "subject")
        and usa_columna(arbol, "body")
    ):
        raise SystemExit(
            f"ERROR: {nombre} no utiliza subject y body."
        )

    if not utiliza_neutralizacion(arbol):
        raise SystemExit(
            f"ERROR: {nombre} no aplica neutralizar_v2."
        )


# ==========================================
# 4. INSPECCION DEL DETECTOR CLASICO
# ==========================================

if not (
    usa_funcion(arbol_t13, "Pipeline")
    and usa_funcion(arbol_t13, "TfidfVectorizer")
    and usa_funcion(arbol_t13, "LogisticRegression")
):
    raise SystemExit(
        "ERROR: La arquitectura de T13 no coincide."
    )


# ==========================================
# 5. INSPECCION DEL DETECTOR SEMANTICO
# ==========================================

if not (
    usa_funcion(arbol_t14, "SentenceTransformer")
    and usa_funcion(arbol_t14, "LogisticRegression")
    and usa_funcion(arbol_t14, "get_max_seq_length")
):
    raise SystemExit(
        "ERROR: La arquitectura de T14 no coincide."
    )


# ==========================================
# 6. VERIFICAR CONFIGURACION DEL ENCODER
# ==========================================

config = cargar_json(CONFIG)
config_v2 = cargar_json(CONFIG_V2)

for clave in ["modelo_encoder", "revision"]:

    if not config.get(clave):
        raise SystemExit(
            f"ERROR: Falta {clave} en config_semantico.json."
        )

    if config_v2.get(clave) != config[clave]:
        raise SystemExit(
            f"ERROR: No coincide {clave} "
            "entre configuraciones."
        )


if config_v2.get("neutralizacion") != "neutralizacion_v2.py":
    raise SystemExit(
        "ERROR: Configuracion V2 no identifica "
        "el neutralizador."
    )


if (
    config_v2.get("modelo_clasificador")
    != MODELO_SEMANTICO.name
):
    raise SystemExit(
        "ERROR: Configuracion V2 no identifica "
        "el modelo semantico."
    )


# ==========================================
# 7. VERIFICAR INTEGRIDAD SHA-256
# ==========================================

inventario = cargar_json(INVENTARIO)
t31 = cargar_json(DIAGNOSTICO)

hashes_modelos = {}

for ruta in [
    MODELO_CLASICO,
    MODELO_SEMANTICO
]:

    hash_actual = sha256_archivo(ruta)

    hash_esperado = inventario.get(
        "modelos", {}
    ).get(ruta.name)

    if not hash_esperado or hash_actual != hash_esperado:
        raise SystemExit(
            f"ERROR: SHA-256 del modelo "
            f"no coincide: {ruta.name}"
        )

    hashes_modelos[ruta.name] = hash_actual


# ==========================================
# 8. VERIFICAR CODIGO CONTRA T31
# ==========================================

hashes_scripts = {}

for ruta in [
    T13,
    T14,
    NEUTRALIZADOR
]:

    hash_actual = sha256_archivo(ruta)

    hash_esperado = t31.get(
        "hashes_codigo", {}
    ).get(ruta.name)

    if not hash_esperado or hash_actual != hash_esperado:
        raise SystemExit(
            f"ERROR: Script diferente de T31: {ruta.name}"
        )

    hashes_scripts[ruta.name] = hash_actual


# ==========================================
# 9. PRUEBAS SINTETICAS DE NEUTRALIZACION
# ==========================================

# Se utilizan ejemplos inventados.
# No se leen mensajes originales del dataset.

pruebas = [
    (
        "URL",
        "Visita https://ejemplo.com/ruta",
        "URL_NEUTRALIZADA"
    ),
    (
        "Correo",
        "Escribe a usuario@ejemplo.org",
        "EMAIL_NEUTRALIZADO"
    ),
    (
        "Dominio",
        "Consulta portal.ejemplo.com",
        "DOMINIO_NEUTRALIZADO"
    ),
    (
        "Numero",
        "Referencia 12345678",
        "NUMERO_NEUTRALIZADO"
    )
]

resultados_pruebas = []

for nombre, entrada, marcador in pruebas:

    resultado = neutralizar_v2(entrada)

    correcto = marcador in resultado

    idempotente = (
        neutralizar_v2(resultado) == resultado
    )

    resultados_pruebas.append({
        "control": nombre,
        "correcto": correcto,
        "idempotente": idempotente
    })

    if not correcto or not idempotente:
        raise SystemExit(
            f"ERROR: Fallo prueba V2: {nombre}"
        )


# ==========================================
# 10. PREPARAR DIAGNOSTICO
# ==========================================

registro = {
    "fecha": datetime.now().astimezone().isoformat(),

    "fase": "T32 - Auditoria del preprocesamiento real",

    "detector_clasico": (
        "subject + body -> neutralizar_v2 -> "
        "TF-IDF -> regresion logistica"
    ),

    "detector_semantico": (
        "subject + body -> neutralizar_v2 -> "
        "encoder -> regresion logistica"
    ),

    "encoder": config["modelo_encoder"],

    "revision_encoder": config["revision"],

    "truncables_entrenamiento_registrados": (
        config_v2.get("truncables_train")
    ),

    "truncables_validacion_registrados": (
        config_v2.get("truncables_val")
    ),

    "hashes_modelos": hashes_modelos,

    "hashes_scripts": hashes_scripts,

    "pruebas_neutralizacion": resultados_pruebas,

    "diferentes_v2_v3_aprobados": t31.get(
        "mensajes_v2_v3_diferentes"
    ),

    "iguales_v2_v3_aprobados": t31.get(
        "mensajes_v2_v3_iguales"
    ),

    "equivalencia_v2_v3": "NO_DEMOSTRADA",

    "revision_preprocesamiento": "ESTATICA",

    "entrenamiento_ejecutado": False,

    "predicciones_ejecutadas": False,

    "modelos_modificados": False,

    "prueba_final_utilizada": False,

    "protocolo_congelado": False
}


# ==========================================
# 11. GUARDAR EVIDENCIA JSON
# ==========================================

EVIDENCIAS.mkdir(
    parents=True,
    exist_ok=True
)

SALIDA_JSON.write_text(
    json.dumps(
        registro,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# ==========================================
# 12. GENERAR REPORTE FINAL
# ==========================================

lineas = [
    "T32 - AUDITORIA DE PREPROCESAMIENTO REAL",
    "=======================================",

    f"Fecha: {registro['fecha']}",

    "T13: subject + body y neutralizacion V2 "
    "antes de TF-IDF.",

    "T14: subject + body y neutralizacion V2 "
    "antes del encoder.",

    "Modelo clasico: Pipeline TF-IDF "
    "+ regresion logistica.",

    "Modelo semantico: encoder externo "
    "+ regresion logistica.",

    "Version del encoder: COINCIDENTE "
    "entre configuraciones.",

    "SHA-256 de los dos modelos: "
    "VERIFICADOS con T21.",

    "SHA-256 de los scripts: "
    "VERIFICADOS con T31.",

    (
        "Pruebas sinteticas V2: "
        f"{len(resultados_pruebas)}/{len(pruebas)}."
    ),

    (
        "V2/V3 diferentes en T31: "
        f"{registro['diferentes_v2_v3_aprobados']}."
    ),

    (
        "V2/V3 iguales en T31: "
        f"{registro['iguales_v2_v3_aprobados']}."
    ),

    "Equivalencia V2/V3: NO DEMOSTRADA.",

    "Truncamiento semantico: "
    "PENDIENTE DE CONTROL EN INFERENCIA.",

    "Modelos: SIN MODIFICACIONES.",

    "Entrenamiento: NO EJECUTADO.",

    "Predicciones: NO EJECUTADAS.",

    "Prueba final: NO UTILIZADA.",

    "Protocolo congelado: NO.",

    "",

    "T32 FINALIZADO."
]

SALIDA_TXT.write_text(
    "\n".join(lineas),
    encoding="utf-8"
)

print("\n".join(lineas))

print("\nARCHIVOS GENERADOS:")
print(SALIDA_JSON)
print(SALIDA_TXT)
