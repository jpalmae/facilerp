from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db
from app.services.bootstrap import ensure_demo_data


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        ensure_demo_data()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()
