from flask import Blueprint


bp = Blueprint("tesoreria", __name__, template_folder="../../templates")


from app.modules.tesoreria import routes  # noqa: E402,F401
