from flask import Blueprint


bp = Blueprint("compras", __name__, template_folder="../../templates")


from app.modules.compras import routes  # noqa: E402,F401
