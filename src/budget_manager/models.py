"""
models.py - The Transaction class.

A Transaction is one income or expense. When it is created, it checks all
its fields using the functions in validation.py, so an invalid transaction
can never exist in the program.

What is inside:
- FIELDS: the 7 field names in the order used in the CSV file.
- Transaction: the class, with:
    - __init__: validates and saves the 7 fields
      (kind, then category, then subcategory, because each depends on the one before).
    - from_dict(): builds a Transaction from a dictionary, like a CSV row.
    - to_dict(): turns a Transaction back into a dictionary to save it.
    - signed_amount(): returns the amount as negative for expenses and
      positive for income, to calculate the balance.
    - __str__: how a transaction looks when printed in the menu.
    - __repr__: how it looks when debugging.
"""

# We import the rules from validation.py, so each rule is written only once.
from budget_manager.validation import (
    validate_id,
    validate_date,
    validate_kind,
    validate_category,
    validate_subcategory,
    validate_amount,
    validate_currency,
)

# The 7 fields in the order they appear in the CSV file.
# storage.py uses this list as the header of the file.
FIELDS = ["id", "date", "kind", "category", "subcategory", "amount", "currency"]


class Transaction:
    # __init__ runs every time we create a Transaction(...).
    # It receives the raw values (they can be strings with spaces or capitals).
    def __init__(self, id, date, kind, category, subcategory, amount, currency):
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
    # It receives a dictionary, like the rows that csv.DictReader gives us,
    # and passes each value to __init__. "cls" means "this class".
    @classmethod
    def from_dict(cls, row):
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

    # The opposite of from_dict: turns the object back into a dictionary.
    # csv.DictWriter in storage.py needs a dictionary to write one row.
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "kind": self.kind,
            "category": self.category,
            "subcategory": self.subcategory,
            # f"{...:.2f}" writes 18.5 as "18.50", so the file always has 2 decimals.
            "amount": f"{self.amount:.2f}",
            "currency": self.currency,
        }

    # signed_amount: expenses count as negative, income as positive.
    # services.py uses it to calculate the balance with a simple sum().
    def signed_amount(self):
        if self.kind == "expense":
            return -self.amount
        return self.amount

    # __str__ decides what print(transaction) shows.
    # Used by the menu to list transactions in one readable line.
    def __str__(self):
        # Expenses show a "-" sign and income a "+" sign.
        sign = "-" if self.kind == "expense" else "+"
        # :<8 and :<30 pad the text with spaces so the columns line up.
        # :>10.2f aligns the number to the right with 2 decimals.
        return (
            f"{self.id}  {self.date}  {self.kind:<8}  "
            f"{self.category + ' / ' + self.subcategory:<30}"
            f"{sign}{self.amount:>10.2f} {self.currency}"
        )

    # __repr__ is what Python shows when you look at the object in a list
    # or in the terminal. Useful when debugging.
    def __repr__(self):
        return f"Transaction({self.id}, {self.kind}, {self.category}, {self.amount})"