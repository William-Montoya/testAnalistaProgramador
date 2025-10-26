# Generación de ordenes a proveedor (Tarea 1)
#
# Funciones puras para cargar datos, preparar agregados, calcular faltantes y
# guardar el reporte. Evitamos cambios de estructura y mantenemos los mismos
# paths/salida para no romper usos existentes.

from pathlib import Path
from typing import List
import re

import pandas as pd

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
PEDIDOS_FILE = BASE_DIR / "data" / "pedidos.csv"
INVENTARIO_FILE = BASE_DIR / "data" / "inventario.csv"
OUTPUT_DIR = BASE_DIR / "data" / "ordenesc"
OUTPUT_FILE = OUTPUT_DIR / "ordenes_proveedor.xlsx"

# Columnas esperadas
COLS_PEDIDOS_REQUERIDAS: List[str] = [
    "Lineitem sku",
    "Lineitem name",
    "Vendor",
    "Lineitem quantity",
]

def _normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    # Limpia espacios en los encabezados y devuelve el DataFrame
    df.columns = [str(c).strip() for c in df.columns]
    return df

def cargar_datos() -> tuple[pd.DataFrame, pd.DataFrame]:
    # Carga archivos base y normaliza encabezados en ambos DataFrames
    pedidos = pd.read_csv(PEDIDOS_FILE, sep=";")
    inventario = pd.read_csv(INVENTARIO_FILE, sep=";")
    _normalizar_columnas(pedidos)
    _normalizar_columnas(inventario)
    return pedidos, inventario

def preparar_agrupado_pedidos(pedidos: pd.DataFrame) -> pd.DataFrame:
    # Valida columnas en pedidos y agrupa cantidades por SKU/Producto/Proveedor
    faltantes = [c for c in COLS_PEDIDOS_REQUERIDAS if c not in pedidos.columns]
    if faltantes:
        raise KeyError(f"Faltan columnas en pedidos.csv: {faltantes}")

    # Agrupar por SKU, nombre y proveedor
    agrupado = (
        pedidos.groupby(["Lineitem sku", "Lineitem name", "Vendor"], as_index=False)
        .agg({"Lineitem quantity": "sum"})
    )

    # Renombrar a nombres consistentes
    agrupado.rename(
        columns={
            "Lineitem sku": "SKU",
            "Lineitem name": "Producto",
            "Vendor": "Proveedor",
            "Lineitem quantity": "Cantidad_Pedida",
        },
        inplace=True,
    )
    return agrupado


def detectar_columna_inventario_sku(inventario: pd.DataFrame) -> str:
    # Determina la columna en inventario para cruzar con el SKU de pedidos
    if "SKU" in inventario.columns:
        return "SKU"
    if "Producto" in inventario.columns:
        return "Producto"
    raise KeyError("El inventario no contiene columna 'SKU' ni 'Producto' para realizar el cruce.")


def calcular_faltantes(agrupado: pd.DataFrame, inventario: pd.DataFrame) -> pd.DataFrame:
    # Cruza con inventario para obtener existencias actuales y calcula faltantes
    # Retorna únicamente filas con faltante > 0
    inv_key = detectar_columna_inventario_sku(inventario)
    inv_cols: List[str] = [inv_key, "Existencias"]
    if "Vendor" in inventario.columns:
        inv_cols.append("Vendor")
    inventario_sel = inventario[inv_cols].copy()

    req = pd.merge(
        agrupado,
        inventario_sel,
        left_on="SKU",
        right_on=inv_key,
        how="left",
        suffixes=("", "_inv"),
    )

    req["Existencias"] = pd.to_numeric(req.get("Existencias"), errors="coerce").fillna(0).astype(int)

    req["Faltante"] = (req["Cantidad_Pedida"] - req["Existencias"]).clip(lower=0)

    faltantes = req[req["Faltante"] > 0].copy()
    return faltantes


def adjuntar_clientes(pedidos: pd.DataFrame, faltantes: pd.DataFrame) -> pd.DataFrame:
    # Añade lista de clientes (únicos) que solicitaron cada SKU si existen columnas
    if "Billing Name" not in pedidos.columns or "Lineitem sku" not in pedidos.columns:
        return faltantes

    clientes = (
        pedidos.groupby("Lineitem sku")["Billing Name"].unique().reset_index()
        .rename(columns={"Lineitem sku": "SKU", "Billing Name": "Clientes"})
    )
    return faltantes.merge(clientes, on="SKU", how="left")


def guardar_reporte(faltantes: pd.DataFrame) -> Path:
    # Crea carpeta de salida y escribe el Excel con la hoja Ordenes_Proveedor
    # Exporta columnas: SKU, PRODUCTO, PROVEEDOR y CANTIDADAPEIDIR (renombrada desde 'Faltante')
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = faltantes.copy()
    # Construir el DataFrame de salida con las 3 columnas solicitadas
    out_cols = {}
    out_cols["SKU"] = df["SKU"]
    # Producto en mayúsculas por consistencia con PROVEEDOR
    if "Producto" in df.columns:
        out_cols["PRODUCTO"] = df["Producto"]
    else:
        out_cols["PRODUCTO"] = ""
    # Proveedor en mayúsculas según requerimiento
    if "Proveedor" in df.columns:
        out_cols["PROVEEDOR"] = df["Proveedor"]
    else:
        # Si no existe, exportar columna vacía para mantener estructura
        out_cols["PROVEEDOR"] = ""
    # Renombrar Faltante -> CANTIDADAPEIDIR
    out_cols["CANTIDADAPEIDIR"] = df["Faltante"].astype(int)

    df_out = pd.DataFrame(out_cols, columns=["SKU", "PRODUCTO", "PROVEEDOR", "CANTIDADAPEIDIR"])

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        # Hoja general (compatibilidad con Tarea 2): ordenada por PROVEEDOR y SKU
        df_general = df_out
        if "PROVEEDOR" in df_general.columns:
            df_general = df_general.sort_values(["PROVEEDOR", "SKU"], kind="mergesort")
        df_general.to_excel(writer, index=False, sheet_name="Ordenes_Proveedor")

        # Hojas por PROVEEDOR (agrupado)
        if "PROVEEDOR" in df_out.columns:
            # Ordenar por PROVEEDOR y SKU para lectura más cómoda
            df_sorted = df_out.sort_values(["PROVEEDOR", "SKU"], kind="mergesort")

            def sanitize_sheet(name: str) -> str:
                # Reglas de Excel: máx 31 chars, no : \ / ? * [ ]
                cleaned = re.sub(r"[:\\/\?\*\[\]]", " ", str(name or "Proveedor"))
                cleaned = cleaned.strip().strip("'")  # sin comillas al borde
                return (cleaned or "Proveedor")[:31]

            used_names = set(["Ordenes_Proveedor"])  # evitar colisión
            for prov in df_sorted["PROVEEDOR"].dropna().astype(str).unique():
                sheet = sanitize_sheet(prov)
                base = sheet
                i = 1
                while sheet in used_names:
                    suffix = f"_{i}"
                    sheet = (base[: max(0, 31 - len(suffix))] + suffix) or f"Prov_{i}"
                    i += 1
                used_names.add(sheet)

                df_prov = df_sorted[df_sorted["PROVEEDOR"] == prov]
                df_prov.to_excel(writer, index=False, sheet_name=sheet)
    return OUTPUT_FILE

