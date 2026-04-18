from flask import Blueprint


bp = Blueprint("cxc_cxp", __name__, template_folder="../../templates")


from app.modules.cxc_cxp import routes  # noqa: E402,F401
