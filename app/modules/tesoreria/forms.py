from __future__ import annotations

from app.forms import BaseForm, DataRequired, Length, NumberRange, Optional
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField
from wtforms.validators import ValidationError


class TreasuryAccountForm(BaseForm):
    tipo = SelectField(
        "Tipo",
        choices=[("banco", "Banco"), ("caja", "Caja")],
        validators=[DataRequired()],
        description="Tipo de cuenta: Banco para cuentas bancarias, Caja para fondos en efectivo",
    )
    nombre = StringField(
        "Nombre",
        validators=[DataRequired(), Length(max=120)],
        description="Nombre identificatorio de la cuenta",
        render_kw={"placeholder": "Banco BCP - Cuenta corriente"},
    )
    banco = StringField(
        "Banco",
        validators=[Optional(), Length(max=120)],
        description="Nombre de la entidad bancaria (solo para tipo Banco)",
        render_kw={"placeholder": "Banco de Crédito del Perú"},
    )
    numero_cuenta = StringField(
        "Número de cuenta",
        validators=[Optional(), Length(max=60)],
        description="Número de cuenta bancaria",
        render_kw={"placeholder": "193-1234567-0-01"},
    )
    moneda = SelectField(
        "Moneda",
        choices=[("PEN", "PEN — Soles"), ("USD", "USD — Dólares")],
        validators=[DataRequired()],
        description="Moneda en la que se registran los movimientos de esta cuenta",
    )
    cuenta_contable_codigo = SelectField(
        "Cuenta contable",
        choices=[],
        validators=[DataRequired()],
        description="Cuenta del Plan Contable asociada a esta cuenta de tesorería",
    )
    submit = SubmitField("Crear cuenta")


class TreasuryMovementForm(BaseForm):
    cuenta_id = SelectField(
        "Cuenta",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta de tesorería donde se registra el movimiento",
    )
    tipo = SelectField(
        "Tipo",
        choices=[("ingreso", "Ingreso"), ("egreso", "Egreso")],
        validators=[DataRequired()],
        description="Ingreso incrementa el saldo, egreso lo reduce",
    )
    monto = DecimalField(
        "Monto",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Monto del movimiento en la moneda de la cuenta",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha del movimiento",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    glosa = StringField(
        "Glosa",
        validators=[DataRequired(), Length(max=255)],
        description="Descripción del movimiento",
        render_kw={"placeholder": "Cobro factura F001-123"},
    )
    contra_cuenta_codigo = SelectField(
        "Contra cuenta",
        choices=[],
        validators=[DataRequired()],
        description="Cuenta contable contraparte del movimiento",
    )
    submit = SubmitField("Registrar movimiento")


class TransferForm(BaseForm):
    cuenta_origen_id = SelectField(
        "Cuenta origen",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta de donde salen los fondos",
    )
    cuenta_destino_id = SelectField(
        "Cuenta destino",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta donde ingresan los fondos",
    )
    monto = DecimalField(
        "Monto",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Monto a transferir entre cuentas",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha de la transferencia",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    glosa = StringField(
        "Glosa",
        validators=[DataRequired(), Length(max=255)],
        description="Motivo de la transferencia",
        render_kw={"placeholder": "Transferencia entre cuentas"},
    )
    submit = SubmitField("Realizar transferencia")

    def validate_cuenta_destino_id(self, field):
        if field.data and hasattr(self, "cuenta_origen_id") and field.data == self.cuenta_origen_id.data:
            raise ValidationError("Las cuentas origen y destino no pueden ser la misma.")


class ExchangeRateForm(BaseForm):
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha del tipo de cambio",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    submit = SubmitField("Actualizar tipo de cambio")


class ReconcileForm(BaseForm):
    cuenta_id = SelectField(
        "Cuenta",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta de tesorería a conciliar",
    )
    csv_file = FileField(
        "Archivo CSV",
        validators=[FileAllowed(["csv"], "Solo archivos CSV")],
        description="Archivo CSV con los movimientos bancarios a conciliar",
    )
    submit = SubmitField("Conciliar")
