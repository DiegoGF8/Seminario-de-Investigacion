
"""T33 - Prueba tecnica de inferencia V2 sin reentrenar.

Ejecuta por separado ambos clasificadores para reducir memoria.
Utiliza tres frases inventadas, no datos reales ni prueba final.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

# Limitar hilos ANTES de cargar bibliotecas de calculo.
for variable in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS"
):
    os.environ[variable] = "1"

os.environ["TOKENIZERS_PARALLELISM"] = "false"

BASE = Path(__file__).resolve().parent
MODELOS = BASE / "modelos"
EVIDENCIAS = BASE / "evidencias"

INVENTARIO = EVIDENCIAS / "21_insumos_piloto.json"
CONFIG = MODELOS / "config_semantico_v2.json"

CLASICO = MODELOS / "detector_clasico_v2.joblib"
SEMANTICO = MODELOS / "detector_semantico_v2.joblib"

FINAL_JSON = EVIDENCIAS / "33_control_inferencia.json"
FINAL_TXT = EVIDENCIAS / "33_resumen_inferencia.txt"
BITACORA = EVIDENCIAS / "33_diagnostico_progreso.txt"

TEMP_CLASICO = EVIDENCIAS / "33_temporal_clasico.json"
TEMP_SEMANTICO = EVIDENCIAS / "33_temporal_semantico.json"

CONTROLES = [
    (
        "CONTROL_A",
        "El taller de fotografia comienza el lunes a las diez."
    ),
    (
        "CONTROL_B",
        "La biblioteca estara cerrada manana por mantenimiento."
    ),
    (
        "CONTROL_C",
        "El informe fue enviado a contacto@ejemplo.org "
        "con referencia 12345678."
    )
]


# ==========================================
# 1. FUNCIONES GENERALES
# ==========================================

def sha_archivo(ruta):
    digest = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(1024 * 1024),
            b""
        ):
            digest.update(bloque)

    return digest.hexdigest()


def sha_texto(texto):
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def leer_json(ruta):
    return json.loads(
        ruta.read_text(encoding="utf-8-sig")
    )


def guardar_json(ruta, datos):
    ruta.write_text(
        json.dumps(
            datos,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def registrar(mensaje):
    linea = (
        f"[{datetime.now().astimezone().isoformat()}] "
        f"{mensaje}"
    )

    print(linea, flush=True)

    with BITACORA.open("a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")


# ==========================================
# 2. VALIDAR PROBABILIDADES
# ==========================================

def probabilidades_clase_uno(modelo, entradas):
    clases = [
        int(valor) for valor in modelo.classes_
    ]

    if 0 not in clases or 1 not in clases:
        raise RuntimeError(
            "El modelo no tiene las clases 0 y 1"
        )

    indice = clases.index(1)

    resultado = modelo.predict_proba(
        entradas
    )[:, indice]

    valores = [
        float(x) for x in resultado
    ]

    if len(valores) != len(CONTROLES):
        raise RuntimeError(
            "Cantidad de predicciones inesperada"
        )

    for p in valores:
        if not math.isfinite(p) or not 0 <= p <= 1:
            raise RuntimeError(
                "Probabilidad fuera del intervalo [0,1]"
            )

    return valores


# ==========================================
# 3. PREPARAR TEXTOS DE CONTROL
# ==========================================

def preparar_textos():
    from neutralizacion_v2 import neutralizar_v2

    textos = [
        neutralizar_v2(texto)
        for _, texto in CONTROLES
    ]

    if any(not texto.strip() for texto in textos):
        raise RuntimeError(
            "Un texto quedo vacio tras neutralizacion"
        )

    for texto in textos:
        if neutralizar_v2(texto) != texto:
            raise RuntimeError(
                "La neutralizacion V2 no fue idempotente"
            )

    return textos


# ==========================================
# 4. PROCESO DEL DETECTOR CLASICO
# ==========================================

def trabajador_clasico():
    import joblib

    print(
        "Cargando detector clasico...",
        flush=True
    )

    textos = preparar_textos()

    modelo = joblib.load(CLASICO)

    if not hasattr(modelo, "named_steps"):
        raise RuntimeError(
            "El modelo clasico no es un Pipeline"
        )

    etapas = {
        "tfidf",
        "clasificador"
    }

    if not etapas.issubset(modelo.named_steps):
        raise RuntimeError(
            "Faltan etapas del Pipeline TF-IDF"
        )

    probabilidades = probabilidades_clase_uno(
        modelo, textos
    )

    guardar_json(
        TEMP_CLASICO,
        {
            "sha_textos": [
                sha_texto(t) for t in textos
            ],
            "probabilidades": probabilidades
        }
    )

    print(
        "Detector clasico: 3 predicciones calculadas.",
        flush=True
    )


# ==========================================
# 5. PROCESO DEL DETECTOR SEMANTICO
# ==========================================

def trabajador_semantico():
    import torch

    torch.set_num_threads(1)

    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    from sentence_transformers import SentenceTransformer
    import joblib

    config = leer_json(CONFIG)
    textos = preparar_textos()

    print(
        "Cargando MiniLM en CPU...",
        flush=True
    )

    encoder = SentenceTransformer(
        config["modelo_encoder"],
        revision=config["revision"],
        device="cpu"
    )

    print(
        "Encoder cargado. Calculando tokens...",
        flush=True
    )

    limite = int(
        encoder.get_max_seq_length()
    )

    tokenizer = encoder._first_module().tokenizer

    longitudes = [
        len(
            tokenizer.encode(
                t,
                add_special_tokens=True,
                truncation=False
            )
        )
        for t in textos
    ]

    print(
        "Calculando embeddings de 3 frases...",
        flush=True
    )

    embeddings = encoder.encode(
        textos,
        batch_size=1,
        show_progress_bar=False,
        convert_to_numpy=True
    )

    print(
        "Embeddings calculados. Cargando clasificador...",
        flush=True
    )

    modelo = joblib.load(SEMANTICO)

    probabilidades = probabilidades_clase_uno(
        modelo,
        embeddings
    )

    guardar_json(
        TEMP_SEMANTICO,
        {
            "sha_textos": [
                sha_texto(t) for t in textos
            ],
            "probabilidades": probabilidades,
            "tokens": longitudes,
            "limite_tokens": limite
        }
    )

    print(
        "Detector semantico: 3 predicciones calculadas.",
        flush=True
    )


# ==========================================
# 6. EJECUTAR PROCESOS INDEPENDIENTES
# ==========================================

def ejecutar_trabajador(nombre):
    registrar(
        "Iniciando proceso: " + nombre
    )

    comando = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--worker",
        nombre
    ]

    entorno = os.environ.copy()

    proceso = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
        env=entorno,
        cwd=str(BASE)
    )

    if proceso.stdout is not None:
        for linea in proceso.stdout:
            mensaje = linea.rstrip("\n")

            registrar(
                nombre + " | " + mensaje
            )

    codigo = proceso.wait()

    registrar(
        f"Proceso {nombre}: codigo de salida {codigo}"
    )

    if codigo != 0:
        raise RuntimeError(
            f"Fallo el proceso {nombre}. "
            f"Codigo de salida: {codigo}. "
            f"Consulta {BITACORA.name}."
        )


# ==========================================
# 7. PROGRAMA PRINCIPAL
# ==========================================

def principal():
    EVIDENCIAS.mkdir(
        parents=True,
        exist_ok=True
    )

    if FINAL_JSON.exists() or FINAL_TXT.exists():
        raise SystemExit(
            "T33 ya tiene resultados finales. "
            "No se sobrescribieron."
        )

    BITACORA.write_text(
        "T33 - Diagnostico por procesos\n",
        encoding="utf-8"
    )

    registrar(
        "Comenzando T33 - inferencia V2"
    )

    requeridos = [
        INVENTARIO,
        CONFIG,
        CLASICO,
        SEMANTICO
    ]

    for ruta in requeridos:
        if not ruta.is_file():
            raise RuntimeError(
                "No existe el archivo: " + str(ruta)
            )

    inventario = leer_json(INVENTARIO)
    config = leer_json(CONFIG)

    if config.get("neutralizacion") != "neutralizacion_v2.py":
        raise RuntimeError(
            "La configuracion no corresponde a V2"
        )

    if config.get("modelo_clasificador") != SEMANTICO.name:
        raise RuntimeError(
            "Nombre de clasificador semantico diferente"
        )

    if not config.get("modelo_encoder"):
        raise RuntimeError(
            "Falta el nombre del encoder"
        )

    if not config.get("revision"):
        raise RuntimeError(
            "Falta la revision del encoder"
        )

    if float(config.get("umbral", -1)) != 0.5:
        raise RuntimeError(
            "Umbral distinto de 0.5"
        )

    # Verificar integridad antes de inferencia
    hashes = {}

    for ruta in [CLASICO, SEMANTICO]:
        actual = sha_archivo(ruta)

        esperado = inventario.get(
            "modelos", {}
        ).get(ruta.name)

        if actual != esperado or not esperado:
            raise RuntimeError(
                "Integridad SHA-256 incorrecta: "
                + ruta.name
            )

        hashes[ruta.name] = actual

    registrar(
        "Integridad inicial de ambos modelos: verificada"
    )

    # Eliminar solo resultados temporales de intentos anteriores
    for temporal in [
        TEMP_CLASICO,
        TEMP_SEMANTICO
    ]:
        if temporal.exists():
            temporal.unlink()

    # Ejecutar clasificador clasico
    ejecutar_trabajador("clasico")

    if not TEMP_CLASICO.is_file():
        raise RuntimeError(
            "El detector clasico no genero resultados"
        )

    # Ejecutar clasificador semantico
    ejecutar_trabajador("semantico")

    if not TEMP_SEMANTICO.is_file():
        raise RuntimeError(
            "El detector semantico no genero resultados"
        )

    a = leer_json(TEMP_CLASICO)
    b = leer_json(TEMP_SEMANTICO)

    if a["sha_textos"] != b["sha_textos"]:
        raise RuntimeError(
            "Los clasificadores recibieron textos diferentes"
        )

    # Consolidar resultados
    resultados = []

    for i, (ident, texto) in enumerate(CONTROLES):
        pc = float(
            a["probabilidades"][i]
        )

        ps = float(
            b["probabilidades"][i]
        )

        tokens = int(
            b["tokens"][i]
        )

        resultados.append({
            "id": ident,
            "sha256_original": sha_texto(texto),
            "sha256_neutralizado": a["sha_textos"][i],
            "tokens_semanticos": tokens,
            "supera_limite_encoder": (
                tokens > b["limite_tokens"]
            ),
            "probabilidad_clasico": round(pc, 6),
            "prediccion_clasico": int(pc >= 0.5),
            "probabilidad_semantico": round(ps, 6),
            "prediccion_semantico": int(ps >= 0.5)
        })

        registrar(
            f"{ident}: "
            f"clasico={pc:.4f}, "
            f"semantico={ps:.4f}, "
            f"tokens={tokens}"
        )

    # Comprobar que no cambiaron los modelos
    for ruta in [CLASICO, SEMANTICO]:
        if sha_archivo(ruta) != hashes[ruta.name]:
            raise RuntimeError(
                "Un modelo cambio durante la prueba"
            )

    # Registrar evidencia
    registro = {
        "fecha": datetime.now().astimezone().isoformat(),
        "tipo": "control_inferencia_con_frases_ficticias",
        "modelo_clasico": CLASICO.name,
        "modelo_semantico": SEMANTICO.name,
        "encoder": config["modelo_encoder"],
        "revision_encoder": config["revision"],
        "umbral": 0.5,
        "limite_tokens": int(b["limite_tokens"]),
        "hashes_modelos": hashes,
        "resultados": resultados,
        "entrenamiento": "NO EJECUTADO",
        "prueba_final": "NO UTILIZADA",
        "equivalencia_v2_v3": "NO DEMOSTRADA"
    }

    reporte = "\n".join([
        "T33 - CONTROL DE INFERENCIA V2",
        "================================",
        "Controles sinteticos: 3",
        "Ambos detectores recibieron el mismo texto V2.",
        "Modelos SHA-256: SIN CAMBIOS.",
        "Entrenamiento: NO EJECUTADO.",
        "Prueba final: NO UTILIZADA.",
        "Equivalencia V2/V3: NO DEMOSTRADA.",
        "T33 FINALIZADO."
    ])

    guardar_json(
        FINAL_JSON,
        registro
    )

    FINAL_TXT.write_text(
        reporte,
        encoding="utf-8"
    )

    registrar(
        "T33 FINALIZADO"
    )

    print(
        "\n" + reporte,
        flush=True
    )

    print(
        "Evidencias:",
        FINAL_JSON,
        FINAL_TXT,
        sep="\n",
        flush=True
    )


# ==========================================
# 8. PUNTO DE ENTRADA
# ==========================================

if __name__ == "__main__":
    try:
        if (
            len(sys.argv) == 3
            and sys.argv[1] == "--worker"
        ):
            if sys.argv[2] == "clasico":
                trabajador_clasico()

            elif sys.argv[2] == "semantico":
                trabajador_semantico()

            else:
                raise ValueError(
                    "Trabajador desconocido"
                )
        else:
            principal()

    except Exception as exc:
        print(
            "ERROR T33:",
            str(exc),
            file=sys.stderr,
            flush=True
        )
        raise

