from __future__ import annotations

from app.forms import BaseForm, DataRequired, NumberRange, Length, Optional
from wtforms import DateField, DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import ValidationError


class ManualEntryForm(BaseForm):
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        description="Fecha contable del asiento",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    glosa = StringField(
        "Glosa",
        validators=[DataRequired(), Length(max=500)],
        description="Descripción del asiento contable",
        render_kw={"placeholder": "Registro de compra según factura F001-123"},
    )
    cuenta_debe_id = SelectField(
        "Cuenta debe",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta del Plan Contable que se debita",
    )
    cuenta_haber_id = SelectField(
        "Cuenta haber",
        coerce=int,
        validators=[DataRequired()],
        description="Cuenta del Plan Contable que se acredita",
    )
    monto = DecimalField(
        "Monto",
        validators=[DataRequired(), NumberRange(min=0.01)],
        places=2,
        description="Monto del asiento (afecta ambas cuentas por igual)",
        render_kw={"placeholder": "0.00", "min": "0.01", "step": "0.01"},
    )
    submit = SubmitField("Registrar asiento")

    def validate_cuenta_haber_id(self, field):
        if field.data and hasattr(self, "cuenta_debe_id") and field.data == self.cuenta_debe_id.data:
            raise ValidationError("Las cuentas debe y haber no pueden ser la misma.")


class ClosePeriodForm(BaseForm):
    periodo_id = SelectField(
        "Período",
        coerce=int,
        validators=[DataRequired()],
        description="Período contable a cerrar. Esta acción es irreversible.",
    )
    submit = SubmitField("Cerrar período")


class ReverseEntryForm(BaseForm):
    asiento_id = SelectField(
        "Asiento",
        coerce=int,
        validators=[DataRequired()],
        description="Asiento contable que se desea revertir",
    )
    fecha = DateField(
        "Fecha de reversión",
        validators=[DataRequired()],
        description="Fecha contable para el asiento de reversión",
        render_kw={"placeholder": "dd/mm/aaaa"},
    )
    submit = SubmitField("Revertir asiento")
