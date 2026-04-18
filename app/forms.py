# -*- coding: utf-8 -*-
"""
Base form module with Spanish validation messages for WTForms.

All app forms should inherit from BaseForm to get consistent
Spanish-language validation messages out of the box.
"""

from flask_wtf import FlaskForm
from wtforms.validators import (
    DataRequired as _DataRequired,
    Email as _Email,
    EqualTo as _EqualTo,
    Length as _Length,
    NumberRange as _NumberRange,
    Optional as _Optional,
    Regexp as _Regexp,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Factory functions that wrap WTForms validators with Spanish default messages
# ---------------------------------------------------------------------------

def Required(message="Este campo es obligatorio."):
    """Valida que el campo no esté vacío (alias de DataRequired)."""
    return _DataRequired(message=message)


def DataRequired(message="Este campo es obligatorio."):
    """Valida que el campo contenga datos."""
    return _DataRequired(message=message)


def Email(message="Ingrese un correo electrónico válido."):
    """Valida que el campo contenga una dirección de correo válida."""
    return _Email(message=message)


def Length(min=-1, max=-1, message=None):
    """
    Valida la longitud del campo.

    Mensaje por defecto según los parámetros:
      - Si se indican ambos min y max:
        «Debe tener entre %(min)d y %(max)d caracteres.»
      - Si solo min:
        «Debe tener al menos %(min)d caracteres.»
      - Si solo max:
        «Debe tener máximo %(max)d caracteres.»
    """
    if message is None:
        if min != -1 and max != -1:
            message = "Debe tener entre %(min)d y %(max)d caracteres."
        elif min != -1:
            message = "Debe tener al menos %(min)d caracteres."
        elif max != -1:
            message = "Debe tener máximo %(max)d caracteres."
    return _Length(min=min, max=max, message=message)


def NumberRange(min=None, max=None, message=None):
    """
    Valida que el valor sea un número dentro del rango indicado.

    Mensaje por defecto según los parámetros:
      - Si se indican ambos min y max:
        «Debe ser un número entre %(min)s y %(max)s.»
      - Si solo min:
        «Debe ser mayor o igual a %(min)s.»
      - Si solo max:
        «Debe ser menor o igual a %(max)s.»
    """
    if message is None:
        if min is not None and max is not None:
            message = "Debe ser un número entre %(min)s y %(max)s."
        elif min is not None:
            message = "Debe ser mayor o igual a %(min)s."
        elif max is not None:
            message = "Debe ser menor o igual a %(max)s."
    return _NumberRange(min=min, max=max, message=message)


def Optional(*args, **kwargs):
    """
    Permite que el campo quede vacío sin activar validaciones.

    Se delega directamente al validator original ya que no requiere mensaje.
    """
    return _Optional(*args, **kwargs)


def Regexp(regex, message="El formato no es válido."):
    """Valida que el campo coincida con la expresión regular indicada."""
    return _Regexp(regex, message=message)


def EqualTo(fieldname, message="Debe ser igual a %(other_name)s."):
    """Valida que el campo sea igual a otro campo del formulario."""
    return _EqualTo(fieldname, message=message)


# ---------------------------------------------------------------------------
# Base form class
# ---------------------------------------------------------------------------

class BaseForm(FlaskForm):
    """
    Clase base para todos los formularios de la aplicación.

    Hereda de FlaskForm y sirve como punto de extensión para añadir
    comportamiento común a todos los formularios (p. ej. estilos
    automáticos, limpieza de datos, etc.).
    """
