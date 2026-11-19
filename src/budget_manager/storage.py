"""
storage.py - Reading and writing the CSV files (transactions and limits).

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
- load_limits(path): reads the monthly spending limits from a CSV file and
  returns (limits, rejected), validated like the transactions.
- save_limits(path, limits): writes the limits to the CSV file.

Tools used:
- with open(...) so the file is always closed (manual 7.1).
- csv.DictReader / csv.DictWriter with newline="" (manual 7.3).
- pathlib.Path for paths, .exists() and .mkdir(exist_ok=True) (manual 7.2).
  .parent (the folder of a file) is not in the manual (see AI_DISCLOSURE.md).
- try / except / else inside the loop: the validation loop pattern (manual 7.5).
- enumerate(..., start=2) for spreadsheet-style row numbers (manual 6.2).
- A set to detect repeated ids (manual 5.4).
- Returning two values as a tuple (manual 5.3).
- Only CSV files, as the course asked: transactions and limits are both
  flat tables (manual 7.3).

Rules followed:
- If the file does not exist yet, the program starts with an empty list.
- Duplicate ids are rejected: the first one is kept, the next ones are reported.
- A file without the 7 columns (for example separated by ";") raises ONE
  ValueError for the whole file, instead of one error per row.
- save_transactions only writes valid transactions. Invalid rows are not
  saved, so it must never be used on the sample file, or its invalid rows
  would be lost. The program saves to data/transactions.csv instead.
"""

import csv
from pathlib import Path

from budget_manager.models import FIELDS, Transaction
from budget_manager.validation import validate_amount, validate_limit_category

# The 2 columns of the limits file, in order (like FIELDS for transactions).
LIMIT_FIELDS: list[str] = ["category", "limit"]


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
            # The whole file is wrong if a column is missing, for example a CSV
            # exported from Spanish Excel, which uses ";" instead of ",". Then
            # every row would say "id is required", which does not help, so we
            # stop with ONE clear message instead (list comprehension, manual 6.1;
            # "in" on a dictionary checks its keys, manual 5.5).
            missing = [field for field in FIELDS if field not in row]
            if missing:
                raise ValueError(
                    f"file '{path}' has no column(s) {', '.join(missing)}. "
                    f"The first line must be: {','.join(FIELDS)} (separated by commas)"
                )

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
    # path.parent is the folder that contains the file;
    # exist_ok=True means "no error if it already exists" (manual 7.2).
    path.parent.mkdir(exist_ok=True)

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
    """Read the limits CSV file and return (valid limits, rejected messages).

    The file looks like:
        category,limit
        food,300.00
        home,650.00
    """
    path = Path(path)
    limits: dict[str, float] = {}
    rejected: list[str] = []

    # No file yet: no limits, not an error.
    if not path.exists():
        return limits, rejected

    # Same pattern as load_transactions: DictReader, row numbers, and
    # try / except / else so one bad limit never stops the others (manual 7.5).
    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            # A file without the 2 columns (for example edited by hand with
            # ";") is reported once, and the program still starts.
            missing = [field for field in LIMIT_FIELDS if field not in row]
            if missing:
                rejected.append(f"{path}: the first line must be: {','.join(LIMIT_FIELDS)}")
                return limits, rejected

            # Each limit is validated with the SAME rules as a transaction:
            # an existing expense category and a valid amount.
            try:
                category = validate_limit_category(row.get("category", ""))
                amount = validate_amount(row.get("limit", ""))
                # One limit per category: the first is kept, like repeated ids.
                if category in limits:
                    raise ValueError(f"category {category} is repeated")
            except ValueError as error:
                rejected.append(f"{path}: Row {row_number}: {error}")
            else:
                limits[category] = amount

    return limits, rejected


def save_limits(path: str | Path, limits: dict[str, float]) -> None:
    """Write the limits to the CSV file, replacing its content."""
    path = Path(path)
    path.parent.mkdir(exist_ok=True)   # same as in save_transactions
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=LIMIT_FIELDS)
        writer.writeheader()
        # .items() gives (category, amount) pairs (manual 5.5).
        for category, amount in limits.items():
            writer.writerow({"category": category, "limit": f"{amount:.2f}"})
