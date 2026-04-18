from flask import Blueprint


bp = Blueprint("contabilidad", __name__, template_folder="../../templates")


from app.modules.contabilidad import routes  # noqa: E402,F401
