from __future__ import annotations

from app.forms import BaseForm, DataRequired, NumberRange, Length, Optional
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField


class CollectionForm(BaseForm):
    documento_id = SelectField(
        "Documento por cobrar",
        coerce=int,
        validators=[DataRequired()],
        description="Seleccione el documento CxC al que se aplicará el cobro",
    )
    cuenta_tesoreria_id = SelectField(
        "Cuenta de tesorería",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta bancaria o caja donde se recibirá el pago",
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha en que se recibió el pago",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    monto = DecimalField(
        "Monto",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Monto a cobrar (no debe exceder el saldo pendiente del documento)",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    tipo_pago = SelectField(
        "Tipo de pago",
        choices=[
            ("transferencia", "Transferencia"),
            ("efectivo", "Efectivo"),
            ("tarjeta", "Tarjeta"),
        ],
        validators=[DataRequired()],
        description="Método de pago utilizado",
    )
    submit = SubmitField("Registrar cobro")


class PaymentForm(BaseForm):
    documento_id = SelectField(
        "Documento por pagar",
        coerce=int,
        validators=[DataRequired()],
        description="Seleccione el documento CxP al que se aplicará el pago",
    )
    cuenta_tesoreria_id = SelectField(
        "Cuenta de tesorería",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta bancaria o caja desde donde se realizará el pago",
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha en que se realizó el pago",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    monto = DecimalField(
        "Monto",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Monto a pagar (no debe exceder el saldo pendiente del documento)",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    tipo_pago = SelectField(
        "Tipo de pago",
        choices=[
            ("transferencia", "Transferencia"),
            ("efectivo", "Efectivo"),
            ("tarjeta", "Tarjeta"),
        ],
        validators=[DataRequired()],
        description="Método de pago utilizado",
    )
    submit = SubmitField("Registrar pago")
