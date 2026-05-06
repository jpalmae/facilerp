"""Constantes centralizadas para FacilERP.

Evita strings mágicos dispersos por el código y facilita buscar usos.
"""

from __future__ import annotations


# ── MovimientoStock.tipo ──────────────────────────────────────────────────────
MOV_ENTRADA = "entrada"
MOV_SALIDA = "salida"
MOV_RECEPCION_COMPRA = "recepcion_compra"
MOV_AJUSTE_ENTRADA = "ajuste_entrada"
MOV_AJUSTE_SALIDA = "ajuste_salida"

MOVEMENT_TYPES: tuple[str, ...] = (
    MOV_ENTRADA,
    MOV_SALIDA,
    MOV_RECEPCION_COMPRA,
    MOV_AJUSTE_ENTRADA,
    MOV_AJUSTE_SALIDA,
)

# ── referencia_tipo (movimientos, asientos, tesorería) ────────────────────────
REF_PEDIDO_VENTA = "pedido_venta"
REF_ORDEN_COMPRA = "orden_compra"
REF_RECEPCION_COMPRA = "recepcion_compra"
REF_DOCUMENTO_CXC = "documento_cxc"
REF_DOCUMENTO_CXP = "documento_cxp"
REF_TRANSFERENCIA_TESORERIA = "transferencia_tesoreria"
REF_REVERSION_ASIENTO = "reversion_asiento"
