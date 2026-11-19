"""
validation.py - The rules for every field of a transaction.

This file decides what is a valid value and what is not. It does not ask the
user anything and does not print anything: it only checks values and returns
them clean, or raises ValueError with a clear message.

What is inside:
- EXPENSE_CATEGORIES and INCOME_CATEGORIES: dictionaries where each category
  has its list of allowed subcategories.
- KINDS, CURRENCIES: sets with the allowed kinds and currencies.
- MAX_AMOUNT: the largest amount accepted.
- clean_required(): removes spaces and rejects empty values.
- categories_for(): returns the expense or income dictionary for a kind.
- validate_id, validate_date, validate_kind, validate_category,
  validate_subcategory, validate_amount, validate_currency:
  one function per field. Each one cleans, checks and returns the value.

Rules followed:
- Cleaning is allowed (" Food " -> "food", "eur" -> "EUR").
- Correcting is not (a negative amount is rejected, never made positive).
- Error messages say what is wrong and what value was received.
  The row number is added later by storage.py.
"""

import re
from datetime import date

#ALLOWED CANTEGORIES AND SUBCATEGORIES FOR EXPENSES AND INCOME
EXPENSE_CATEGORIES = {
    "food": ["supermarket", "restaurants", "delivery", "general"],
    "transport": ["public_transport", "fuel", "taxi", "general"],
    "home": ["rent", "utilities", "internet", "general"],
    "leisure": ["cinema", "travel", "sports", "general"],
    "health": ["pharmacy", "doctor", "general"],
    "shopping": ["clothes", "electronics", "general"],
}
#EXPENSE_CATEGORIES is a dictionary.
# Each key is a category, and its value is the list of allowed subcategories.

INCOME_CATEGORIES = {
    "salary": ["payroll", "bonus", "general"],
    "other_income": ["bizum", "refund", "general"],
}

KINDS = {"expense", "income"}
CURRENCIES = {"EUR", "USD", "GBP"}

#KINDS and CURRENCIES are sets {} because the only question we ask them is “is this value in here?
MAX_AMOUNT = 1_000_000
#upper limit

#TWO HELPER FUNCTIONS: CLEANING AND DIRECTORY FOR CATEGORIES (to avoid repeating code)
def clean_required(value, field):
    text = str(value).strip()
    if text == "":
        raise ValueError(f"{field} is required")
    return text

#str(value) makes sure we have text, even if someone passes a number.
# .strip() removes spaces at the start and end: " Food " → "Food".
# if text == "": after stripping, an empty value means the field is missing, so we stop with a clear message.
# field is only used in the message, e.g. "amount is required".
# Every validator below starts by calling this function, so the “required” rule is written once.

def categories_for(kind):
    if kind == "expense":
        return EXPENSE_CATEGORIES
    return INCOME_CATEGORIES

#Given a kind, this returns the right dictionary.
# Both the category and subcategory checks need it.
#There’s no else because return already leaves the function. 
# If kind is "expense", we never reach the last line.

#ID 
def validate_id(value):
    text = clean_required(value, "id").upper()
    if not re.fullmatch(r"T\d{3}", text):
        raise ValueError(f"id must look like T001, got '{text}'")
    return text

#DATE
def validate_date(value):
    text = clean_required(value, "date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError(f"date must be YYYY-MM-DD, got '{text}'")
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"date '{text}' does not exist")
    return text

#Shape: the regex requires 4 digits, a dash, 2 digits, a dash, 2 digits. "04/09/2026" fails here.
# Real date: date.fromisoformat() tries to build the date. If the date doesn’t exist (2026-13-40, or 2025-02-29 because 2025 isn’t a leap year), it raises ValueError, which we catch and replace with our own clearer message.
# We return text (a string), not the date object. 
# A string goes straight into the CSV, and comparing "2026-09-04" < "2026-10-01" as strings works correctly for ISO dates, so sorting stays simple.

#KIND 
def validate_kind(value):
    text = clean_required(value, "kind").lower()
    if text not in KINDS:
        raise ValueError(f"kind must be expense or income, got '{text}'")
    return text

#CATEGORY 
def validate_category(kind, value):
    text = clean_required(value, "category").lower()
    allowed = categories_for(kind)
    if text not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValueError(f"category '{text}' is not valid for {kind}. Options: {options}")
    return text

#SUBCATEGORY
def validate_subcategory(kind, category, value):
    text = clean_required(value, "subcategory").lower()
    allowed = categories_for(kind)[category]
    if text not in allowed:
        options = ", ".join(allowed)
        raise ValueError(f"subcategory '{text}' is not valid for {category}. Options: {options}")
    return text

#AMOUNT BOUNDRIES
def validate_amount(value):
    text = clean_required(value, "amount")
    try:
        amount = float(text)
    except ValueError:
        raise ValueError(f"amount must be a number, got '{text}'")
    if not amount > 0:
        raise ValueError(f"amount must be > 0, got {text}")
    if amount > MAX_AMOUNT:
        raise ValueError(f"amount must be at most {MAX_AMOUNT}, got {text}")
    if round(amount, 2) != amount:
        raise ValueError(f"amount can have at most 2 decimals, got {text}")
    return amount

#CURRENCY
def validate_currency(value):
    text = clean_required(value, "currency").upper()
    if text not in CURRENCIES:
        options = ", ".join(sorted(CURRENCIES))
        raise ValueError(f"currency must be one of {options}, got '{text}'")
    return text
