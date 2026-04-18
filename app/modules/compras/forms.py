from __future__ import annotations

from app.forms import BaseForm, DataRequired, Length, NumberRange, Optional, Regexp
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField


class SupplierForm(BaseForm):
    ruc = StringField(
        "RUC",
        validators=[DataRequired(), Length(min=11, max=11, message="El RUC debe tener exactamente 11 dígitos."), Regexp(r"^\d{11}$", message="El RUC solo debe contener dígitos.")],
        description="Número de RUC del proveedor (11 dígitos)",
        render_kw={"placeholder": "20123456789"},
    )
    razon_social = StringField(
        "Razón social",
        validators=[DataRequired(), Length(max=255)],
        description="Nombre legal o razón social del proveedor",
        render_kw={"placeholder": "Distribuidora ABC S.A.C."},
    )
    condicion_pago = SelectField(
        "Condición de pago",
        choices=[("contado", "Contado"), ("credito", "Crédito")],
        validators=[DataRequired()],
        description="Condición de pago por defecto para las órdenes de compra",
    )
    submit = SubmitField("Crear proveedor")


class PurchaseOrderForm(BaseForm):
    proveedor_id = SelectField(
        "Proveedor",
        coerce=int,
        validators=[DataRequired()],
        description="Seleccione el proveedor para esta orden de compra",
    )
    producto_id = SelectField(
        "Producto",
        coerce=int,
        validators=[DataRequired()],
        description="Producto a solicitar en esta orden",
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha de emisión de la orden de compra",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    cantidad = DecimalField(
        "Cantidad",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Cantidad solicitada del producto",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    precio_unitario = DecimalField(
        "Precio unitario",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Precio por unidad sin IGV",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    observaciones = TextAreaField(
        "Observaciones",
        validators=[Optional(), Length(max=1000)],
        description="Notas adicionales para esta orden (máx. 1000 caracteres)",
        render_kw={"placeholder": "Ingrese observaciones adicionales...", "rows": 3},
    )
    submit = SubmitField("Emitir orden")


class ReceptionForm(BaseForm):
    oc_id = SelectField(
        "Orden de compra",
        coerce=int,
        validators=[DataRequired()],
        description="Seleccione la orden de compra a recibir",
    )
    almacen_id = SelectField(
        "Almacén",
        coerce=int,
        validators=[DataRequired()],
        description="Almacén donde se ingresará la mercadería",
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha real de recepción de la mercadería",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    cantidad_recibida = DecimalField(
        "Cantidad recibida",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Cantidad physically recibida en esta entrega",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    submit = SubmitField("Registrar recepción")
