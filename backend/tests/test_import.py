"""Importing: text parsing, JSON-LD extraction, the URL guard, and the
endpoints that turn all three into drafts.

Nothing here touches the network. `fetch_page` is replaced where a test needs
a page, because a test that depends on a recipe site staying up is a test that
fails for reasons that have nothing to do with this code.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.services import web_import
from app.services.recipe_text import (
    guess_category,
    parse_ingredient_line,
    parse_quantity,
    parse_recipe_text,
)
from app.services.web_import import (
    SourceFetchError,
    check_url,
    extract_jsonld_recipe,
    html_to_text,
    iso_duration_to_minutes,
    payload_from_jsonld,
    payload_from_page,
)

D = Decimal


# --------------------------------------------------------------------------
# quantities
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1", "1"),
        ("2.5", "2.5"),
        ("1/2", "0.5"),
        ("1 1/2", "1.5"),
        ("½", "0.5"),
        ("1½", "1.5"),
        ("¾", "0.75"),
        ("1,5", "1.5"),  # comma decimal
        ("2-3", "2"),  # a range becomes its lower bound
        ("2 – 3", "2"),
    ],
)
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == D(expected)


@pytest.mark.parametrize("text", ["", "   ", "a pinch", "some"])
def test_parse_quantity_gives_up_rather_than_guessing(text):
    assert parse_quantity(text) is None


# --------------------------------------------------------------------------
# ingredient lines
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line,quantity,unit,name",
    [
        ("1 1/2 cups arborio rice", "1.5", "cups", "arborio rice"),
        ("2 tablespoons butter", "2", "tablespoons", "butter"),
        ("250 g chestnut mushrooms", "250", "g", "chestnut mushrooms"),
        ("2 cloves garlic", "2", "cloves", "garlic"),
        ("2 cups of flour", "2", "cups", "flour"),
        ("½ cup white wine", "0.5", "cup", "white wine"),
        ("3 large eggs", "3", None, "large eggs"),
        ("- 1 onion, finely sliced", "1", None, "onion, finely sliced"),
        ("1. 400g tinned tomatoes", "400", "g", "tinned tomatoes"),
    ],
)
def test_parse_ingredient_line(line, quantity, unit, name):
    parsed = parse_ingredient_line(line)
    assert parsed["quantity"] == quantity
    assert parsed["unit"] == unit
    assert parsed["name"] == name


def test_amountless_ingredients_stay_amountless():
    """"Salt to taste" must not acquire a quantity, or a unit called "salt"."""
    parsed = parse_ingredient_line("Salt and pepper to taste")
    assert parsed["quantity"] is None
    assert parsed["unit"] is None
    assert parsed["name"] == "Salt and pepper to taste"


def test_trailing_notes_are_kept():
    """Dropping what the cook wrote is worse than an untidy name."""
    assert parse_ingredient_line("2 onions, finely sliced")["name"] == "onions, finely sliced"


def test_a_line_naming_no_ingredient_is_dropped():
    assert parse_ingredient_line("2 cups") is None
    assert parse_ingredient_line("   ") is None


@pytest.mark.parametrize(
    "name,category",
    [
        ("black pepper", "spice_sauce"),
        ("soy sauce", "spice_sauce"),
        ("arborio rice", "pantry_dry_good"),
        ("chestnut mushrooms", "raw_ingredient"),
        # Matches how the recipes already in the library are filed.
        ("chicken stock", "pantry_dry_good"),
    ],
)
def test_category_is_a_first_guess(name, category):
    assert guess_category(name) == category


def test_no_keyword_decides_a_column_by_accident():
    """A word in both sets gets its column from the order of the checks, which
    is not a reason. "stock" was in both."""
    from app.services.recipe_text import _PANTRY_WORDS, _SPICE_WORDS

    assert not (_SPICE_WORDS & _PANTRY_WORDS)


# --------------------------------------------------------------------------
# whole recipes, pasted
# --------------------------------------------------------------------------

PASTED = """Mushroom Risotto
Serves 4
Prep time: 10 min
Cook time: 30 min

Ingredients:
1 1/2 cups arborio rice
1 l chicken stock
250 g chestnut mushrooms
2 cloves garlic
salt and pepper

Method:
1. Soften the garlic in butter.
2. Toast the rice until translucent.
3. Add stock a ladle at a time.
"""


def test_parse_pasted_recipe():
    payload = parse_recipe_text(PASTED)

    assert payload["title"] == "Mushroom Risotto"
    assert payload["servings"] == 4
    assert payload["prep_time"] == 10
    assert payload["cook_time"] == 30
    assert [i["name"] for i in payload["ingredients"]] == [
        "arborio rice", "chicken stock", "chestnut mushrooms", "garlic", "salt and pepper",
    ]
    assert [s["instruction_text"] for s in payload["steps"]][0] == "Soften the garlic in butter."


def test_step_numbers_come_out_as_a_real_sequence():
    """The parser can't produce the gap-or-repeat that validation rejects:
    numbering is assigned by position, not read from the text."""
    payload = parse_recipe_text("Ingredients:\n1 egg\n\nMethod:\n5. whisk\n5. fry\n9. serve")

    assert [s["order"] for s in payload["steps"]] == [1, 2, 3]
    assert payload["steps"][0]["instruction_text"] == "whisk"


# A recipe as it actually arrives: no `Ingredients:` heading, a glued amount,
# a range, a mixed fraction, a vulgar fraction, and an amountless last line.
MESSY = """Dad's Bolognese
Serves 6

2 tbsp olive oil
1 large onion, finely diced
2-3 cloves garlic
500g beef mince
400g tinned tomatoes
1 1/2 cups beef stock
salt and pepper to taste

Method:
1. Soften the onion and garlic in the oil.
2. Brown the mince.
"""


def test_a_glued_amount_is_still_an_ingredient():
    """`500g beef mince` has no space, so the line did not look like an
    ingredient at all and was filed as an instruction."""
    payload = parse_recipe_text(MESSY)
    names = [i["name"] for i in payload["ingredients"]]

    assert "beef mince" in names
    assert next(i for i in payload["ingredients"] if i["name"] == "beef mince")["quantity"] == "500"
    assert not any("500" in s["instruction_text"] for s in payload["steps"])


def test_a_glued_amount_opens_the_ingredient_list_on_its_own():
    """The case above is also caught by the amountless-run rule, because a
    normal ingredient precedes it. Here the glued line is the first one, so
    only the routing fix can save it."""
    payload = parse_recipe_text("Quick Sauce\n400g tinned tomatoes\n1 tsp salt\nSimmer for ten.")

    assert [i["name"] for i in payload["ingredients"]] == ["tinned tomatoes", "salt"]
    assert [s["instruction_text"] for s in payload["steps"]] == ["Simmer for ten."]


def test_an_amountless_line_among_ingredients_is_an_ingredient():
    """"salt and pepper to taste" carries no amount; what makes it an
    ingredient is sitting in the middle of a list of them."""
    payload = parse_recipe_text(MESSY)
    names = [i["name"] for i in payload["ingredients"]]

    assert "salt and pepper to taste" in names
    assert len(payload["ingredients"]) == 7


def test_the_ingredient_run_still_ends_at_a_sentence():
    """The rule above must not swallow the method when there is no heading."""
    payload = parse_recipe_text("Toastie\n2 slices bread\n30 g cheddar\nGrill until melted.")

    assert [i["name"] for i in payload["ingredients"]] == ["bread", "cheddar"]
    assert [s["instruction_text"] for s in payload["steps"]] == ["Grill until melted."]


def test_headings_are_not_needed():
    """Most pasted recipes have no `Ingredients:` line. Amount-led lines are
    ingredients; the rest are steps."""
    payload = parse_recipe_text("Cheese Toastie\n2 slices bread\n30 g cheddar\nGrill until melted.")

    assert [i["name"] for i in payload["ingredients"]] == ["bread", "cheddar"]
    assert [s["instruction_text"] for s in payload["steps"]] == ["Grill until melted."]


def test_a_parsed_draft_passes_validation():
    """The two halves have to fit: a clean paste should be promotable without
    the reviewer fixing anything first."""
    from app.services.drafts import has_errors, validate_payload

    assert not has_errors(validate_payload(parse_recipe_text(PASTED)))


def test_an_unusable_paste_produces_a_draft_that_validation_rejects():
    """Garbage in is allowed to produce a draft -- that is what drafts are
    for -- but it must not pass validation."""
    from app.services.drafts import has_errors, validate_payload

    payload = parse_recipe_text("just some words about soup")

    assert has_errors(validate_payload(payload))


# --------------------------------------------------------------------------
# JSON-LD
# --------------------------------------------------------------------------

JSONLD_PAGE = """<!doctype html><html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"WebSite","name":"Some Food Blog"},
  {"@type":["Recipe","Thing"],
   "name":"Leek &amp; Potato Soup",
   "recipeYield":["4","4 servings"],
   "prepTime":"PT10M","cookTime":"PT1H15M",
   "recipeCategory":"Soup","keywords":"winter, easy",
   "recipeIngredient":["3 leeks, sliced","30 g butter","1 l chicken stock"],
   "recipeInstructions":[
     {"@type":"HowToStep","text":"Sweat the leeks in the butter."},
     {"@type":"HowToStep","text":"Add the stock and simmer."}]}
]}
</script></head><body><p>blah</p></body></html>"""


def test_extract_jsonld_recipe_from_graph():
    node = extract_jsonld_recipe(JSONLD_PAGE)
    assert node is not None
    assert node["name"] == "Leek & Potato Soup"


def test_a_malformed_block_does_not_hide_a_later_good_one():
    page = '<script type="application/ld+json">{oops</script>' + JSONLD_PAGE
    assert extract_jsonld_recipe(page) is not None


def test_payload_from_jsonld():
    payload = payload_from_jsonld(extract_jsonld_recipe(JSONLD_PAGE))

    assert payload["title"] == "Leek & Potato Soup"
    assert payload["servings"] == 4
    assert payload["prep_time"] == 10
    assert payload["cook_time"] == 75
    assert payload["tags"] == ["soup", "winter", "easy"]
    assert [i["name"] for i in payload["ingredients"]] == ["leeks, sliced", "butter", "chicken stock"]
    assert [i["unit"] for i in payload["ingredients"]] == [None, "g", "l"]
    assert [s["order"] for s in payload["steps"]] == [1, 2]


@pytest.mark.parametrize(
    "value,minutes",
    [("PT30M", 30), ("PT1H", 60), ("PT1H30M", 90), ("P1DT2H", 1560), ("PT45S", 1)],
)
def test_iso_durations(value, minutes):
    assert iso_duration_to_minutes(value) == minutes


@pytest.mark.parametrize("value", ["", "half an hour", None, 30, "PT"])
def test_unreadable_durations_are_none_rather_than_a_guess(value):
    assert iso_duration_to_minutes(value) is None


def test_instructions_as_one_prose_blob_are_split():
    node = {"@type": "Recipe", "name": "x", "recipeInstructions": "Chop it. Cook it. Eat it."}
    assert len(payload_from_jsonld(node)["steps"]) == 3


def test_instructions_in_howto_sections_are_flattened():
    node = {
        "@type": "Recipe",
        "name": "x",
        "recipeInstructions": [
            {"@type": "HowToSection", "itemListElement": [{"@type": "HowToStep", "text": "one"}]},
            {"@type": "HowToSection", "itemListElement": [{"@type": "HowToStep", "text": "two"}]},
        ],
    }
    assert [s["instruction_text"] for s in payload_from_jsonld(node)["steps"]] == ["one", "two"]


def test_page_without_jsonld_falls_back_to_text():
    page = "<html><body><h1>Toastie</h1><p>2 slices bread</p><p>Grill it.</p></body></html>"

    payload, source_text, from_jsonld = payload_from_page(page)

    assert from_jsonld is False
    assert "Toastie" in source_text
    assert [i["name"] for i in payload["ingredients"]] == ["bread"]


def test_jsonld_is_preferred_over_the_page_text():
    payload, source_text, from_jsonld = payload_from_page(JSONLD_PAGE)

    assert from_jsonld is True
    # The kept source is the publisher's structured data, not the article.
    assert json.loads(source_text)["name"] == "Leek & Potato Soup"


def test_html_to_text_drops_scripts_and_styles():
    text = html_to_text("<html><style>p{color:red}</style><script>alert(1)</script><p>Hi</p></html>")
    assert "alert" not in text and "color" not in text
    assert "Hi" in text


# --------------------------------------------------------------------------
# the URL guard
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/recipe",
        "http://127.0.0.1:8000/recipe",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/recipe",
    ],
)
def test_private_addresses_are_refused(url):
    """CookVault fetches whatever URL it is handed, so it must not be usable
    to reach inside the network."""
    with pytest.raises(SourceFetchError, match="private address"):
        check_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "data:text/html,hi"])
def test_non_http_schemes_are_refused(url):
    with pytest.raises(SourceFetchError, match="http"):
        check_url(url)


def test_unresolvable_host_is_refused():
    with pytest.raises(SourceFetchError, match="resolve"):
        check_url("http://this-host-does-not-exist.invalid/recipe")


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------


def test_paste_import_creates_a_draft_with_provenance(client):
    response = client.post("/import/paste", json={"text": PASTED, "source_title": "Nonna's card"})
    assert response.status_code == 201
    draft = response.json()

    assert draft["status"] == "draft"
    assert draft["title"] == "Mushroom Risotto"
    assert len(draft["payload"]["ingredients"]) == 5

    prov = draft["provenance"]
    assert prov["import_method"] == "paste"
    assert prov["source_title"] == "Nonna's card"
    # The raw paste is kept apart from what was parsed out of it.
    assert prov["original_text"] == PASTED
    assert prov["extracted_payload"]["title"] == "Mushroom Risotto"


def test_import_never_creates_a_recipe_directly(client):
    """The whole point: an importer's output goes to the review queue."""
    client.post("/import/paste", json={"text": PASTED})

    assert client.get("/recipes").json() == []
    assert len(client.get("/drafts").json()) == 1


def test_an_imported_draft_promotes_like_any_other(client):
    draft = client.post("/import/paste", json={"text": PASTED}).json()

    assert client.post(f"/drafts/{draft['id']}/validate").json()["ok"] is True
    recipe = client.post(f"/drafts/{draft['id']}/promote").json()

    assert recipe["title"] == "Mushroom Risotto"
    assert recipe["provenance"]["import_method"] == "paste"


def test_empty_paste_is_refused(client):
    assert client.post("/import/paste", json={"text": "   "}).status_code == 400


def test_url_import_reads_the_page(client, monkeypatch):
    monkeypatch.setattr(web_import, "fetch_page", lambda url: JSONLD_PAGE)
    monkeypatch.setattr("app.routers.import_.fetch_page", lambda url: JSONLD_PAGE)

    response = client.post("/import", json={"url": "https://example.com/soup"})
    assert response.status_code == 201
    draft = response.json()

    assert draft["title"] == "Leek & Potato Soup"
    assert draft["payload"]["cook_time"] == 75
    prov = draft["provenance"]
    assert prov["import_method"] == "url_fetch"
    assert prov["source_url"] == "https://example.com/soup"
    assert prov["source_type"] == "web"


def test_a_fetch_failure_is_the_callers_problem_not_a_500(client, monkeypatch):
    def boom(url):
        raise SourceFetchError("example.com returned 404.")

    monkeypatch.setattr("app.routers.import_.fetch_page", boom)

    response = client.post("/import", json={"url": "https://example.com/missing"})

    assert response.status_code == 400
    assert "404" in response.json()["detail"]


def test_import_requires_auth_when_the_gate_is_on(locked_client):
    assert locked_client.post("/import/paste", json={"text": PASTED}).status_code == 401
    assert locked_client.post("/import", json={"url": "https://example.com/x"}).status_code == 401
