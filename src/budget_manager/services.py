"""
services.py - The budget logic.

This file holds the Budget class, which keeps the list of transactions and
does everything the menu needs: add, list, filter, report, import and undo.
It does not ask the user anything and does not print anything: every method
returns a value, so it can be tested with assert.

What is inside:
- Budget: a class that contains a list of Transaction objects (composition,
  manual 10.4). It is created with the path of its CSV file and:
    - loads the file when it starts.
    - saves the file after EVERY change (add, import, undo), so the file on
      disk always matches what the program shows, even if it closes suddenly.
  Methods:
    - next_id(): the next free id (T001, T002, ...).
    - add(...): creates, validates, saves and returns a new transaction.
    - undo(): removes the last added transaction and saves the file.
    - import_file(path): adds the valid rows of another CSV (with new ids)
      and returns the rejected rows. The other file is only read.
    - list_by_date(): all transactions sorted by date.
    - filter(kind, category): transactions that match.
    - currencies(): the currencies used.
    - summary(currency): total income, total expenses and balance.
    - totals_by_category(currency): expenses added up per category.

Rules followed:
- Totals are always calculated for ONE currency. Adding euros and dollars
  together would give a wrong number.
- "Last transaction" means the last one added, not the one with the latest
  date. The list keeps the order in which transactions were added, and the
  file is saved in that same order, so undo still works after a restart.
- Importing a file that does not exist raises ValueError with a clear
  message, instead of silently importing 0 transactions.
"""

from pathlib import Path

from budget_manager.models import Transaction
from budget_manager.storage import load_transactions, save_transactions


class Budget:
    def __init__(self, path):
        # The file where this budget is saved.
        self.path = path

        # Load the file. "rejected" keeps the bad rows so the menu can show
        # them to the user when the program starts.
        self.transactions, self.rejected = load_transactions(path)

    def save(self):
        # Writes the whole list to the file. Called after every change.
        save_transactions(self.path, self.transactions)

    def next_id(self):
        # t.id[1:] takes "T007" and removes the "T" -> "007" -> int 7.
        numbers = [int(t.id[1:]) for t in self.transactions]

        # max(..., default=0): if the list is empty, start from 0.
        # We use max + 1 (not len + 1) so ids never repeat after an undo
        # or if a row in the middle was removed.
        next_number = max(numbers, default=0) + 1

        # :03d writes the number with 3 digits: 7 -> "007".
        # If we pass T999, validate_id rejects "T1000" with a clear message.
        return f"T{next_number:03d}"

    def add(self, date, kind, category, subcategory, amount, currency):
        # Creating the Transaction validates everything (models.py).
        # If a value is wrong, ValueError goes up to the menu and nothing
        # is added or saved.
        transaction = Transaction(
            self.next_id(), date, kind, category, subcategory, amount, currency
        )
        self.transactions.append(transaction)

        # Save immediately, so the file always matches the list.
        self.save()
        return transaction

    def undo(self):
        # Nothing to undo: return None so the menu can say so.
        if not self.transactions:
            return None

        # pop() removes and returns the LAST item of the list,
        # which is the last transaction added.
        removed = self.transactions.pop()

        # Save after removing. Undo is not only in memory: the file changes too.
        self.save()
        return removed

    def import_file(self, path):
        # load_transactions returns empty lists for a missing file (useful when
        # the program starts for the first time), but for an import a missing
        # file is a mistake, so we say it clearly instead of "Imported 0".
        if not Path(path).exists():
            raise ValueError(f"file '{path}' was not found")

        # Read the other file. It is never written, only read.
        loaded, rejected = load_transactions(path)

        added = []
        for t in loaded:
            # Each imported transaction gets a NEW id from this budget,
            # because the ids of the other file could already be used here.
            new = Transaction(
                self.next_id(), t.date, t.kind, t.category,
                t.subcategory, t.amount, t.currency,
            )
            self.transactions.append(new)
            added.append(new)

        # Save once at the end, with all the imported transactions.
        self.save()
        return added, rejected

    def list_by_date(self):
        # sorted() returns a NEW list and does not change self.transactions,
        # so the "added" order needed by undo is kept.
        # key=lambda t: (t.date, t.id): sort by date, and by id if the date is the same.
        return sorted(self.transactions, key=lambda t: (t.date, t.id))

    def filter(self, kind=None, category=None):
        # None means "do not filter by this".
        # List comprehension (manual 6.1): keep t only if it matches both conditions.
        return [
            t for t in self.list_by_date()
            if (kind is None or t.kind == kind)
            and (category is None or t.category == category)
        ]

    def currencies(self):
        # A set comprehension removes repeated currencies, sorted() orders them.
        return sorted({t.currency for t in self.transactions})

    def summary(self, currency="EUR"):
        # Only the transactions in this currency.
        items = [t for t in self.transactions if t.currency == currency]

        income = sum(t.amount for t in items if t.kind == "income")
        expenses = sum(t.amount for t in items if t.kind == "expense")

        # round(..., 2) avoids results like 0.30000000000000004.
        return {
            "currency": currency,
            "income": round(income, 2),
            "expenses": round(expenses, 2),
            "balance": round(income - expenses, 2),
        }

    def totals_by_category(self, currency="EUR"):
        totals = {}
        for t in self.transactions:
            if t.kind == "expense" and t.currency == currency:
                # .get(category, 0): 0 the first time we see the category,
                # then add the amount (manual 5.5).
                totals[t.category] = round(totals.get(t.category, 0) + t.amount, 2)

        # Return the categories from biggest to smallest expense.
        # reverse=True means descending order.
        return dict(sorted(totals.items(), key=lambda pair: pair[1], reverse=True))