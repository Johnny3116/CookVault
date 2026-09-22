"""Turn written recipe text into a draft payload.

This is a **heuristic**, and it is only allowed to exist because its output
lands in a draft rather than in the cookbook. It will mis-split an awkward
ingredient line and it will guess a category wrong; validation then reports
what is missing and a human fixes the rest before promotion. That is the
whole arrangement -- a parser this rough would be indefensible writing
straight into `recipes`.

Deliberately deterministic: no model, no network, no API key. "2 tbsp butter"
does not need a language model, and a function that always does the same thing
to the same text is one you can write regression tests against. When Agent
Zero is eventually wired up it produces the same payload shape and lands in
the same draft, so everything downstream is already built and tested.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.units import canonical_unit

# Vulgar fractions, which recipe sites emit constantly.
_VULGAR = {
    "½": Decimal("0.5"), "⅓": Decimal("1") / 3, "⅔": Decimal("2") / 3,
    "¼": Decimal("0.25"), "¾": Decimal("0.75"), "⅕": Decimal("0.2"),
    "⅖": Decimal("0.4"), "⅗": Decimal("0.6"), "⅘": Decimal("0.8"),
    "⅙": Decimal("1") / 6, "⅚": Decimal("5") / 6, "⅛": Decimal("0.125"),
    "⅜": Decimal("0.375"), "⅝": Decimal("0.625"), "⅞": Decimal("0.875"),
}

# Words that act as units without being convertible. units.py already treats
# these as legitimate ("pinch, sprig and clove are real recipe entries"), so
# reading them as units is consistent -- and validation will warn that they
# won't merge in the shopping list, which is exactly the right nudge.
_COUNT_WORDS = {
    "clove", "cloves", "sprig", "sprigs", "pinch", "pinches", "dash", "dashes",
    "can", "cans", "tin", "tins", "jar", "jars", "packet", "packets", "pack",
    "slice", "slices", "handful", "handfuls", "bunch", "bunches", "head",
    "heads", "stick", "sticks", "stalk", "stalks", "sheet", "sheets", "knob",
    "knobs", "rasher", "rashers", "fillet", "fillets", "piece", "pieces",
}

# A first guess at the four columns, corrected by whoever reviews the draft.
# Leaving everything in one column would mean re-sorting a dozen ingredients
# by hand after every import.
_SPICE_WORDS = {
    "salt", "pepper", "peppercorns", "paprika", "cumin", "coriander", "chilli",
    "chili", "cinnamon", "nutmeg", "turmeric", "oregano", "thyme", "rosemary",
    "basil", "parsley", "sage", "bay", "vinegar", "soy", "sauce", "mustard",
    "ketchup", "mayonnaise", "honey", "sugar", "spice", "seasoning", "wine",
    "oil",
}
_PANTRY_WORDS = {
    "flour", "rice", "pasta", "spaghetti", "noodles", "lentils", "beans",
    "chickpeas", "oats", "breadcrumbs", "cornflour", "cornstarch", "baking",
    "yeast", "couscous", "quinoa", "tinned", "canned", "tomatoes", "passata",
    "coconut", "stock", "broth",
}

_SECTION_INGREDIENTS = re.compile(r"^\s*(ingredients?|you(?:'| wi)?ll need|shopping list)\s*:?\s*$", re.I)
_SECTION_STEPS = re.compile(r"^\s*(instructions?|method|directions?|steps?|preparation)\s*:?\s*$", re.I)
_SERVINGS = re.compile(r"\b(?:serves|servings?|makes|yield)\b\s*:?\s*(\d+)", re.I)
_PREP = re.compile(r"\bprep(?:aration)?(?:\s*time)?\s*:?\s*(\d+)\s*(?:min|m\b)", re.I)
_COOK = re.compile(r"\bcook(?:ing)?(?:\s*time)?\s*:?\s*(\d+)\s*(?:min|m\b)", re.I)
# "1." / "1)" / "-" / "*" -- list markers, not part of the instruction.
_LIST_MARKER = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[-*•])\s*")


def parse_quantity(text: str) -> Decimal | None:
    """Read the leading amount of an ingredient line.

    Handles "1", "1.5", "1/2", "1 1/2", "½" and "1½". A range ("2-3 apples")
    becomes its lower bound: under-buying by one apple is a smaller error than
    inventing a number, and the reviewer can see the original line.
    """
    text = text.strip()
    if not text:
        return None

    # Split a leading range before anything else: "2-3" -> "2".
    range_match = re.match(r"^(\d+(?:\.\d+)?)\s*[-–]\s*\d+(?:\.\d+)?$", text)
    if range_match:
        text = range_match.group(1)

    total = Decimal(0)
    found = False
    # "1½" arrives as one token; separate the vulgar fraction from the whole.
    # `\d+/\d+` has to come first: alternation is ordered, so a leading `\d+`
    # would otherwise match the "1" of "1/2" and leave "2" as a second whole
    # number, making "1 1/2" add up to 4.
    for part in re.findall(r"\d+/\d+|\d+(?:[.,]\d+)?|[" + "".join(_VULGAR) + r"]", text):
        if part in _VULGAR:
            total += _VULGAR[part]
            found = True
        elif "/" in part:
            numerator, _, denominator = part.partition("/")
            try:
                total += Decimal(numerator) / Decimal(denominator)
            except (InvalidOperation, ZeroDivisionError):
                return None
            found = True
        else:
            try:
                total += Decimal(part.replace(",", "."))
            except InvalidOperation:
                return None
            found = True
    return total if found else None


def _is_quantity_token(token: str) -> bool:
    if token in _VULGAR:
        return True
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?|\d+/\d+|\d+[" + "".join(_VULGAR) + r"]", token))


def _is_unit_token(token: str) -> bool:
    cleaned = token.strip(".,").lower()
    if not cleaned:
        return False
    if cleaned in _COUNT_WORDS:
        return True
    # canonical_unit(None) means "no unit given", so only a real string counts.
    return canonical_unit(cleaned) is not None


# The two sets must stay disjoint: a word in both would have its column
# decided by the order of the checks below rather than by anything meaningful.
# "stock" was in both, and landed in Spices & Sauces while the recipes already
# in the library file it under Pantry.
assert not (_SPICE_WORDS & _PANTRY_WORDS), "a keyword cannot belong to two columns"


def guess_category(name: str) -> str:
    words = set(re.findall(r"[a-z]+", name.lower()))
    if words & _SPICE_WORDS:
        return "spice_sauce"
    if words & _PANTRY_WORDS:
        return "pantry_dry_good"
    return "raw_ingredient"


def _split_glued_amount(tokens: list[str]) -> list[str]:
    """"400g" is one token. Split the amount off when what follows is a unit.

    Leaves "3x4" and "2litres-ish" alone -- only a clean number followed by a
    recognised unit is split.
    """
    if not tokens:
        return tokens
    glued = re.fullmatch(r"(\d+(?:[.,]\d+)?)([a-zA-Z]+)", tokens[0])
    if glued and _is_unit_token(glued.group(2)):
        return [glued.group(1), glued.group(2), *tokens[1:]]
    return tokens


def parse_ingredient_line(line: str) -> dict | None:
    """One written line -> one draft ingredient.

    Everything after the amount and unit is kept verbatim as the name,
    including trailing notes: "onion, finely sliced" stays whole rather than
    being trimmed to "onion". Dropping what the cook wrote is worse than an
    untidy name, and the draft editor is right there.
    """
    line = _LIST_MARKER.sub("", line).strip()
    if not line:
        return None

    tokens = _split_glued_amount(line.split())

    index = 0
    quantity_tokens: list[str] = []
    while index < len(tokens) and _is_quantity_token(tokens[index]):
        quantity_tokens.append(tokens[index])
        index += 1

    quantity = parse_quantity(" ".join(quantity_tokens)) if quantity_tokens else None

    unit = None
    # A unit only counts as one if an amount came before it -- otherwise
    # "Salt to taste" would read "salt" as a unit of "to taste".
    if quantity is not None and index < len(tokens) and _is_unit_token(tokens[index]):
        unit = tokens[index].strip(".,").lower()
        index += 1
        # "2 cups of flour" -- drop the connecting word, keep the ingredient.
        if index < len(tokens) and tokens[index].lower() == "of":
            index += 1

    name = " ".join(tokens[index:]).strip()
    if not name:
        # A line that is all numbers and units names no ingredient.
        return None

    return {
        "name": name,
        "quantity": str(quantity) if quantity is not None else None,
        "unit": unit,
        "category": guess_category(name),
    }


def _looks_like_ingredient(line: str) -> bool:
    stripped = _LIST_MARKER.sub("", line).strip()
    if not stripped:
        return False
    # Same glued-amount split as the parser, or "500g beef mince" would be
    # classified as an instruction and never reach parse_ingredient_line.
    return _is_quantity_token(_split_glued_amount(stripped.split())[0])


def _looks_like_instruction(line: str) -> bool:
    """Does this line end a run of ingredients?

    Used only where there are no `Ingredients:` / `Method:` headings to follow.
    An ingredient is a short noun phrase; an instruction is a sentence. So a
    numbered line, a long line, or one that ends in sentence punctuation ends
    the run -- which is what lets "salt and pepper to taste" stay an
    ingredient while "Grill until melted." becomes a step.
    """
    stripped = line.strip()
    if _LIST_MARKER.match(stripped):
        return True
    return len(stripped) > 60 or stripped.endswith((".", "!", "?"))


def parse_recipe_text(text: str) -> dict:
    """Written recipe -> a draft payload, shaped like RecipeCreate.

    Explicit `Ingredients:` / `Method:` headings are followed when present.
    Without them, lines that start with an amount are read as ingredients and
    the rest as steps, which is how most pasted recipes actually look.

    Step numbers come out as 1..n by construction, so a parsed draft never
    fails validation's sequence check on the parser's account.
    """
    lines = text.splitlines()
    ingredients: list[dict] = []
    step_lines: list[str] = []

    title: str | None = None
    servings: int | None = None
    prep_time: int | None = None
    cook_time: int | None = None

    section: str | None = None
    # Whether we are inside a run of ingredient lines that had no heading.
    in_ingredient_run = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if _SECTION_INGREDIENTS.match(line):
            section = "ingredients"
            in_ingredient_run = False
            continue
        if _SECTION_STEPS.match(line):
            section = "steps"
            in_ingredient_run = False
            continue

        # Metadata can appear anywhere in the header block.
        if servings is None and (match := _SERVINGS.search(line)):
            servings = int(match.group(1))
            if len(line.split()) <= 4:
                continue
        if prep_time is None and (match := _PREP.search(line)):
            prep_time = int(match.group(1))
            if len(line.split()) <= 5:
                continue
        if cook_time is None and (match := _COOK.search(line)):
            cook_time = int(match.group(1))
            if len(line.split()) <= 5:
                continue

        if section is None and title is None and not _looks_like_ingredient(line) and len(line) <= 120:
            title = line
            continue

        if section == "steps":
            step_lines.append(line)
            in_ingredient_run = False
        elif (
            section == "ingredients"
            or _looks_like_ingredient(line)
            # "salt and pepper to taste" carries no amount, but sitting in the
            # middle of a list of ingredients is what makes it one.
            or (in_ingredient_run and not _looks_like_instruction(line))
        ):
            parsed = parse_ingredient_line(line)
            if parsed:
                ingredients.append(parsed)
                in_ingredient_run = True
        else:
            step_lines.append(line)
            in_ingredient_run = False

    steps = [
        {"order": index, "instruction_text": _LIST_MARKER.sub("", line).strip()}
        for index, line in enumerate(step_lines, start=1)
        if _LIST_MARKER.sub("", line).strip()
    ]

    return {
        "title": title or "",
        "servings": servings,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "ingredients": ingredients,
        "steps": steps,
        "tags": [],
        "cook_methods": [],
        "alternates": [],
    }
