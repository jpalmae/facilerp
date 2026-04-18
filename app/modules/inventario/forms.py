from __future__ import annotations

from app.forms import BaseForm, DataRequired, Length, NumberRange, Optional
from wtforms import DecimalField, SelectField, StringField, SubmitField


class ProductForm(BaseForm):
    codigo = StringField(
        "Código",
        validators=[DataRequired(), Length(max=50)],
        description="Código interno único del producto",
        render_kw={"placeholder": "PROD-001"},
    )
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(max=255)],
        description="Nombre descriptivo del producto",
        render_kw={"placeholder": "Aceite lubricante 20W-50"},
    )
    categoria = StringField(
        "Categoría",
        validators=[Optional(), Length(max=120)],
        description="Categoría para agrupar productos (ej: Lubricantes, Filtros)",
        render_kw={"placeholder": "Lubricantes"},
    )
    unidad_medida = StringField(
        "Unidad",
        validators=[DataRequired(), Length(max=20)],
        description="Unidad de medida (ej: UND, GAL, KG, LT)",
        render_kw={"placeholder": "UND"},
    )
    tipo = SelectField(
        "Tipo",
        choices=[("bien", "Bien"), ("servicio", "Servicio")],
        validators=[DataRequired()],
        description="Un bien tiene control de stock; un servicio no",
    )
    precio_venta = DecimalField(
        "Precio de venta",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        description="Precio de venta al público (incluye IGV)",
        render_kw={"placeholder": "0.00", "min": "0", "step": "0.01"},
    )
    stock_minimo = DecimalField(
        "Stock mínimo",
        validators=[DataRequired(), NumberRange(min=0)],
        places=2,
        description="Cantidad mínima antes de generar alerta de reposición",
        render_kw={"placeholder": "0.00", "min": "0", "step": "0.01"},
    )
    submit = SubmitField("Crear producto")


class WarehouseForm(BaseForm):
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(max=120)],
        description="Nombre identificatorio del almacén",
        render_kw={"placeholder": "Almacén Principal"},
    )
    ubicacion = StringField(
        "Ubicación",
        validators=[Optional(), Length(max=255)],
        description="Dirección o referencia de la ubicación del almacén",
        render_kw={"placeholder": "Av. Industrial 123, Lima"},
    )
    submit = SubmitField("Crear almacén")


class MovementForm(BaseForm):
    producto_id = SelectField(
        "Producto",
        coerce=int,
        validators=[DataRequired()],
        description="Producto al que se aplica el movimiento",
    )
    almacen_id = SelectField(
        "Almacén",
        coerce=int,
        validators=[DataRequired()],
        description="Almacén donde se registra el movimiento",
    )
    tipo = SelectField(
        "Tipo",
        choices=[("entrada", "Entrada"), ("salida", "Salida"), ("ajuste", "Ajuste")],
        validators=[DataRequired()],
        description="Entrada incrementa stock, salida lo reduce, ajuste corrige diferencias",
    )
    cantidad = DecimalField(
        "Cantidad",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Cantidad de unidades del movimiento",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    costo_unitario = DecimalField(
        "Costo unitario",
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0,
        description="Costo por unidad (obligatorio en entradas, recalcula el costo promedio)",
        render_kw={"placeholder": "0.00", "min": "0", "step": "0.01"},
    )
    submit = SubmitField("Registrar movimiento")
