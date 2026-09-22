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


@pytest.fixture(scope="session")
def _seeded_aisle_rules(_schema) -> list[dict]:
    """The aisle rules exactly as migration 0006 shipped them.

    Captured once, after migrating, so that each test can be handed the same
    starting point. The migration stays the single source of that seed -- the
    tests read it rather than restating it, which means a change to the seed
    cannot silently disagree with what the tests assume.
    """
    from sqlalchemy import text as sql_text

    from app.db import engine

    with engine.connect() as conn:
        rows = conn.execute(sql_text("SELECT id, term, aisle::text FROM aisle_rules")).all()
    return [{"id": row[0], "term": row[1], "aisle": row[2]} for row in rows]


@pytest.fixture(autouse=True)
def _clean_tables(_seeded_aisle_rules) -> None:
    """Start every test from an empty database.

    TRUNCATE ... CASCADE reaches the child tables through their foreign keys;
    shopping_list_items and recipe_drafts are listed explicitly because their
    references to recipes are nullable, so rows that never had a recipe are
    not reachable from one. meal_plan_drafts has no foreign key at all -- its
    meals are JSONB -- so nothing would reach it either.
    """
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE recipes, shopping_list_items, recipe_drafts, "
                "meal_plan_drafts RESTART IDENTITY CASCADE"
            )
        )
        # Rules are editable data, so a test that edits one would otherwise
        # leak into the next. Reset to what the migration seeded.
        conn.execute(text("TRUNCATE aisle_rules, pantry_items"))
        if _seeded_aisle_rules:
            conn.execute(
                text("INSERT INTO aisle_rules (id, term, aisle) VALUES (:id, :term, CAST(:aisle AS shopping_aisle))"),
                _seeded_aisle_rules,
            )


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


@pytest.fixture
def draft_payload(recipe_payload: dict) -> dict:
    """A draft body whose payload is a valid recipe, with real provenance."""
    return {
        "title": recipe_payload["title"],
        "payload": recipe_payload,
        "provenance": {
            "source_type": "youtube",
            "source_url": "https://example.test/watch?v=abc123",
            "source_title": "The only carbonara video you need",
            "import_method": "agent",
            "original_text": "so you want about two zucchini, an apple, plenty of pepper",
            "extracted_payload": recipe_payload,
            "agent_model": "some-extractor",
            "agent_version": "0.1.0",
        },
    }
