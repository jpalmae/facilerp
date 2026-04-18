from __future__ import annotations

from app.forms import BaseForm, DataRequired, Email, Length
from wtforms import BooleanField, PasswordField, StringField, SubmitField


class LoginForm(BaseForm):
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField(
        "Contraseña", validators=[DataRequired(), Length(min=8, max=128)]
    )
    remember = BooleanField("Mantener sesión")
    submit = SubmitField("Ingresar")
