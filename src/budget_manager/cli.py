"""
cli.py - The menu the user sees.

This is the only file that uses input() and print(). It asks the user for
values, calls the Budget class (services.py) to do the work, and shows the
results. It does not calculate anything and does not touch the file itself.

What is inside:
- DATA_FILE, SAMPLE_FILE: the two file paths the program uses.
- ask_until_valid(): asks the same question again until the answer is valid.
- show_transactions(): prints a list of transactions as a table.
- One function per menu option: add, list, filter, report, import, undo.
- main(): reads the --file option with argparse and runs the menu loop.

How to run:
    uv run python -m budget_manager.cli
    uv run python -m budget_manager.cli --file data/other.csv

Rules followed:
- The program always saves to its own file (data/transactions.csv by default).
  The sample file is only read (imported), never written, so its invalid rows
  stay there for testing.
- Every change is saved immediately by Budget, so closing the program at any
  moment (even with Ctrl+C) never loses data.
"""

import argparse

from budget_manager.services import Budget
from budget_manager.validation import (
    CURRENCIES,
    KINDS,
    categories_for,
    validate_amount,
    validate_category,
    validate_currency,
    validate_date,
    validate_kind,
    validate_subcategory,
)

# The program always saves to its own file. The sample file is only read
# (imported), never written, so its invalid rows stay there for testing.
DATA_FILE = "data/transactions.csv"
SAMPLE_FILE = "data/sample_transactions.csv"

MENU = """
===== Personal Budget Manager =====
1. Add a transaction
2. List all transactions
3. Filter transactions
4. Report
5. Import a CSV file
6. Undo last transaction
0. Exit
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ask_until_valid(prompt, check):
    # The validation loop from manual 3.3: keep asking until the value is valid.
    # "check" is one of the validate_... functions. It returns the clean value
    # or raises ValueError with the reason.
    while True:
        answer = input(prompt)
        try:
            return check(answer)
        except ValueError as error:
            # Show the reason and ask again. The program never crashes here.
            print(f"  Error: {error}. Try again.")


def show_transactions(transactions):
    # An empty list would print nothing, which looks like a bug. Say it clearly.
    if not transactions:
        print("No transactions to show.")
        return
    # Each transaction prints itself using __str__ (models.py).
    for t in transactions:
        print(t)
    print(f"({len(transactions)} transactions)")


# ---------------------------------------------------------------------------
# One function per menu option
# ---------------------------------------------------------------------------

def add_transaction(budget):
    print("\nNew transaction")

    # Each field is checked as soon as it is typed, so the user can fix it
    # right away instead of typing everything again.
    date = ask_until_valid("Date (YYYY-MM-DD): ", validate_date)
    kind = ask_until_valid(f"Kind ({' / '.join(sorted(KINDS))}): ", validate_kind)

    # Show only the categories that are valid for this kind.
    categories = categories_for(kind)
    print("  Categories:", ", ".join(categories))
    # lambda: validate_category needs the kind too, so we wrap it in a small
    # function that only receives the answer.
    category = ask_until_valid("Category: ", lambda text: validate_category(kind, text))

    print("  Subcategories:", ", ".join(categories[category]))
    subcategory = ask_until_valid(
        "Subcategory: ", lambda text: validate_subcategory(kind, category, text)
    )

    amount = ask_until_valid("Amount (e.g. 18.50): ", validate_amount)
    currency = ask_until_valid(
        f"Currency ({', '.join(sorted(CURRENCIES))}): ", validate_currency
    )

    # Budget.add creates the Transaction (which checks everything again),
    # gives it an id, and saves the file.
    transaction = budget.add(date, kind, category, subcategory, amount, currency)
    print(f"Saved: {transaction}")


def list_transactions(budget):
    print("\nAll transactions (by date)")
    show_transactions(budget.list_by_date())


def filter_transactions(budget):
    print("\nFilter (press Enter to skip a filter)")

    # .strip().lower() cleans the answer. An empty answer means "no filter",
    # so we turn "" into None, which is what Budget.filter expects.
    kind = input("Kind (expense / income): ").strip().lower() or None
    category = input("Category: ").strip().lower() or None

    show_transactions(budget.filter(kind=kind, category=category))


def show_report(budget):
    currencies = budget.currencies()
    if not currencies:
        print("\nNo transactions yet, nothing to report.")
        return

    # One report per currency, because euros and dollars cannot be added together.
    for currency in currencies:
        summary = budget.summary(currency)
        print(f"\n--- Report in {currency} ---")
        # :>10.2f aligns the numbers to the right with 2 decimals.
        print(f"Income:   {summary['income']:>10.2f}")
        print(f"Expenses: {summary['expenses']:>10.2f}")
        print(f"Balance:  {summary['balance']:>10.2f}")

        totals = budget.totals_by_category(currency)
        if totals:
            print("Expenses by category:")
            for category, total in totals.items():
                # Percentage of all expenses in this currency.
                share = total / summary["expenses"] * 100
                print(f"  {category:<12} {total:>10.2f}  ({share:.0f}%)")


def import_transactions(budget):
    path = input(f"File to import (Enter for {SAMPLE_FILE}): ").strip() or SAMPLE_FILE
    try:
        added, rejected = budget.import_file(path)
    except ValueError as error:
        # For example, the file name was typed wrong.
        print(f"Error: {error}")
        return

    print(f"\nImported {len(added)} transactions.")
    if rejected:
        # Never ignore bad rows silently: show every one with its reason.
        print(f"{len(rejected)} rows were rejected:")
        for message in rejected:
            print(f"  {message}")


def undo_last(budget):
    if not budget.transactions:
        print("\nNothing to undo.")
        return

    # Show what will be removed and ask before deleting.
    last = budget.transactions[-1]
    print(f"\nLast transaction added: {last}")
    answer = input("Remove it? (y/n): ").strip().lower()
    if answer == "y":
        removed = budget.undo()
        print(f"Removed: {removed}")
    else:
        print("Nothing was removed.")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def main():
    # argparse reads options written after the command (manual 9.3),
    # for example: uv run python -m budget_manager.cli --file data/test.csv
    parser = argparse.ArgumentParser(description="Personal budget manager")
    parser.add_argument(
        "--file", default=DATA_FILE, help=f"CSV file to use (default: {DATA_FILE})"
    )
    args = parser.parse_args()

    budget = Budget(args.file)
    print(f"Using file: {args.file} ({len(budget.transactions)} transactions loaded)")

    # If the working file has bad rows (for example, edited by hand), warn the user.
    if budget.rejected:
        print("Warning: some rows in the file are invalid and were skipped:")
        for message in budget.rejected:
            print(f"  {message}")

    # A dictionary that links each menu option to its function.
    # This replaces a long chain of if / elif.
    actions = {
        "1": add_transaction,
        "2": list_transactions,
        "3": filter_transactions,
        "4": show_report,
        "5": import_transactions,
        "6": undo_last,
    }

    # The menu loop: repeat until the user chooses 0.
    try:
        while True:
            print(MENU)
            choice = input("Choose an option: ").strip()
            if choice == "0":
                print("Goodbye!")
                break
            if choice in actions:
                actions[choice](budget)
            else:
                print("Unknown option, please choose a number from the menu.")
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C or Ctrl+D: exit cleanly. Nothing is lost, because every
        # change was already saved to the file.
        print("\nGoodbye! (all changes were already saved)")


# Runs main() only when this file is started directly,
# not when it is imported (for example, by the tests).
if __name__ == "__main__":
    main()