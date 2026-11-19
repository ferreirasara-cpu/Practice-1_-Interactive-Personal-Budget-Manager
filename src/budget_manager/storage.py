"""
storage.py - Reading and writing the CSV file.

This file is the only place that touches the disk. It does not ask the user
anything and does not print anything: it loads rows, turns them into
Transaction objects, and saves them back.

What is inside:
- load_transactions(path): reads the CSV and returns two lists:
    - accepted: the valid Transaction objects.
    - rejected: the invalid rows, as messages with the row number,
      for example "Row 4: amount must be > 0, got -5".
  One bad row never stops the rest of the file from loading.
- save_transactions(path, transactions): writes all transactions to the CSV,
  replacing the old content, so the file always matches the program.

Rules followed:
- save_transactions only writes valid transactions. Invalid rows are not
  saved, so it must never be used on the sample file, or its invalid rows
  would be lost. The program saves to data/transactions.csv instead.
"""

import csv
from pathlib import Path

from budget_manager.models import FIELDS, Transaction


def load_transactions(path):
    # Path() turns the text "data/sample.csv" into a path object (manual 7.2).
    path = Path(path)

    # The two lists we will return.
    accepted = []
    rejected = []

    # If the file does not exist (first time using the program),
    # we return two empty lists instead of crashing.
    if not path.exists():
        return accepted, rejected

    # A set to remember the ids we have already accepted.
    # A set is used because we only ask "have I seen this id?" (manual 5.4).
    seen_ids = set()

    # "with" closes the file automatically when the block ends.
    # newline="" lets the csv module control line endings (manual 7.3).
    # encoding="utf-8" avoids problems with accents or symbols like €.
    with open(path, newline="", encoding="utf-8") as file:
        # DictReader turns each row into a dictionary using the header,
        # for example {"id": "T001", "amount": "18.50", ...}.
        # All values arrive as strings.
        reader = csv.DictReader(file)

        # enumerate(..., start=2): row 1 is the header,
        # so the first data row is row 2, like in Excel.
        for row_number, row in enumerate(reader, start=2):
            try:
                # from_dict validates every field (see models.py).
                # If something is wrong, it raises ValueError.
                transaction = Transaction.from_dict(row)

                # Uniqueness can only be checked here, because only the loader
                # sees all the rows together.
                if transaction.id in seen_ids:
                    raise ValueError(f"id {transaction.id} is repeated")

            except ValueError as error:
                # We add the row number to the message so the user can find it.
                rejected.append(f"Row {row_number}: {error}")

            else:
                # "else" runs only when there was no error (manual 3.2).
                accepted.append(transaction)
                seen_ids.add(transaction.id)

    return accepted, rejected


def save_transactions(path, transactions):
    path = Path(path)

    # Creates the folder (for example "data/") if it does not exist yet.
    # parents=True creates any missing parent folders,
    # exist_ok=True means "no error if it already exists".
    path.parent.mkdir(parents=True, exist_ok=True)

    # "w" mode erases the old file and writes it again from zero.
    # We always write ALL the transactions, so the file is a full copy
    # of what the program has in memory (this is what makes undo safe).
    with open(path, "w", newline="", encoding="utf-8") as file:
        # DictWriter writes dictionaries as rows, using FIELDS as the columns.
        writer = csv.DictWriter(file, fieldnames=FIELDS)

        # The first line of the file: id,date,kind,...
        writer.writeheader()

        # One row per transaction. to_dict() gives the dictionary
        # that DictWriter needs (see models.py).
        for transaction in transactions:
            writer.writerow(transaction.to_dict())