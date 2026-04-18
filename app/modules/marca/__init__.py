from flask import Blueprint


bp = Blueprint("marca", __name__, template_folder="../../templates")


from app.modules.marca import routes  # noqa: E402,F401
