from pathlib import Path
from datetime import datetime
import sys
 

import pandas as pd
import streamlit as st


# Rutas base
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ORDENES_DIR = DATA_DIR / "ordenesc"
RECEPCIONES_DIR = DATA_DIR / "recepciones"
REPORTES_DIR = DATA_DIR / "reportes"
ORDENES_XLSX = ORDENES_DIR / "ordenes_proveedor.xlsx"

# Habilitar import de los módulos del proyecto
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import generar_ordenes  # type: ignore
import reporte_faltantes_por_cliente  # type: ignore


st.set_page_config(
    page_title="Cinco Azul - Órdenes y Recepción",
    page_icon="📦",
    layout="wide",
)

# Ocultar menú/botón superior derecho (menú 3 puntos), botón Deploy, toolbar y footer
st.markdown(
    """
    <style>
    .stDeployButton {display: none !important;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Mantener visible la toolbar para que el botón de mostrar/ocultar sidebar siga disponible */
    </style>
    """,
    unsafe_allow_html=True,
)
 

st.sidebar.title("Menú")
page = st.sidebar.radio(
    "",
    [
        "Tarea 1 · Orden al proveedor",
        "Tarea 2 · Recepción de mercadería",
        "Tarea 3 · Faltantes por cliente",
    ],
    key="nav",
)


def load_ordenes_df() -> pd.DataFrame:
    # Carga el Excel de órdenes del proveedor y devuelve un DataFrame.
    # Muestra advertencias/errores en la UI y devuelve un DataFrame vacío si hay problemas.
    if not ORDENES_XLSX.exists():
        st.warning("Aún no existe el Excel de órdenes. Ejecuta la Tarea 1.")
        return pd.DataFrame()
    try:
        return pd.read_excel(ORDENES_XLSX, sheet_name="Ordenes_Proveedor")
    except Exception as e:
        st.error(f"No se pudo leer {ORDENES_XLSX}: {e}")
        return pd.DataFrame()


def recepcion_ui() -> None:
    # Pantalla para capturar la recepción de mercadería con edición en línea.
    st.header("Tarea 2 · Recepción de mercadería")
    df = load_ordenes_df()
    if df.empty:
        st.stop()

    # Normalizar columnas esperadas
    df.columns = [str(c).strip() for c in df.columns]

    # Detectar columna de cantidad a pedir
    qty_col = None
    for c in [
        "Faltante",
        "CANTIDADAPEIDIR",
        "CANTIDADAPEDIR",
        "Cantidad_Ordenada",
        "Cantidad_Pedida",
        "Cantidad a pedir",
        "A_Ordenar",
    ]:
        if c in df.columns:
            qty_col = c
            break
    if qty_col is None:
        st.error("No se encontró una columna de cantidad ordenada (Faltante/CANTIDADAPEIDIR/...).")
        st.stop()

    st.write("Vista previa del pedido al proveedor y captura de recepción:")
    # Detectar columnas visibles
    proveedor_col = "Proveedor" if "Proveedor" in df.columns else ("PROVEEDOR" if "PROVEEDOR" in df.columns else None)
    producto_col = "Producto" if "Producto" in df.columns else ("PRODUCTO" if "PRODUCTO" in df.columns else None)
    preview_cols = ["SKU"]
    if proveedor_col:
        preview_cols.append(proveedor_col)
    if producto_col:
        preview_cols.append(producto_col)
    if qty_col and qty_col not in preview_cols:
        preview_cols.append(qty_col)

    # Construir DataFrame editable junto a la cantidad a pedir
    edit_df = df[preview_cols].copy()
    if "Recibido" not in edit_df.columns:
        edit_df["Recibido"] = 0

    from streamlit import column_config as cc
    column_cfg = {
        "SKU": cc.TextColumn("SKU", disabled=True),
        qty_col: cc.NumberColumn(qty_col, disabled=True, step=1, format="%d"),
        "Recibido": cc.NumberColumn("Recibido (editable)", min_value=0, step=1, format="%d", help="Ingrese la cantidad recibida"),
    }
    if proveedor_col:
        column_cfg[proveedor_col] = cc.TextColumn(proveedor_col, disabled=True)
    if producto_col:
        column_cfg[producto_col] = cc.TextColumn(producto_col, disabled=True)

    edited = st.data_editor(
        edit_df,
        column_config=column_cfg,
        key="editor_recepcion",
    )

    if st.button("Guardar recepción", key="save_recepcion"):
        registros = []
        # 'edited' conserva el índice original de df; lo usamos para completar datos auxiliares
        for idx, row in edited.iterrows():
            base = df.loc[idx]
            sku = row.get("SKU", base.get("SKU", "-"))
            prod = base.get("Producto", base.get("PRODUCTO", "-"))
            prov = base.get("Proveedor", base.get("PROVEEDOR", "-"))
            pedido = int(pd.to_numeric(row.get(qty_col, 0), errors="coerce") or 0)
            recibido = int(pd.to_numeric(row.get("Recibido", 0), errors="coerce") or 0)
            falt = max(0, pedido - recibido)
            exc = max(0, recibido - pedido)
            estado = "Exceso" if exc > 0 else ("Incompleto" if falt > 0 else "Completo")
            registros.append(
                {
                    "SKU": sku,
                    "Producto": prod,
                    "Proveedor": prov,
                    "Cantidad_Ordenada": pedido,
                    "Recibido": recibido,
                    "FaltanteEntrega": falt,
                    "Exceso": exc,
                    "Estado": estado,
                }
            )

        out_df = pd.DataFrame(registros)
        RECEPCIONES_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = RECEPCIONES_DIR / f"recepcion_{ts}.csv"
        out_df.to_csv(out_csv, sep=";", index=False)

        st.success(f"Recepción guardada: {out_csv}")

        st.write("Resumen:")
        total = len(out_df)
        incompletos = (out_df["FaltanteEntrega"] > 0).sum()
        completos = (out_df["Estado"] == "Completo").sum()
        excesos = (out_df["Exceso"] > 0).sum()
        st.write(f"Líneas: {total} · Completos: {completos} · Incompletos: {incompletos} · Exceso: {excesos}")
        if incompletos:
            st.write("Faltantes:")
            # Mostrar faltantes incluyendo nombre del producto
            cols_falt = [
                c for c in ["SKU", "Producto", "PRODUCTO", "Cantidad_Ordenada", "Recibido", "FaltanteEntrega"]
                if c in out_df.columns
            ]
            st.dataframe(out_df[out_df["FaltanteEntrega"] > 0][cols_falt], width="stretch")


if page.startswith("Tarea 1"):
    st.header("Tarea 1 · Generar orden al proveedor")
    st.write("Genera el Excel con la cantidad a pedir por SKU (CODPRODUCTO) y proveedor.")
    if st.button("Generar orden"):
        try:
            pedidos, inventario = generar_ordenes.cargar_datos()
            agrupado = generar_ordenes.preparar_agrupado_pedidos(pedidos)
            faltantes = generar_ordenes.calcular_faltantes(agrupado, inventario)
            faltantes = generar_ordenes.adjuntar_clientes(pedidos, faltantes)
            out_path = generar_ordenes.guardar_reporte(faltantes)
            st.success(f"Orden generada en {out_path}")
        except Exception as e:
            st.error(f"Ocurrió un error al generar la orden: {e}")
    if ORDENES_XLSX.exists():
        st.subheader("Vista previa del Excel")
        df_prev = load_ordenes_df()
        if not df_prev.empty:
            st.dataframe(df_prev.head(100), width="stretch")

elif page.startswith("Tarea 2"):
    recepcion_ui()

else:
    st.header("Tarea 3 · Faltantes por cliente")
    st.write("Calcula faltantes por cliente usando la última recepción guardada.")
    if st.button("Generar reporte de faltantes por cliente"):
        try:
            out = reporte_faltantes_por_cliente.generar_reporte()
            st.success(f"Reporte generado: {out}")
            try:
                df = pd.read_csv(out, sep=";")
                st.dataframe(df.head(200), width="stretch")
            except Exception:
                st.info("El archivo es grande o contiene caracteres especiales; se generó correctamente.")
        except Exception as e:
            st.error(str(e))
