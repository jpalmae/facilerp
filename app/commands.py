from __future__ import annotations

import click
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from flask import Flask
from sqlalchemy import text

from app.extensions import db
from app.services.bootstrap import ensure_demo_data


def register_commands(app: Flask) -> None:
    def alembic_config() -> AlembicConfig:
        config = AlembicConfig(str(Path(app.root_path).parent / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", app.config["SQLALCHEMY_DATABASE_URI"])
        return config

    @app.cli.command("init-db")
    def init_db_command():
        """Run all pending migrations and seed demo data."""
        command.upgrade(alembic_config(), "head")
        click.echo("Base de datos inicializada con migraciones.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Load demo/seed data into the database."""
        ensure_demo_data()
        click.echo("Datos demo cargados.")

    @app.cli.command("db-upgrade")
    @click.argument("revision", default="head")
    def db_upgrade_command(revision: str):
        """Apply migrations up to REVISION (default: head)."""
        command.upgrade(alembic_config(), revision)
        click.echo(f"Migraciones aplicadas hasta {revision}.")

    @app.cli.command("db-downgrade")
    @click.argument("revision", default="-1")
    def db_downgrade_command(revision: str):
        """Revert migrations to REVISION (default: -1)."""
        command.downgrade(alembic_config(), revision)
        click.echo(f"Migración revertida a {revision}.")

    @app.cli.command("db-check")
    def db_check_command():
        """Verify database connectivity."""
        db.session.execute(text("SELECT 1"))
        db.session.commit()
        click.echo("Conexión a base de datos OK.")
