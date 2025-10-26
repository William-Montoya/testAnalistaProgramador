# Reporte de faltantes por cliente (Tarea 3)
#
# Carga pedidos, inventario y la última recepción, hace asignación FIFO por SKU
# y genera un CSV con los faltantes por cliente. Usa regex precompilada.

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Dict, List

import pandas as pd
import re

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent
PEDIDOS_FILE = BASE_DIR / "data" / "pedidos.csv"
INVENTARIO_FILE = BASE_DIR / "data" / "inventario.csv"
RECEPCIONES_DIR = BASE_DIR / "data" / "recepciones"
REPORTES_DIR = BASE_DIR / "data" / "reportes"

# Regex precompilada para extraer número del identificador de pedido
RE_NUM = re.compile(r"(\d+)")


def _norm_col_name(name: str) -> str:
    # Normaliza un nombre de columna: minúsculas, sin separadores y sin acentos
    s = str(name or "").strip().lower()
    # quitar acentos comunes
    s = (
        s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
         .replace("ä", "a").replace("ë", "e").replace("ï", "i").replace("ö", "o").replace("ü", "u")
         .replace("ñ", "n")
    )
    # quitar separadores
    for ch in (" ", "_", "-", "/", "\\"):
        s = s.replace(ch, "")
    return s


def _detectar_columna_sku_inventario(inv: pd.DataFrame) -> str | None:
    # Detecta la columna de SKU/código de producto en inventario con heurísticas
    # Prioridad: 'sku' > 'producto' > 'cod' y 'prod' > equivalentes comunes
    if not len(inv.columns):
        return None

    # Mapa normalizado -> original
    mapping = { _norm_col_name(c): c for c in inv.columns }

    # 1) 'sku' explícito
    for norm, orig in mapping.items():
        if "sku" in norm:
            return orig

    # 2) 'producto' (algunas bases usan nombre del producto como clave)
    for norm, orig in mapping.items():
        if "producto" in norm:
            return orig

    # 3) Combinación 'cod' y 'prod'
    for norm, orig in mapping.items():
        if ("cod" in norm and "prod" in norm):
            return orig

    # 4) Equivalentes conocidos
    candidatos_exactos = [
        "codigo", "codigoproducto", "idproducto", "idprod", "referencia", "item",
    ]
    for cand in candidatos_exactos:
        if cand in mapping:
            return mapping[cand]

    return None

# === LECTURA DE DATOS ===
def _detectar_columna_orden(df: pd.DataFrame) -> str | None:
    # Detecta la columna que representa el número/identificador del pedido.
    # Acepta nombres comunes de exports (Shopify y similares): 'Name' ('#1001'),
    # 'Order Number', 'Order ID', 'Order', 'Número de pedido', etc.
    candidatos = [
        "Name",
        "Order Number",
        "Order number",
        "Order ID",
        "Order Id",
        "Order",
        "Numero de pedido",
        "Número de pedido",
        "Order Name",
    ]
    lc = {c.lower(): c for c in df.columns}
    for cand in candidatos:
        if cand.lower() in lc:
            return lc[cand.lower()]
    return None

def _normalizar_id_pedido(valor) -> str:
    # Extrae un identificador comparable del pedido. Ej: '#1001' -> '1001'.
    s = str(valor or "").strip()
    m = RE_NUM.search(s)
    return m.group(1) if m else s

def cargar_pedidos() -> pd.DataFrame:
    df = pd.read_csv(PEDIDOS_FILE, sep=";")
    df.columns = [str(c).strip() for c in df.columns]
    rename = {
        "Lineitem sku": "SKU",
        "Lineitem name": "Producto",
        "Lineitem quantity": "Cantidad",
        "Billing Name": "Cliente",
    }
    for k, v in rename.items():
        if k in df.columns and v not in df.columns:
            df.rename(columns={k: v}, inplace=True)

    # columnas mínimas
    for col in ["SKU", "Producto", "Cantidad", "Cliente"]:
        if col not in df.columns:
            raise KeyError(f"La columna '{col}' no existe en pedidos.csv")

    # Aseguramos tipos
    df["Cantidad"] = pd.to_numeric(df["Cantidad"], errors="coerce").fillna(0).astype(int)

    # Índice de orden para priorizar FIFO según el orden del CSV
    df["Orden"] = range(len(df))

    # Asociar NOMBRE COMPLETO del cliente por número de pedido
    col_orden = _detectar_columna_orden(df)
    if col_orden:
        df["OrderId"] = df[col_orden].apply(_normalizar_id_pedido)

        # Determinar el NOMBRE COMPLETO por fila, priorizando columnas específicas
        nombre_completo = None
        if "Billing First Name" in df.columns or "Billing Last Name" in df.columns:
            f = df.get("Billing First Name", "").astype(str).str.strip()
            l = df.get("Billing Last Name", "").astype(str).str.strip()
            nombre_completo = (f + " " + l).str.strip()
        elif "Shipping First Name" in df.columns or "Shipping Last Name" in df.columns:
            f = df.get("Shipping First Name", "").astype(str).str.strip()
            l = df.get("Shipping Last Name", "").astype(str).str.strip()
            nombre_completo = (f + " " + l).str.strip()
        elif "Shipping Name" in df.columns:
            nombre_completo = df["Shipping Name"].astype(str).str.strip()
        else:
            # Ya renombramos 'Billing Name' -> 'Cliente' antes; úsalo tal cual (nombre completo)
            nombre_completo = df["Cliente"].astype(str).str.strip()

        df["NombreCompleto"] = nombre_completo

        # Elegir el nombre correspondiente a la primera aparición del pedido (menor Orden)
        idx_primera_aparicion = df.groupby("OrderId")["Orden"].idxmin()
        mapeo = (
            df.loc[idx_primera_aparicion, ["OrderId", "NombreCompleto"]]
            .set_index("OrderId")["NombreCompleto"]
            .to_dict()
        )
        # Sobrescribir 'Cliente' con el nombre completo del pedido
        df["Cliente"] = df["OrderId"].map(mapeo).fillna(df["Cliente"].astype(str).str.strip())

    return df


def cargar_inventario() -> pd.DataFrame:
    inv = pd.read_csv(INVENTARIO_FILE, sep=";")
    inv.columns = [str(c).strip() for c in inv.columns]

    # Determinar columna SKU/código usando heurística flexible
    sku_col = _detectar_columna_sku_inventario(inv)
    if not sku_col:
        cols = ", ".join(map(str, inv.columns))
        raise KeyError(
            "No se encontró columna de SKU en inventario. Esperado una columna que contenga "
            "'SKU', 'Producto' o algún 'Código de producto' (p. ej., CODPRODUCTO). "
            f"Columnas disponibles: {cols}"
        )

    # Normalizar
    if "Existencias" not in inv.columns:
        # Intento de nombre alternativo
        alt = [c for c in inv.columns if "existencia" in c.lower()]
        if alt:
            inv.rename(columns={alt[0]: "Existencias"}, inplace=True)
        else:
            raise KeyError("'Existencias' no encontrada en inventario.csv")

    inv = inv[[sku_col, "Existencias"]].copy()
    inv.rename(columns={sku_col: "SKU"}, inplace=True)
    inv["Existencias"] = pd.to_numeric(inv["Existencias"], errors="coerce").fillna(0).astype(int)
    return inv


def cargar_ultima_recepcion() -> pd.DataFrame:
    if not RECEPCIONES_DIR.exists():
        raise FileNotFoundError(
            "Ejecuta primero la recepción de mercadería."
        )

    archivos = sorted(RECEPCIONES_DIR.glob("recepcion_*.csv"))
    if not archivos:
        raise FileNotFoundError(
            "Aún no existe el Excel de recepción de mercaderías. Ejecuta la Tarea 2."
        )

    ultimo = archivos[-1]
    df = pd.read_csv(ultimo, sep=";")
    df.columns = [str(c).strip() for c in df.columns]

    # columnas mínimas requeridas
    for col in ["SKU", "Recibido"]:
        if col not in df.columns:
            raise KeyError(
                f"La recepción '{ultimo.name}' no contiene la columna requerida '{col}'."
            )

    df["Recibido"] = pd.to_numeric(df["Recibido"], errors="coerce").fillna(0).astype(int)
    return df


# Asignación de stock a pedidos (FIFO)
def asignar_stock_por_sku(
    pedidos: pd.DataFrame, disponible_por_sku: Dict[str, int]
) -> pd.DataFrame:
    # Distribuye el stock disponible (Existencias + Recibido) entre los pedidos de clientes
    # en orden FIFO (orden natural del CSV) por cada SKU.
    # Devuelve un DataFrame con columnas: Cliente, SKU, Producto, Cantidad_Pedida, Asignado, FaltanteCliente.

    # Orden estable por SKU
    pedidos_sorted = pedidos.sort_values(["SKU", "Orden"], kind="mergesort")

    registros: List[Dict] = []
    for sku, grupo in pedidos_sorted.groupby("SKU", sort=False):
        disponible = int(disponible_por_sku.get(sku, 0))
        for _, row in grupo.iterrows():
            cant = int(row["Cantidad"])
            asignado = min(cant, max(0, disponible))
            faltante = max(0, cant - asignado)
            disponible -= asignado

            registros.append(
                {
                    "Cliente": row["Cliente"],
                    "SKU": sku,
                    "Producto": row["Producto"],
                    "Cantidad_Pedida": cant,
                    "Asignado": int(asignado),
                    "FaltanteCliente": int(faltante),
                }
            )

    return pd.DataFrame(registros)


def generar_reporte() -> Path:
    # Datos base
    pedidos = cargar_pedidos()
    inventario = cargar_inventario()
    recepcion = cargar_ultima_recepcion()

    # Stock disponible por SKU = Existencias + Recibido
    recibido_por_sku = recepcion.groupby("SKU", as_index=False)["Recibido"].sum()
    base = (
        inventario.merge(recibido_por_sku, on="SKU", how="left")
        .fillna({"Recibido": 0})
    )
    base["Disponible"] = base["Existencias"] + base["Recibido"]

    disponible_por_sku: Dict[str, int] = {
        str(r.SKU): int(r.Disponible) for r in base[["SKU", "Disponible"]].itertuples(index=False)
    }

    asignaciones = asignar_stock_por_sku(pedidos, disponible_por_sku)

    # Solo faltantes de clientes
    faltantes_clientes = asignaciones[asignaciones["FaltanteCliente"] > 0].copy()

    # Orden amigable: por Cliente, luego por SKU
    faltantes_clientes.sort_values(["Cliente", "SKU"], inplace=True)

    # Guardar
    REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = REPORTES_DIR / f"faltantes_por_cliente_{ts}.csv"
    faltantes_clientes.to_csv(out_csv, sep=";", index=False)
    
    return out_csv


