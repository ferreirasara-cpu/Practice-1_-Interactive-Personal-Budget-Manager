"""
services.py - The budget logic.

This file holds the Budget class, which keeps the transactions and the monthly
spending limits, and does everything the menu needs: add, list, filter,
report, limits, import and undo.
It does not ask the user anything and does not print anything: every method
returns a value, so it can be tested with assert.
(Brief: "Service - domain rules and business logic", its own layer.)

What is inside:
- Budget: a class that contains a list of Transaction objects and a
  dictionary of limits (composition, manual 10.4). It is created with the
  path of its CSV file and:
    - loads the transactions (CSV) and the limits (JSON) when it starts.
    - saves after EVERY change (add, import, undo, set or remove a limit),
      so the files on disk always match what the program shows.
  Properties (read-only, manual 10.3):
    - transactions: a copy of the list, so nobody can change it from outside.
    - last_transaction: the last one added, or None.
    - limits: a copy of the limits dictionary.
  Methods:
    - next_id(): the next free id (T001, T002, ...).
    - add(...): creates, validates, saves and returns a new transaction.
    - undo(): removes the last added transaction and saves the file.
    - import_file(path): adds the valid rows of another CSV (with new ids)
      and returns the rejected rows. The other file is only read.
    - list_by_date(): all transactions sorted by date.
    - filter(kind, category, month): transactions that match.
    - currencies() / months(): the currencies and months used.
    - summary(currency, month): total income, total expenses and balance.
    - totals_by_category(currency, month): expenses added up per category.
    - set_limit(category, amount) / remove_limit(category): monthly limits.
    - limit_status(month): spent vs. limit for each category in that month.

Tools used:
- Composition: a Budget HAS transactions and limits (manual 10.4).
- Encapsulation: the data is stored as self._transactions and self._limits
  (the _ means "internal") and shown through properties (manual 10.3).
- A private helper method (_select) so the currency/month rule is written once.
- List, set and generator comprehensions (manual 6.1).
- sorted() with key=lambda, max(default=...), sum(), round() (manual 6.3).
- String methods: .startswith() to match a month, slicing [:7] (manual 5.2, 8.1).
- Dictionary accumulation with .get(key, 0) and dict.pop() (manual 5.5).
- Default parameters and None as "not given" (manual 4.2).

Rules followed:
- Totals are always calculated for ONE currency. Adding euros and dollars
  together would give a wrong number.
- Limits are monthly and in EUR: they are compared with the expenses of
  ONE month, because a budget starts again every month.
- "Last transaction" means the last one added, not the one with the latest
  date. The list keeps the order in which transactions were added, and the
  file is saved in that same order, so undo still works after a restart.
- Importing a file that does not exist raises ValueError with a clear
  message, instead of silently importing 0 transactions.
"""

from pathlib import Path

from budget_manager.models import Transaction
from budget_manager.storage import (
    load_limits,
    load_transactions,
    save_limits,
    save_transactions,
)
from budget_manager.validation import validate_amount, validate_limit_category

# Limits are kept in one currency, so they can be compared with spending.
LIMITS_CURRENCY = "EUR"


class Budget:
    """All the transactions and limits of one budget, and what you can do with them."""

    def __init__(self, path: str | Path, limits_path: str | Path | None = None) -> None:
        # The CSV file where the transactions are saved.
        self.path = path

        # The JSON file for the limits. If none is given, it goes next to the
        # CSV file: data/transactions.csv -> data/limits.json
        # (Path(...).parent is the folder that contains the file, manual 7.2.)
        if limits_path is None:
            limits_path = Path(path).parent / "limits.json"
        self.limits_path = limits_path

        # Load both files. The _ means "internal": other files use the
        # properties below. "rejected" keeps the bad rows to warn the user.
        self._transactions, rejected_rows = load_transactions(path)
        self._limits, rejected_limits = load_limits(limits_path)
        self.rejected = rejected_rows + rejected_limits

    # ------------------------------------------------------------------
    # Read-only properties (manual 10.3)
    # ------------------------------------------------------------------

    @property
    def transactions(self) -> list[Transaction]:
        """A COPY of the list, in the order they were added."""
        # list(...) returns a new list. If someone appends to it, the real
        # budget does not change, so the file and the memory never disagree.
        return list(self._transactions)

    @property
    def last_transaction(self) -> Transaction | None:
        """The last transaction added, or None if there are none."""
        # [-1] is the last item of a list (manual 5.2).
        # Conditional expression: avoids IndexError on an empty list.
        return self._transactions[-1] if self._transactions else None

    @property
    def limits(self) -> dict[str, float]:
        """A COPY of the limits: {category: monthly limit in EUR}."""
        return dict(self._limits)

    # ------------------------------------------------------------------
    # Changes to transactions (each one is saved immediately)
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write all transactions to the CSV file. Called after every change."""
        save_transactions(self.path, self._transactions)

    def next_id(self) -> str:
        """Return the next free id: one more than the biggest id used."""
        # List comprehension: t.id[1:] takes "T007" -> "007" -> int 7.
        numbers = [int(t.id[1:]) for t in self._transactions]

        # max(..., default=0): if the list is empty, start from 0.
        # We use max + 1 (not len + 1) so ids never repeat after an undo
        # or if a row in the middle was removed.
        next_number = max(numbers, default=0) + 1

        # :03d writes the number with 3 digits: 7 -> "007".
        # If we pass T999, validate_id rejects "T1000" with a clear message.
        return f"T{next_number:03d}"

    def add(
        self,
        date: str,
        kind: str,
        category: str,
        subcategory: str,
        amount: str | float,
        currency: str,
    ) -> Transaction:
        """Create, validate, save and return a new transaction."""
        # Creating the Transaction validates everything (models.py).
        # If a value is wrong, ValueError goes up to the menu and nothing
        # is added or saved.
        transaction = Transaction(
            self.next_id(), date, kind, category, subcategory, amount, currency
        )
        self._transactions.append(transaction)

        # Save immediately, so the file always matches the list.
        self.save()
        return transaction

    def undo(self) -> Transaction | None:
        """Remove the last added transaction, save, and return it (or None)."""
        # Nothing to undo: return None so the menu can say so.
        if not self._transactions:
            return None

        # pop() removes and returns the LAST item of the list,
        # which is the last transaction added.
        removed = self._transactions.pop()

        # Save after removing. Undo is not only in memory: the file changes too.
        # (Brief stretch challenge: "undo is not just in-memory deletion".)
        self.save()
        return removed

    def import_file(self, path: str | Path) -> tuple[list[Transaction], list[str]]:
        """Add the valid rows of another CSV. Return (added, rejected)."""
        # load_transactions returns empty lists for a missing file (useful when
        # the program starts for the first time), but for an import a missing
        # file is a mistake, so we say it clearly instead of "Imported 0".
        if not Path(path).exists():
            raise ValueError(f"file '{path}' was not found")

        # Read the other file. It is never written, only read.
        loaded, rejected = load_transactions(path)

        added: list[Transaction] = []
        for t in loaded:
            # Each imported transaction gets a NEW id from this budget,
            # because the ids of the other file could already be used here.
            new = Transaction(
                self.next_id(), t.date, t.kind, t.category,
                t.subcategory, t.amount, t.currency,
            )
            self._transactions.append(new)
            added.append(new)

        # Save once at the end, with all the imported transactions.
        self.save()
        return added, rejected

    # ------------------------------------------------------------------
    # Monthly limits (saved to the JSON file immediately)
    # ------------------------------------------------------------------

    def set_limit(self, category: str, amount: str | float) -> tuple[str, float]:
        """Set (or change) the monthly limit of an expense category."""
        # Same rules as everywhere else: an expense category and a valid amount.
        clean_category = validate_limit_category(category)
        clean_amount = validate_amount(amount)
        self._limits[clean_category] = clean_amount
        save_limits(self.limits_path, self._limits)
        return clean_category, clean_amount

    def remove_limit(self, category: str) -> bool:
        """Remove the limit of a category. Return False if it had none."""
        clean_category = validate_limit_category(category)
        if clean_category not in self._limits:
            return False
        # dict.pop(key) removes the pair (manual 5.5).
        self._limits.pop(clean_category)
        save_limits(self.limits_path, self._limits)
        return True

    # ------------------------------------------------------------------
    # Queries (they only read, they never change anything)
    # ------------------------------------------------------------------

    def _select(self, currency: str | None = None, month: str | None = None) -> list[Transaction]:
        """Internal helper: transactions of one currency and/or one month.

        The _ at the start of the name means "used inside this class only".
        It keeps the currency/month rule in ONE place for every query below.
        """
        return [
            t for t in self._transactions
            if (currency is None or t.currency == currency)
            # "2026-09-04".startswith("2026-09") is True: same month.
            and (month is None or t.date.startswith(month))
        ]

    def list_by_date(self) -> list[Transaction]:
        """All transactions sorted by date (and by id when the date is the same)."""
        # sorted() returns a NEW list and does not change self._transactions,
        # so the "added" order needed by undo is kept.
        # key=lambda t: (t.date, t.id): sorting by a tuple compares the date
        # first and the id only when the dates are equal (manual 6.3).
        return sorted(self._transactions, key=lambda t: (t.date, t.id))

    def filter(
        self,
        kind: str | None = None,
        category: str | None = None,
        month: str | None = None,
    ) -> list[Transaction]:
        """Transactions that match kind, category and month. None = no filter."""
        # List comprehension with a condition (manual 6.1):
        # keep t only if it matches all the conditions that were given.
        return [
            t for t in self.list_by_date()
            if (kind is None or t.kind == kind)
            and (category is None or t.category == category)
            and (month is None or t.date.startswith(month))
        ]

    def currencies(self) -> list[str]:
        """The currencies used, without repeats, in alphabetical order."""
        # A set comprehension {...} removes repeated currencies (manual 6.1),
        # sorted() turns it into an ordered list.
        return sorted({t.currency for t in self._transactions})

    def months(self) -> list[str]:
        """The months that have transactions, like ["2026-09", "2026-10"]."""
        # t.date[:7] takes the first 7 characters: "2026-09-04" -> "2026-09".
        return sorted({t.date[:7] for t in self._transactions})

    def summary(self, currency: str = "EUR", month: str | None = None) -> dict[str, str | float]:
        """Total income, total expenses and balance for ONE currency (and month)."""
        items = self._select(currency, month)

        # Generator expressions inside sum(): add up without building a list.
        income = sum(t.amount for t in items if t.kind == "income")
        expenses = sum(t.amount for t in items if t.kind == "expense")

        # The balance uses the signed_amount property from models.py:
        # income counts as +, expenses as -.
        balance = sum(t.signed_amount for t in items)

        # round(..., 2) avoids results like 0.30000000000000004.
        return {
            "currency": currency,
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "balance": round(balance, 2),
        }

    def totals_by_category(self, currency: str = "EUR", month: str | None = None) -> dict[str, float]:
        """Expenses added up per category, biggest first, for ONE currency (and month)."""
        totals: dict[str, float] = {}
        for t in self._select(currency, month):
            if t.kind == "expense":
                # .get(category, 0): 0 the first time we see the category,
                # then add the amount (the "group / tally" pattern, manual 5.5).
                totals[t.category] = round(totals.get(t.category, 0) + t.amount, 2)

        # .items() gives (category, total) pairs. We sort them by the total
        # (pair[1]), biggest first (reverse=True), and build a dict again.
        return dict(sorted(totals.items(), key=lambda pair: pair[1], reverse=True))

    def limit_status(self, month: str) -> list[dict[str, str | float | bool]]:
        """For each category with a limit: spent, limit, remaining, over or not.

        Spending is counted for ONE month and in EUR only, because the
        limits are monthly and in EUR.
        """
        spent_by_category = self.totals_by_category(LIMITS_CURRENCY, month)

        status = []
        for category, limit in self._limits.items():
            # A category with a limit but no spending this month has spent 0.
            spent = spent_by_category.get(category, 0)
            status.append({
                "category": category,
                "spent": spent,
                "limit": limit,
                "remaining": round(limit - spent, 2),
                "percent": round(spent / limit * 100),
                # Exactly at the limit is NOT over: only more than the limit is.
                "over": spent > limit,
            })

        # The most used limits first, so problems are at the top.
        return sorted(status, key=lambda row: row["percent"], reverse=True)