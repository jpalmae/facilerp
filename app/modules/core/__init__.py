from flask import Blueprint


bp = Blueprint("core", __name__, template_folder="../../templates")


from app.modules.core import routes  # noqa: E402,F401
