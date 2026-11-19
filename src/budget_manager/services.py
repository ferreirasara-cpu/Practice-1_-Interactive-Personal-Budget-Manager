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
    - category_shares(currency, month): the % of expenses of each category.
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
- Default parameters, and None as "no filter" (manual 4.2).
- Conditional expressions (manual 2.1).

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
- Importing the same transactions twice does not count them twice: a row
  identical to one already in the budget is reported and not imported.
- Ids stop at T999: adding or importing past it raises ValueError with a
  clear message, and an import that does not fit adds nothing.
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

# Where the monthly limits are saved, unless another file is given.
LIMITS_FILE = "data/limits.json"


class Budget:
    """All the transactions and limits of one budget, and what you can do with them."""

    def __init__(self, path: str | Path, limits_path: str | Path = LIMITS_FILE) -> None:
        """Load the transactions (CSV) and the limits (JSON) of one budget."""
        # The CSV file where the transactions are saved.
        self.path = path

        # The JSON file for the limits. A default parameter (manual 4.2):
        # the program uses data/limits.json, the tests pass their own file.
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

    def _biggest_id_number(self) -> int:
        """Internal helper: the number of the biggest id used, or 0 if there are none."""
        # List comprehension: t.id[1:] takes "T007" -> "007" -> int 7.
        numbers = [int(t.id[1:]) for t in self._transactions]
        # Conditional expression (manual 2.1): max() of an empty list would
        # raise ValueError, so an empty budget starts from 0.
        return max(numbers) if numbers else 0

    def _content(self, t: Transaction) -> tuple[str, str, str, str, float, str]:
        """Internal helper: everything about a transaction except its id, as a tuple."""
        return (t.date, t.kind, t.category, t.subcategory, t.amount, t.currency)

    def next_id(self) -> str:
        """Return the next free id: one more than the biggest id used."""
        # We use the biggest + 1 (not len + 1) so ids never repeat after an
        # undo or if a row in the middle was removed.
        next_number = self._biggest_id_number() + 1

        # Ids have 3 digits, so T999 is the last one (see README, Known limitations).
        if next_number > 999:
            raise ValueError("the file is full: ids only go up to T999")

        # :03d writes the number with 3 digits: 7 -> "007".
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
        # .is_file() is False for a missing path AND for a folder like "data",
        # which open() could not read (it would crash with IsADirectoryError).
        # Note: .is_file() is not in the course manual (see AI_DISCLOSURE.md).
        if not Path(path).is_file():
            raise ValueError(f"file '{path}' was not found")

        # Read the other file. It is never written, only read.
        loaded, rejected = load_transactions(path)

        # Duplicate policy: importing the same file twice must not count every
        # transaction twice. A row identical to a transaction ALREADY in the
        # budget (same date, kind, category, subcategory, amount and currency)
        # is not imported, and it is reported. A tuple is a fixed record, so it
        # can be stored in a set (manual 5.3, 5.4): "in" then answers instantly.
        # The set is built BEFORE the loop, so two identical rows inside the
        # same file (two coffees on the same day) are both imported.
        existing = {self._content(t) for t in self._transactions}
        new_rows: list[Transaction] = []
        for t in loaded:
            if self._content(t) in existing:
                rejected.append(
                    f"id {t.id} ({t.date}, {t.category}, {t.amount:.2f} {t.currency}): "
                    f"already in your budget, not imported again"
                )
            else:
                new_rows.append(t)

        # Check the space BEFORE adding anything, so an import that does not
        # fit adds nothing at all, instead of only half of the file.
        if self._biggest_id_number() + len(new_rows) > 999:
            raise ValueError(
                f"not enough space for {len(new_rows)} transaction(s): ids only go up to T999"
            )

        added: list[Transaction] = []
        for t in new_rows:
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

    def category_shares(self, currency: str = "EUR", month: str | None = None) -> dict[str, float]:
        """The percentage of all expenses that each category represents (1 decimal)."""
        totals = self.totals_by_category(currency, month)
        all_expenses = sum(totals.values())
        # Dictionary comprehension (manual 6.1), same order as totals (biggest first).
        # With no expenses the dictionary is empty, so we never divide by 0.
        return {
            category: round(total / all_expenses * 100, 1)
            for category, total in totals.items()
        }

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