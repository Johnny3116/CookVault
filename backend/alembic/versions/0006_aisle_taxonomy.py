"""shopping aisles, as a data-driven mapping

Aisle is a different axis from ingredient category. Category is what a thing
*is* when you cook with it (raw / spice / pantry / misc); aisle is where you
walk to pick it up. Fresh parsley is a spice_sauce ingredient in the produce
aisle. Folding them together would lose one of the two.

The mapping lives in rows rather than in the source because the right answer
is personal and shop-specific -- it should be editable without a deploy. The
set seeded here is a starting point, not a fixture the code depends on: every
one of these rows can be edited or deleted through the API.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-22

"""
from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

shopping_aisle = postgresql.ENUM(
    "produce", "meat_seafood", "dairy_eggs", "bakery", "frozen",
    "pantry", "drinks", "household", "other",
    name="shopping_aisle",
    create_type=False,
)

# term -> aisle. Longest match wins at lookup time, which is why both
# "chicken" and "chicken stock" can sit here without fighting.
SEED: dict[str, list[str]] = {
    "produce": [
        "onion", "onions", "garlic", "leek", "leeks", "potato", "potatoes",
        "carrot", "carrots", "celery", "tomato", "tomatoes", "mushroom",
        "mushrooms", "lettuce", "spinach", "kale", "cabbage", "broccoli",
        "cauliflower", "courgette", "zucchini", "aubergine", "eggplant",
        "pepper", "peppers", "chilli", "cucumber", "apple", "apples", "banana",
        "lemon", "lemons", "lime", "limes", "orange", "ginger", "parsley",
        "coriander", "cilantro", "basil", "mint", "rosemary", "thyme", "sage",
        "spring onion", "shallot", "shallots", "avocado", "berries",
    ],
    "meat_seafood": [
        "chicken", "beef", "mince", "pork", "bacon", "sausage", "sausages",
        "lamb", "steak", "ham", "turkey", "duck", "fish", "salmon", "cod",
        "tuna", "prawns", "shrimp", "squid", "mussels",
    ],
    "dairy_eggs": [
        "milk", "butter", "cheese", "cheddar", "parmesan", "mozzarella",
        "feta", "yoghurt", "yogurt", "cream", "creme fraiche", "sour cream",
        "egg", "eggs",
    ],
    "bakery": [
        "bread", "baguette", "roll", "rolls", "bun", "buns", "tortilla",
        "tortillas", "pitta", "naan", "croissant", "bagel",
    ],
    "frozen": ["frozen peas", "ice cream", "frozen"],
    "pantry": [
        "flour", "sugar", "rice", "pasta", "spaghetti", "noodles", "lentils",
        "beans", "chickpeas", "oats", "breadcrumbs", "cornflour", "cornstarch",
        "baking powder", "yeast", "couscous", "quinoa", "oil", "olive oil",
        "vinegar", "soy sauce", "stock", "chicken stock", "beef stock",
        "vegetable stock", "broth", "tinned tomatoes", "passata", "coconut milk",
        "salt", "black pepper", "paprika", "cumin", "cinnamon", "nutmeg",
        "turmeric", "oregano", "bay leaves", "honey", "mustard", "ketchup",
        "mayonnaise", "peanut butter", "jam", "tea", "coffee",
    ],
    "drinks": ["wine", "white wine", "red wine", "beer", "juice", "water", "cider"],
    "household": [
        "bin bags", "bin liners", "washing up liquid", "kitchen roll",
        "foil", "cling film", "baking paper", "sponges", "detergent",
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    shopping_aisle.create(bind, checkfirst=True)

    op.create_table(
        "aisle_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("term", sa.String(100), nullable=False),
        sa.Column("aisle", shopping_aisle, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_aisle_rules_term", "aisle_rules", ["term"], unique=True)

    op.add_column("shopping_list_items", sa.Column("aisle_override", shopping_aisle, nullable=True))

    rows = [
        {"id": uuid.uuid4(), "term": term, "aisle": aisle}
        for aisle, terms in SEED.items()
        for term in terms
    ]
    op.bulk_insert(
        sa.table(
            "aisle_rules",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("term", sa.String),
            sa.column("aisle", shopping_aisle),
        ),
        rows,
    )


def downgrade() -> None:
    op.drop_column("shopping_list_items", "aisle_override")
    op.drop_index("ix_aisle_rules_term", table_name="aisle_rules")
    op.drop_table("aisle_rules")
    shopping_aisle.drop(op.get_bind(), checkfirst=True)
