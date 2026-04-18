from __future__ import annotations

from app.forms import BaseForm, DataRequired, Length, NumberRange, Optional, Regexp
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField


class ClientForm(BaseForm):
    documento = StringField(
        "Documento",
        validators=[DataRequired(), Length(min=8, max=11, message="El documento debe tener entre 8 y 11 caracteres."), Regexp(r"^\d+$", message="El documento solo debe contener dígitos.")],
        description="DNI (8 dígitos) o RUC (11 dígitos) del cliente",
        render_kw={"placeholder": "12345678"},
    )
    razon_social = StringField(
        "Razón social",
        validators=[DataRequired(), Length(max=255)],
        description="Nombre legal o razón social del cliente",
        render_kw={"placeholder": "Empresa XYZ S.A.C."},
    )
    condicion_pago = SelectField(
        "Condición de pago",
        choices=[("credito", "Crédito"), ("contado", "Contado")],
        validators=[DataRequired()],
        description="Condición de pago por defecto para los pedidos de venta",
    )
    submit = SubmitField("Crear cliente")


class SalesOrderForm(BaseForm):
    cliente_id = SelectField(
        "Cliente",
        coerce=int,
        validators=[DataRequired()],
        description="Seleccione el cliente para este pedido",
    )
    producto_id = SelectField(
        "Producto",
        coerce=int,
        validators=[DataRequired()],
        description="Producto a incluir en este pedido",
    )
    almacen_id = SelectField(
        "Almacén",
        coerce=int,
        validators=[DataRequired()],
        description="Almacén desde donde se despachará la mercadería",
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha del pedido de venta",
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
        description="Precio de venta por unidad (incluye IGV)",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    observaciones = TextAreaField(
        "Observaciones",
        validators=[Optional(), Length(max=1000)],
        description="Notas adicionales para este pedido (máx. 1000 caracteres)",
        render_kw={"placeholder": "Ingrese observaciones adicionales...", "rows": 3},
    )
    submit = SubmitField("Confirmar venta")
