"""
models.py - The Transaction class.

A Transaction is one income or expense. When it is created, it checks all
its fields using the functions in validation.py, so an invalid transaction
can never exist in the program (its "invariants" always hold, manual 10.2).

What is inside:
- FIELDS: the 7 field names in the order used in the CSV file.
- Transaction: the class, with:
    - __init__: validates and saves the 7 fields
      (kind, then category, then subcategory, because each depends on the one before).
    - from_dict(): builds a Transaction from a dictionary, like a CSV row.
    - to_dict(): turns a Transaction back into a dictionary to save it.
    - signed_amount: a read-only property, negative for expenses and
      positive for income, used to calculate the balance.
    - __str__: how a transaction looks when printed.
    - __repr__: how it looks when debugging.

Tools used:
- A class that bundles data (attributes) and behavior (methods) (manual 10.1).
- __init__ that checks the rules before assigning (manual 10.2).
- @classmethod as an alternate constructor for CSV rows (manual 11.3).
- @property for a computed, read-only value (manual 10.3).
- __str__ / __repr__ to control how the object is shown.
- f-string format specs like :.2f and :<8 (manual 8.2).
- Type hints on every method (manual 4.1).
"""

from budget_manager.validation import (
    validate_amount,
    validate_category,
    validate_currency,
    validate_date,
    validate_id,
    validate_kind,
    validate_subcategory,
)

# The 7 fields in the order they appear in the CSV file.
# storage.py uses this list as the header of the file, so the column order
# is defined in ONE place.
FIELDS: list[str] = ["id", "date", "kind", "category", "subcategory", "amount", "currency"]


class Transaction:
    """One income or expense. Always valid: invalid data raises ValueError."""

    def __init__(
        self,
        id: str,
        date: str,
        kind: str,
        category: str,
        subcategory: str,
        amount: str | float,
        currency: str,
    ) -> None:
        # Each line validates one field and saves the CLEAN value on the object.
        # If any value is wrong, validate_... raises ValueError and the object
        # is never created.
        self.id = validate_id(id)
        self.date = validate_date(date)

        # The order matters here:
        # 1. kind first, because the category depends on it (income or expense list).
        # 2. category second, because the subcategory depends on it.
        # 3. subcategory last. If we checked it before the category, an unknown
        #    category like "gym" would crash with KeyError instead of a clear message.
        self.kind = validate_kind(kind)
        self.category = validate_category(self.kind, category)
        self.subcategory = validate_subcategory(self.kind, self.category, subcategory)

        # validate_amount turns the text "18.50" into the number 18.5.
        self.amount = validate_amount(amount)
        self.currency = validate_currency(currency)

    # @classmethod: an alternate way to build a Transaction (manual 11.3).
    # It receives a dictionary, like the rows that csv.DictReader gives us.
    # "cls" means "this class", so it also works for a future subclass.
    @classmethod
    def from_dict(cls, row: dict[str, str]) -> "Transaction":
        """Build a Transaction from a dictionary such as a CSV row."""
        # row.get(field, "") returns "" if a column is missing in the file,
        # so __init__ reports "category is required" instead of crashing with KeyError.
        return cls(
            row.get("id", ""),
            row.get("date", ""),
            row.get("kind", ""),
            row.get("category", ""),
            row.get("subcategory", ""),
            row.get("amount", ""),
            row.get("currency", ""),
        )

    def to_dict(self) -> dict[str, str]:
        """Turn the transaction back into a dictionary, ready for csv.DictWriter."""
        return {
            "id": self.id,
            "date": self.date,
            "kind": self.kind,
            "category": self.category,
            "subcategory": self.subcategory,
            # :.2f writes 18.5 as "18.50", so the file always has 2 decimals.
            "amount": f"{self.amount:.2f}",
            "currency": self.currency,
        }

    # @property: read it like an attribute (t.signed_amount, no brackets),
    # but it is calculated every time. There is no setter, so it cannot be
    # changed from outside (manual 10.3).
    @property
    def signed_amount(self) -> float:
        """The amount with a sign: negative for expenses, positive for income."""
        if self.kind == "expense":
            return -self.amount
        return self.amount

    def __str__(self) -> str:
        """One readable line, used by print(transaction)."""
        # Conditional expression: one value or the other in a single line.
        sign = "-" if self.kind == "expense" else "+"
        # :<8 pads the text to 8 characters (left aligned) so columns line up.
        # :>10.2f aligns the number to the right with 2 decimals.
        return (
            f"{self.id}  {self.date}  {self.kind:<8}  "
            f"{self.category + ' / ' + self.subcategory:<28}"
            f"{sign}{self.amount:>10.2f} {self.currency}"
        )

    def __repr__(self) -> str:
        """Short technical view, shown when debugging or printing a list."""
        return f"Transaction({self.id}, {self.kind}, {self.category}, {self.amount})"