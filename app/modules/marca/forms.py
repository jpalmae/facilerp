from __future__ import annotations

import re

from app.forms import BaseForm, DataRequired, Length, Regexp
from flask_wtf.file import FileAllowed, FileField
from wtforms import StringField, SubmitField


HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BrandForm(BaseForm):
    nombre_sistema = StringField(
        "Nombre del sistema", validators=[DataRequired(), Length(min=3, max=120)]
    )
    color_primary = StringField(
        "Color primario",
        validators=[
            DataRequired(),
            Regexp(HEX_COLOR, message="Usa un color hexadecimal válido."),
        ],
    )
    color_secondary = StringField(
        "Color secundario",
        validators=[
            DataRequired(),
            Regexp(HEX_COLOR, message="Usa un color hexadecimal válido."),
        ],
    )
    logo = FileField(
        "Logo",
        validators=[FileAllowed(["png", "svg"], "Sólo PNG o SVG.")],
    )
    favicon = FileField(
        "Favicon",
        validators=[FileAllowed(["png", "svg", "ico"], "Sólo PNG, SVG o ICO.")],
    )
    submit = SubmitField("Guardar cambios")
