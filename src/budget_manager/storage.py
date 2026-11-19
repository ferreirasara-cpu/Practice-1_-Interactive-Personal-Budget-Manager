"""
storage.py - Reading and writing the files (CSV for transactions, JSON for limits).

This file is the only place that touches the disk. It does not ask the user
anything and does not print anything: it loads rows, turns them into
Transaction objects, and saves them back.
(Brief: "Storage - persistence and file I/O", its own layer.)

What is inside:
- load_transactions(path): reads the CSV and returns two lists:
    - accepted: the valid Transaction objects.
    - rejected: the invalid rows, as messages with the row number,
      for example "Row 6: amount must be > 0, got -5".
  One bad row never stops the rest of the file from loading.
- save_transactions(path, transactions): writes all transactions to the CSV,
  replacing the old content, so the file always matches the program.
- load_limits(path): reads the monthly spending limits from a JSON file and
  returns (limits, rejected), validated like the transactions.
- save_limits(path, limits): writes the limits to the JSON file.

Tools used:
- with open(...) so the file is always closed (manual 7.1).
- csv.DictReader / csv.DictWriter with newline="" (manual 7.3).
- pathlib.Path for paths, .exists() and .mkdir() (manual 7.2).
- try / except / else inside the loop: the validation loop pattern (manual 7.5).
- enumerate(..., start=2) for spreadsheet-style row numbers (manual 6.2).
- A set to detect repeated ids (manual 5.4).
- Returning two values as a tuple (manual 5.3).
- json.load / json.dump for the limits (manual 7.4). JSON is used because
  the limits are a dictionary of settings, not a table of records
  (manual 7.4: "CSV: flat tables... JSON: nested data, settings").

Rules followed:
- If the file does not exist yet, the program starts with an empty list.
- Duplicate ids are rejected: the first one is kept, the next ones are reported.
- save_transactions only writes valid transactions. Invalid rows are not
  saved, so it must never be used on the sample file, or its invalid rows
  would be lost. The program saves to data/transactions.csv instead.
"""

import csv
import json
from pathlib import Path

from budget_manager.models import FIELDS, Transaction
from budget_manager.validation import validate_amount, validate_limit_category


def load_transactions(path: str | Path) -> tuple[list[Transaction], list[str]]:
    """Read a CSV file and return (accepted transactions, rejected messages)."""
    # Path() turns the text "data/sample.csv" into a path object (manual 7.2).
    path = Path(path)

    # The two lists we will return.
    accepted: list[Transaction] = []
    rejected: list[str] = []

    # If the file does not exist (first time using the program),
    # we return two empty lists instead of crashing.
    if not path.exists():
        return accepted, rejected

    # A set to remember the ids we have already accepted.
    # A set is used because we only ask "have I seen this id?" (manual 5.4).
    seen_ids: set[str] = set()

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
                # We add the row number so the user can find and fix the row.
                # (Brief: "Row 4: amount must be > 0." - specific and locatable.)
                rejected.append(f"Row {row_number}: {error}")

            else:
                # "else" runs only when there was no error (manual 3.2).
                accepted.append(transaction)
                seen_ids.add(transaction.id)

    # Two values returned together as a tuple; the caller unpacks them:
    # accepted, rejected = load_transactions(...)
    return accepted, rejected


def save_transactions(path: str | Path, transactions: list[Transaction]) -> None:
    """Write all transactions to the CSV file, replacing its content."""
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
        # (Manual 7.3 trap: forgetting writeheader() on a new CSV.)
        writer.writeheader()

        # One row per transaction. to_dict() gives the dictionary
        # that DictWriter needs (see models.py).
        for transaction in transactions:
            writer.writerow(transaction.to_dict())


def load_limits(path: str | Path) -> tuple[dict[str, float], list[str]]:
    """Read the limits JSON file and return (valid limits, rejected messages).

    The file looks like: {"food": 300.0, "home": 650.0}
    """
    path = Path(path)
    limits: dict[str, float] = {}
    rejected: list[str] = []

    # No file yet: no limits, not an error.
    if not path.exists():
        return limits, rejected

    with open(path, encoding="utf-8") as file:
        try:
            # json.load turns the text of the file into Python objects (manual 7.4).
            data = json.load(file)
        except ValueError:
            # A broken JSON file (for example, edited by hand with a missing
            # comma) raises an error that is a kind of ValueError.
            rejected.append(f"{path.name}: the file is not valid JSON")
            return limits, rejected

    # The file must contain a dictionary {category: amount}.
    # isinstance(x, dict) asks "is x a dictionary?" (types, manual 1.3).
    if not isinstance(data, dict):
        rejected.append(f"{path.name}: expected {{category: amount}}")
        return limits, rejected

    # Each limit is validated with the SAME rules as a transaction:
    # an existing expense category and a valid amount.
    for category, amount in data.items():
        try:
            clean_category = validate_limit_category(category)
            clean_amount = validate_amount(amount)
        except ValueError as error:
            rejected.append(f"{path.name}: '{category}': {error}")
        else:
            limits[clean_category] = clean_amount

    return limits, rejected


def save_limits(path: str | Path, limits: dict[str, float]) -> None:
    """Write the limits to the JSON file, replacing its content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        # indent=2 writes one limit per line, so the file is easy to read.
        json.dump(limits, file, indent=2)
