from __future__ import annotations

from app.forms import BaseForm, DataRequired, Email, Length, Optional
from wtforms import PasswordField, SelectField, SelectMultipleField, StringField, SubmitField, TextAreaField
from wtforms.widgets import CheckboxInput, ListWidget


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class SecurityUserForm(BaseForm):
    nombre = StringField("Nombre", validators=[DataRequired(), Length(min=3, max=160)])
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "Contraseña inicial",
        validators=[Optional(), Length(min=8, max=128)],
    )
    rol = SelectField("Rol", validators=[DataRequired()])
    submit = SubmitField("Guardar usuario")


class SecurityGroupForm(BaseForm):
    nombre = StringField("Nombre del grupo", validators=[DataRequired(), Length(min=3, max=120)])
    descripcion = TextAreaField("Descripción", validators=[Optional(), Length(max=255)])
    permisos = MultiCheckboxField("Permisos", validators=[Optional()])
    submit = SubmitField("Guardar grupo")


class SecurityCompanyForm(BaseForm):
    ruc = StringField("RUC", validators=[DataRequired(), Length(min=11, max=11)])
    razon_social = StringField(
        "Razón social",
        validators=[DataRequired(), Length(min=3, max=255)],
    )
    moneda = SelectField(
        "Moneda",
        choices=[("PEN", "PEN"), ("USD", "USD")],
        validators=[DataRequired()],
    )
    regimen_tributario = StringField(
        "Régimen tributario",
        validators=[DataRequired(), Length(min=3, max=120)],
        default="Régimen General",
    )
    submit = SubmitField("Crear empresa")
