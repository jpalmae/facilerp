from flask import Blueprint


bp = Blueprint("reportes", __name__, template_folder="../../templates")


from app.modules.reportes import routes  # noqa: E402,F401
