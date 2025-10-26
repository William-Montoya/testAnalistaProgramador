# Cinco Azul · Orden a proveedor, Recepción y Faltantes por Cliente (UI)

Este proyecto implementa 3 tareas encadenadas y orientadas a uso por interfaz gráfica (Streamlit):

1) Tarea 1 — Generar orden al proveedor
2) Tarea 2 — Recepción de mercadería
3) Tarea 3 — Reporte de faltantes por cliente

La lógica corre 100% desde la interfaz web; los puntos de entrada por consola (CLI) fueron retirados para simplificar el flujo.

## Estructura del proyecto

- `generar_ordenes.py` — Lógica para construir la orden por proveedor (columnas estrictas y hojas por proveedor).
- `recepcion_mercaderia.py` — Utilidades de lectura/escritura para la recepción (sin interacción por consola).
- `reporte_faltantes_por_cliente.py` — Genera CSV de faltantes por cliente con asignación FIFO.
- `ui/streamlit_app.py` — Interfaz Streamlit con las 3 tareas.
- `data/`
   - `pedidos.csv` — pedidos de clientes (separador `;`).
   - `inventario.csv` — existencias por producto (separador `;`).
   - `ordenesc/` — salida de Tarea 1: `ordenes_proveedor.xlsx`.
   - `recepciones/` — salidas de Tarea 2 (`recepcion_YYYYMMDD_HHMMSS.csv`).
   - `reportes/` — salidas de Tarea 3 (`faltantes_por_cliente_YYYYMMDD_HHMMSS.csv`).
- `requirements.txt` — dependencias (pandas, openpyxl, streamlit).

## Requisitos

- Python 3.10+ (recomendado)
- Windows PowerShell
- Dependencias del archivo `requirements.txt`

Instalación (PowerShell):

```powershell
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

## Uso (Interfaz gráfica)

1) Coloca tus archivos base en `data/` usando separador `;`:

- `data/pedidos.csv`: columnas mínimas esperadas:
   - `Lineitem sku`, `Lineitem name`, `Lineitem quantity`, `Billing Name`.
   - Opcionales para mapear nombre completo del cliente por pedido: `Name`, `Order Number`, `Order ID`, `Número de pedido`, etc.
- `data/inventario.csv`: columnas mínimas esperadas:
   - `Existencias` (numérica).
   - Una columna de código/SKU autodetectable: se aceptan variantes como `SKU`, `Producto`, `CODPRODUCTO`, `Codigo`, `Codigo Producto`, `IDProducto`, etc. Si no se detecta, el error te mostrará las columnas disponibles.

2) Ejecuta la app (PowerShell):

```powershell
streamlit run .\ui\streamlit_app.py
```

3) Flujo en la interfaz:

- Tarea 1 — Generar orden al proveedor
   - Lee `pedidos.csv` e `inventario.csv`.
   - Calcula faltantes y exporta `data/ordenesc/ordenes_proveedor.xlsx`.
   - Formato del Excel (hoja principal `Ordenes_Proveedor`): columnas exactas `SKU`, `PRODUCTO`, `PROVEEDOR`, `CANTIDADAPEIDIR`. La hoja está ordenada por `PROVEEDOR` y `SKU` y se generan hojas adicionales por proveedor.

- Tarea 2 — Recepción de mercadería
   - Muestra la orden en una tabla editable (columna “Recibido”).
   - Guarda `data/recepciones/recepcion_YYYYMMDD_HHMMSS.csv` con resumen de `Recibido`, `FaltanteEntrega`, `Exceso` y `Estado`.

- Tarea 3 — Faltantes por cliente
   - Usa stock disponible = `Existencias` + `Recibido` (última recepción).
   - Asigna FIFO por `SKU` y exporta `data/reportes/faltantes_por_cliente_YYYYMMDD_HHMMSS.csv`.

## Notas importantes

- Separador CSV: el proyecto lee y escribe con `;` (punto y coma), habitual en configuraciones regionales de Excel en Windows.
- Detección de columnas (robusta):
   - En inventario, la columna de código/SKU se detecta heurísticamente (admite múltiples nombres). Si falla, el mensaje de error incluye la lista de columnas encontradas.
   - En pedidos, si existe un identificador de pedido, se mapea el “Nombre completo” del cliente por pedido.
- Excel de Tarea 1:
   - Hojas por proveedor además de la principal; los nombres de hoja se sanitizan para cumplir reglas de Excel.
- Sin consola: se retiraron los scripts interactivos por CLI. Todo se ejecuta desde la interfaz Streamlit.

## Solución de problemas

- “No se encontró columna de SKU en inventario”: revisa el encabezado de `inventario.csv` y renómbralo a alguna de las variantes aceptadas (`SKU`, `Producto`, `CODPRODUCTO`, `Codigo`, etc.). El error mostrará las columnas detectadas.
- El Excel no se puede escribir: cierra `data/ordenesc/ordenes_proveedor.xlsx` si está abierto en Excel y vuelve a generar.
- Columnas faltantes en `pedidos.csv`: agrega las columnas mínimas (`Lineitem sku`, `Lineitem name`, `Lineitem quantity`, `Billing Name`).
