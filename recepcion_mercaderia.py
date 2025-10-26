# Recepción de mercadería (utilidades para Tarea 2)
#
# Este módulo conserva utilidades de lectura/escritura para apoyar la UI.
# Se eliminan las funciones de interacción por consola.

from pathlib import Path
from datetime import datetime
from typing import List

import pandas as pd


# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
ORDENES_XLSX = BASE_DIR / "data" / "ordenesc" / "ordenes_proveedor.xlsx"
RECEPCIONES_DIR = BASE_DIR / "data" / "recepciones"


def _guess_qty_column(df: pd.DataFrame) -> str:
    # Detecta la columna de cantidad ordenada al proveedor.
    # Priorizamos 'Faltante' generado por generar_ordenes.py
    candidatos: List[str] = [
        "Faltante",
        "CANTIDADAPEIDIR",
        "Cantidad_Ordenada",
        "Cantidad a pedir",
        "A_Ordenar",
        "Cantidad_Pedida_Proveedor",
    ]

    for col in candidatos:
        if col in df.columns:
            return col

    # Respaldo: si no existe ninguna, intentamos con 'Cantidad_Pedida'
    if "Cantidad_Pedida" in df.columns:
        return "Cantidad_Pedida"

    raise KeyError(
        "No se encontró una columna de cantidad ordenada en el reporte. "
        "Revisa que el archivo 'ordenes_proveedor.xlsx' contenga una de estas columnas: "
        "Faltante, Cantidad_Ordenada, 'Cantidad a pedir', A_Ordenar, Cantidad_Pedida_Proveedor, Cantidad_Pedida."
    )


def cargar_reporte_ordenes(sheet: str = "Ordenes_Proveedor") -> pd.DataFrame:
    # Carga el Excel de órdenes y devuelve un DataFrame listo para recepción.
    # Requiere columnas al menos: SKU, Producto y la cantidad ordenada (detectada).
    if not ORDENES_XLSX.exists():
        raise FileNotFoundError(
            f"No se encontró {ORDENES_XLSX}. Ejecuta primero 'generar_ordenes.py' para crear el reporte."
        )

    df = pd.read_excel(ORDENES_XLSX, sheet_name=sheet)

    # Normalizamos encabezados y quitamos espacios
    df.columns = [str(c).strip() for c in df.columns]

    # Algunas salidas pueden traer columnas duplicadas del merge; limpiamos si aplica
    # Preferimos columnas clave estándar si existen
    rename_map = {
        "Lineitem sku": "SKU",
        "Lineitem name": "Producto",
        "Vendor": "Proveedor",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df.rename(columns={k: v}, inplace=True)

    # Garantizamos columnas mínimas
    for required in ["SKU", "Producto"]:
        if required not in df.columns:
            # Algunos reportes pueden tener 'Producto_x' o nombres similares; hacemos un mejor esfuerzo
            similares = [c for c in df.columns if required in str(c)]
            if similares:
                df.rename(columns={similares[0]: required}, inplace=True)
            else:
                raise KeyError(f"No se encontró la columna requerida '{required}' en el reporte.")

    qty_col = _guess_qty_column(df)
    # Normalizamos nombre interno
    if qty_col != "Cantidad_Ordenada":
        df.rename(columns={qty_col: "Cantidad_Ordenada"}, inplace=True)

    # Limpieza básica de nulos
    df["Cantidad_Ordenada"] = pd.to_numeric(df["Cantidad_Ordenada"], errors="coerce").fillna(0).astype(int)

    # Solo nos quedamos con columnas relevantes + las que el usuario pudiera querer ver
    cols_prior = [c for c in ["SKU", "Producto", "Proveedor", "Cantidad_Ordenada"] if c in df.columns]
    # Preservamos otras informativas si existen (Clientes, Existencias, etc.) para el reporte final
    other_cols = [c for c in df.columns if c not in cols_prior]
    return df[cols_prior + other_cols]


def guardar_reporte(recepcion_df: pd.DataFrame) -> Path:
    RECEPCIONES_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = RECEPCIONES_DIR / f"recepcion_{ts}.csv"
    recepcion_df.to_csv(out_csv, sep=";", index=False)
    return out_csv

