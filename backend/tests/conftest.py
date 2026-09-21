"""Shared fixtures.

These tests run against a real PostgreSQL database rather than SQLite: the
models use Postgres-specific column types (UUID, ARRAY, native ENUM), so a
SQLite stand-in would not exercise the schema that actually ships.

Point DATABASE_URL at a throwaway database before running. CI starts one as a
service container; see .github/workflows/ci.yml.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_PASSWORD = "correct-horse-battery-staple"


def pytest_configure(config: pytest.Config) -> None:
    if not os.environ.get("DATABASE_URL"):
        raise pytest.UsageError(
            "DATABASE_URL is not set. These tests need a real PostgreSQL database, "
            "e.g. DATABASE_URL=postgresql+psycopg://cookvault:cookvault@localhost:5432/cookvault"
        )


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Bring the test database up to head once per run."""
    from alembic import command
    from alembic.config import Config

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Start every test from an empty database.

    TRUNCATE ... CASCADE reaches the child tables through their foreign keys;
    shopping_list_items is listed explicitly because its recipe_id is nullable,
    so manually-added rows are not reachable from recipes.
    """
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE recipes, shopping_list_items RESTART IDENTITY CASCADE"))


@pytest.fixture
def client() -> TestClient:
    """Client with the password gate disabled (the default deployment mode)."""
    from app.config import settings
    from app.main import app

    settings.cookvault_password = None
    return TestClient(app)


@pytest.fixture
def locked_client() -> TestClient:
    """Client with the password gate enabled."""
    from app.config import settings
    from app.main import app

    settings.cookvault_password = TEST_PASSWORD
    client = TestClient(app)
    yield client
    settings.cookvault_password = None


@pytest.fixture
def recipe_payload() -> dict:
    """A recipe whose ingredients are deliberately not in alphabetical order,
    so tests can tell submitted order from incidental order."""
    return {
        "title": "Test Carbonara",
        "tags": ["italian", "weeknight"],
        "cook_methods": ["stovetop"],
        "estimated_cost": 12.50,
        "servings": 4,
        "is_favorite": False,
        "ingredients": [
            {"name": "zucchini", "quantity": 2, "unit": "ea", "category": "raw_ingredient"},
            {"name": "apple", "quantity": 1, "unit": "ea", "category": "raw_ingredient"},
            {"name": "black pepper", "category": "spice_sauce"},
        ],
        "steps": [
            {"order": 1, "instruction_text": "Boil water", "duration": "5 min"},
            {"order": 2, "instruction_text": "Cook pasta"},
        ],
        "alternates": [
            {
                "type": "ingredient_substitute",
                "original_value": "zucchini",
                "alternate_value": "squash",
            }
        ],
    }
