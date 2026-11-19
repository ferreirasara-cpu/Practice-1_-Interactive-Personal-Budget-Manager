"""
validation.py - The rules for every field of a transaction.

This file decides what is a valid value and what is not. It does not ask the
user anything and does not print anything: it only checks values and returns
them clean, or raises ValueError with a clear message.
(Brief: "Validate at boundaries, not everywhere" - all rules live here.)

What is inside:
- EXPENSE_CATEGORIES and INCOME_CATEGORIES: dictionaries where each category
  has its list of allowed subcategories (nested data, manual 5.6).
- KINDS, CURRENCIES: sets with the allowed kinds and currencies (manual 5.4).
- MAX_AMOUNT: the largest amount accepted.
- clean_required(): removes spaces and rejects empty values.
- categories_for(): returns the expense or income dictionary for a kind.
- validate_id, validate_date, validate_kind, validate_category,
  validate_subcategory, validate_amount, validate_currency:
  one function per field. Each one cleans, checks and returns the value.
- validate_any_category(): for filters, where the kind may not be known.
- validate_month(): a month like "2026-09", for monthly reports and filters.
- validate_limit_category(): a monthly spending limit can only be set on an
  EXPENSE category (the amount of a limit uses validate_amount).

Tools used:
- Functions as contracts with type hints and docstrings (manual 4.1).
- raise ValueError with f-string messages (manual 3.3).
- try / except to translate Python errors into clear messages (manual 3.2).
- String cleaning: .strip(), .lower(), .upper() (manual 8.1).
- Regular expressions: re.fullmatch (manual 8.3).
- Sets and dictionaries with "in" for fast membership checks (manual 5.4, 5.5).

Rules followed:
- Cleaning is allowed (" Food " -> "food", "eur" -> "EUR").
- Correcting is not (a negative amount is rejected, never made positive).
- Error messages say what is wrong and what value was received.
  The row number is added later by storage.py.
"""

import re
from datetime import date

# ---------------------------------------------------------------------------
# Allowed values (constants: written in CAPITALS, never changed while running)
# ---------------------------------------------------------------------------

# Dictionary: category -> list of its subcategories.
# A dict is used because we look things up by name (the category), not by
# position. The value is a list because we only read it, in a fixed order
# that is nice to show to the user.
EXPENSE_CATEGORIES: dict[str, list[str]] = {
    "food": ["supermarket", "restaurants", "delivery", "general"],
    "transport": ["public_transport", "fuel", "taxi", "general"],
    "home": ["rent", "utilities", "internet", "general"],
    "leisure": ["cinema", "travel", "sports", "general"],
    "health": ["pharmacy", "doctor", "general"],
    "shopping": ["clothes", "electronics", "general"],
}

# Kept separate from expenses, so "income + food" is rejected.
INCOME_CATEGORIES: dict[str, list[str]] = {
    "salary": ["payroll", "bonus", "general"],
    "other_income": ["bizum", "refund", "general"],
}

# Sets: the only question we ask them is "is this value allowed?",
# and "in" on a set answers that very fast (manual 5.4).
KINDS: set[str] = {"expense", "income"}
CURRENCIES: set[str] = {"EUR", "USD", "GBP"}

# Upper limit for one amount. It also rejects float("inf").
# The _ in 1_000_000 is only for readability; Python ignores it.
MAX_AMOUNT: int = 1_000_000


# ---------------------------------------------------------------------------
# Helpers (used by every validator, so each rule is written only once)
# ---------------------------------------------------------------------------

def clean_required(value: object, field: str) -> str:
    """Return the value as clean text, or raise ValueError if it is empty."""
    # str() makes sure we have text even if a number is passed.
    # .strip() removes spaces at both ends: " Food " -> "Food".
    text = str(value).strip()
    if text == "":
        raise ValueError(f"{field} is required")
    return text


def categories_for(kind: str) -> dict[str, list[str]]:
    """Return the dictionary of categories that belongs to a kind."""
    if kind == "expense":
        return EXPENSE_CATEGORIES
    # No "else" needed: return already left the function above.
    return INCOME_CATEGORIES


# ---------------------------------------------------------------------------
# One function per field. Same three steps every time:
#   1. clean   2. check (raise if wrong)   3. return the clean value
# ---------------------------------------------------------------------------

def validate_id(value: object) -> str:
    """Return a clean id like 'T001'. Uniqueness is checked by storage/services."""
    text = clean_required(value, "id").upper()
    # fullmatch: the WHOLE text must match. T = letter T, \d = digit, {3} = 3 times.
    # The r before the string means "raw", so \d is not read as an escape.
    if not re.fullmatch(r"T\d{3}", text):
        raise ValueError(f"id must look like T001, got '{text}'")
    return text


def validate_date(value: object) -> str:
    """Return a date as 'YYYY-MM-DD' text, only if the date really exists."""
    text = clean_required(value, "date")

    # Check 1, the shape: 4 digits - 2 digits - 2 digits.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"date must be YYYY-MM-DD, got '{text}'")

    # Check 2, the date exists: fromisoformat fails for 2026-13-40 or
    # 2025-02-29 (2025 is not a leap year). We catch Python's error and
    # raise our own clearer message instead (manual 3.2).
    # Note: date.fromisoformat was suggested by AI (see AI_DISCLOSURE.md).
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"date '{text}' does not exist")

    # We return text, not a date object: it goes straight to the CSV, and
    # ISO dates sort correctly as text ("2026-09-04" < "2026-10-01").
    return text


def validate_kind(value: object) -> str:
    """Return 'expense' or 'income'."""
    text = clean_required(value, "kind").lower()
    if text not in KINDS:
        raise ValueError(f"kind must be expense or income, got '{text}'")
    return text


def validate_category(kind: str, value: object) -> str:
    """Return a category that exists for the given kind."""
    text = clean_required(value, "category").lower()
    allowed = categories_for(kind)
    # "in" on a dictionary checks its KEYS (the category names).
    if text not in allowed:
        # ", ".join(...) builds "food, health, home..." so the message
        # tells the user what they CAN type (an actionable error).
        options = ", ".join(sorted(allowed))
        raise ValueError(f"category '{text}' is not valid for {kind}. Options: {options}")
    return text


def validate_subcategory(kind: str, category: str, value: object) -> str:
    """Return a subcategory that belongs to the given category.

    The category must be validated FIRST: with an unknown category,
    categories_for(kind)[category] would crash with KeyError.
    """
    text = clean_required(value, "subcategory").lower()
    allowed = categories_for(kind)[category]
    if text not in allowed:
        options = ", ".join(allowed)
        raise ValueError(f"subcategory '{text}' is not valid for {category}. Options: {options}")
    return text


def validate_amount(value: object) -> float:
    """Return a positive amount with at most 2 decimals, up to MAX_AMOUNT."""
    text = clean_required(value, "amount")

    # float("abc") raises ValueError; we replace it with our own message.
    try:
        amount = float(text)
    except ValueError:
        raise ValueError(f"amount must be a number, got '{text}'")

    # Written as "not amount > 0" on purpose: float("nan") is "not a number",
    # and nan <= 0 is False, so "if amount <= 0" would let nan through.
    # "not nan > 0" is True, so nan is rejected. Found while testing.
    if not amount > 0:
        raise ValueError(f"amount must be > 0, got {text}")

    # Also rejects float("inf").
    if amount > MAX_AMOUNT:
        raise ValueError(f"amount must be at most {MAX_AMOUNT}, got {text}")

    # If rounding changes the number, it had more than 2 decimals.
    # We reject it instead of rounding silently (never correct data).
    if round(amount, 2) != amount:
        raise ValueError(f"amount can have at most 2 decimals, got {text}")

    return amount


def validate_currency(value: object) -> str:
    """Return a currency code in capitals: EUR, USD or GBP."""
    text = clean_required(value, "currency").upper()
    if text not in CURRENCIES:
        options = ", ".join(sorted(CURRENCIES))
        raise ValueError(f"currency must be one of {options}, got '{text}'")
    return text


def validate_any_category(value: object) -> str:
    """Return a category that exists for expenses OR income.

    Used by the filter, where the user may not choose a kind first.
    """
    text = clean_required(value, "category").lower()
    # | joins the keys of both dictionaries into one set (set union, manual 5.4).
    all_categories = set(EXPENSE_CATEGORIES) | set(INCOME_CATEGORIES)
    if text not in all_categories:
        options = ", ".join(sorted(all_categories))
        raise ValueError(f"category '{text}' does not exist. Options: {options}")
    return text


def validate_month(value: object) -> str:
    """Return a month as 'YYYY-MM' text, with the month between 01 and 12."""
    text = clean_required(value, "month")

    # Shape: 4 digits, a dash, 2 digits.
    if not re.fullmatch(r"\d{4}-\d{2}", text):
        raise ValueError(f"month must be YYYY-MM, got '{text}'")

    # text[5:] is the part after "YYYY-" (slicing, manual 5.2): "2026-09" -> "09".
    # int("09") -> 9. A month must be between 1 and 12.
    if not 1 <= int(text[5:]) <= 12:
        raise ValueError(f"month '{text}' does not exist")

    # Returned as text: a transaction is in this month if its date starts
    # with it ("2026-09-04".startswith("2026-09") is True).
    return text


def validate_limit_category(value: object) -> str:
    """Return an expense category, the only kind that can have a spending limit."""
    # A limit on income ("spend at most 300 of salary") makes no sense,
    # so we reuse the expense rule instead of writing a new one.
    return validate_category("expense", value)
