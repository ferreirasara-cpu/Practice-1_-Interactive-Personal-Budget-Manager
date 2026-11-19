"""
cli.py - The menu the user sees.

This is the only file that uses input() and print(). It asks the user for
values, calls the Budget class (services.py) to do the work, and shows the
results. It does not calculate anything and does not touch the file itself.
(Brief: "CLI - input/output and user prompts", kept free of business logic.)

What is inside:
- DATA_FILE, SAMPLE_FILE: the two file paths the program uses.
- Display helpers: title(), section(), success(), error(), bar(), pause(),
  show_table() - they only decide how things look.
- Input helpers: ask_until_valid() and optional().
- One function per menu option: add, list, filter, report, limits,
  import, undo.
- main(): reads the --file option with argparse and runs the menu loop.

Tools used:
- The menu loop: while True + input() + break (manual 2.3, 4.3).
- The validation loop: while True + try / except, ask again on error (manual 3.3).
- A dictionary that maps menu options to functions, instead of a long
  if / elif chain (manual 4.3: functions can be stored in a dict).
- lambda to adapt a validator that needs extra arguments (manual 6.3).
- f-string alignment and widths (:<10, :>12, :,.2f) and .center() (manual 8.2).
- String repetition ("─" * 60) to draw lines and bars.
- argparse for the --file option (manual 9.3).
- if __name__ == "__main__": so importing the file does not start the menu.

How to run:
    uv run budget
    uv run python -m budget_manager.cli --file data/other.csv

Rules followed:
- The program always saves to its own file (data/transactions.csv by default).
  The sample file is only read (imported), never written, so its invalid rows
  stay there for testing.
- Reports and filters can be for one month (YYYY-MM) or for all time.
  Limits are only compared with ONE month, because budgets are monthly.
- Every change is saved immediately by Budget, so closing the program at any
  moment (even with Ctrl+C) never loses data.
- Wrong input is never ignored: it is explained and asked again.
"""

import argparse

from budget_manager.models import Transaction
from budget_manager.services import Budget
from budget_manager.validation import (
    CURRENCIES,
    KINDS,
    categories_for,
    validate_amount,
    validate_any_category,
    validate_category,
    validate_currency,
    validate_date,
    validate_kind,
    validate_limit_category,
    validate_month,
    validate_subcategory,
)

# The program always saves to its own file. The sample file is only read
# (imported), never written, so its invalid rows stay there for testing.
DATA_FILE = "data/transactions.csv"
SAMPLE_FILE = "data/sample_transactions.csv"

# Width of the screen "frame". One constant, so the whole look can be
# changed in one place.
WIDTH = 72

MENU_OPTIONS = [
    ("1", "Add a transaction"),
    ("2", "List all transactions"),
    ("3", "Filter transactions"),
    ("4", "Report"),
    ("5", "Monthly spending limits"),
    ("6", "Import a CSV file"),
    ("7", "Undo last transaction"),
    ("0", "Exit"),
]


# ---------------------------------------------------------------------------
# Display helpers: they only decide how things look
# ---------------------------------------------------------------------------

def title(text: str) -> None:
    """A big title between double lines."""
    # "═" * WIDTH repeats the character WIDTH times.
    # .center(WIDTH) adds spaces on both sides so the text is in the middle.
    print()
    print("═" * WIDTH)
    print(text.upper().center(WIDTH))
    print("═" * WIDTH)


def section(text: str) -> None:
    """A smaller heading, underlined to the length of the text."""
    print()
    print(f"  {text}")
    print("  " + "─" * len(text))


def success(text: str) -> None:
    print(f"  ✔ {text}")


def error(text: str) -> None:
    print(f"  ✖ {text}")


def bar(percent: float, width: int = 20) -> str:
    """A text bar like ████████░░░░ for a percentage (capped at 100%)."""
    # min(..., width): a category at 150% still draws a full bar, not a longer one.
    filled = min(round(percent / 100 * width), width)
    # String repetition: "█" * 3 -> "███".
    return "█" * filled + "░" * (width - filled)


def pause() -> None:
    """Wait for Enter, so the result stays on screen before the menu returns."""
    input("\n  Press Enter to return to the menu...")


def show_table(transactions: list[Transaction]) -> None:
    """Print transactions as a table with a header row."""
    # An empty table would print nothing, which looks like a bug. Say it clearly.
    if not transactions:
        print("  No transactions to show.")
        return

    # Header row. :<5 = left aligned in 5 characters, :>14 = right aligned.
    header = (
        f"  {'ID':<5} {'DATE':<10}  {'KIND':<7}  "
        f"{'CATEGORY / SUBCATEGORY':<29}{'AMOUNT':>14}"
    )
    print(header)
    print("  " + "─" * (len(header) - 2))

    for t in transactions:
        # Expenses show "-" and income "+", so the sign is visible at a glance.
        sign = "-" if t.kind == "expense" else "+"
        # :,.2f adds a thousands separator and 2 decimals: 1500 -> 1,500.00
        amount = f"{sign}{t.amount:,.2f} {t.currency}"
        place = f"{t.category} / {t.subcategory}"
        print(f"  {t.id:<5} {t.date:<10}  {t.kind:<7}  {place:<29}{amount:>14}")

    print("  " + "─" * (len(header) - 2))
    print(f"  {len(transactions)} transaction(s)")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask_until_valid(prompt: str, check) -> object:
    """Ask again and again until check(answer) does not raise ValueError.

    This is the validation loop from manual 3.3. "check" is one of the
    validate_... functions: it returns the clean value or raises ValueError.
    (check has no type hint on purpose: describing "a function" as a type
    needs a tool we did not see in class.)
    """
    while True:
        answer = input(f"  {prompt}")
        try:
            return check(answer)
        except ValueError as problem:
            # Show the reason and ask again. The program never crashes here.
            error(f"{problem}. Try again.")


def optional(check):
    """Wrap a validator so that an empty answer means 'skip' (returns None)."""
    # This function RETURNS a new function (a lambda). Functions are values
    # in Python: they can be stored, passed and returned (manual 4.3).
    return lambda text: None if text.strip() == "" else check(text)


# ---------------------------------------------------------------------------
# One function per menu option
# ---------------------------------------------------------------------------

def add_transaction(budget: Budget) -> None:
    section("New transaction")

    # Each field is checked as soon as it is typed, so the user can fix it
    # right away instead of typing everything again.
    date = ask_until_valid("Date (YYYY-MM-DD): ", validate_date)
    kind = ask_until_valid(f"Kind ({' / '.join(sorted(KINDS))}): ", validate_kind)

    # Show only the categories that are valid for this kind.
    categories = categories_for(kind)
    print(f"    Options: {', '.join(categories)}")
    # lambda: validate_category needs the kind too, so we wrap it in a small
    # function that only receives the answer.
    category = ask_until_valid("Category: ", lambda text: validate_category(kind, text))

    print(f"    Options: {', '.join(categories[category])}")
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
    print()
    success(f"Saved as {transaction.id}")
    show_table([transaction])


def list_transactions(budget: Budget) -> None:
    section("All transactions (by date)")
    show_table(budget.list_by_date())


def filter_transactions(budget: Budget) -> None:
    section("Filter transactions")
    print("    Press Enter to skip a filter.")

    # optional(...) accepts an empty answer as "no filter" (None), but still
    # rejects typos like "expence" instead of silently showing nothing.
    kind = ask_until_valid("Kind (expense / income): ", optional(validate_kind))

    # If a kind was chosen, the category must belong to it.
    # If not, any existing category is accepted.
    if kind is None:
        category = ask_until_valid("Category: ", optional(validate_any_category))
    else:
        category = ask_until_valid(
            "Category: ", optional(lambda text: validate_category(kind, text))
        )

    month = ask_until_valid("Month (YYYY-MM): ", optional(validate_month))

    print()
    show_table(budget.filter(kind=kind, category=category, month=month))


def show_report(budget: Budget) -> None:
    section("Report")
    currencies = budget.currencies()
    if not currencies:
        print("  No transactions yet, nothing to report.")
        return

    # Show the months that have data, so the user knows what to type.
    print(f"    Months with data: {', '.join(budget.months())}")
    month = ask_until_valid("Month (YYYY-MM, Enter for all time): ", optional(validate_month))
    period = month if month else "all time"

    # True once at least one currency had data in this period.
    shown = False

    # One report per currency, because euros and dollars cannot be added together.
    for currency in currencies:
        summary = budget.summary(currency, month)
        # Skip a currency with nothing in this month.
        if summary["income"] == 0 and summary["expenses"] == 0:
            continue
        shown = True

        section(f"{period} · {currency}")
        # :>14,.2f = right aligned in 14 characters, thousands separator, 2 decimals.
        print(f"  {'Income':<12}{summary['income']:>14,.2f}")
        print(f"  {'Expenses':<12}{summary['expenses']:>14,.2f}")
        print("  " + "─" * 26)
        print(f"  {'Balance':<12}{summary['balance']:>14,.2f}")

        totals = budget.totals_by_category(currency, month)
        if totals:
            print()
            print("  Expenses by category")
            for category, total in totals.items():
                # Share of all expenses in this currency, as a percentage.
                share = total / summary["expenses"] * 100
                print(f"  {category:<12}{total:>12,.2f}  {bar(share)} {share:>3.0f}%")

    if not shown:
        print(f"\n  No transactions in {period}.")

    # Limits are monthly and in EUR, so they are only shown for one month.
    if budget.limits:
        if month is None:
            print("\n    Choose a month to compare spending with your limits.")
        else:
            show_limits(budget, month)


def show_limits(budget: Budget, month: str) -> None:
    """Print spent vs. limit for each category that has a limit."""
    section(f"Limits for {month} · EUR")
    for row in budget.limit_status(month):
        # ✔ when under or exactly at the limit, ✖ when over it.
        if row["over"]:
            verdict = f"✖ over by {-row['remaining']:,.2f}"
        else:
            verdict = f"✔ {row['remaining']:,.2f} left"
        used = f"{row['spent']:,.2f} / {row['limit']:,.2f}"
        print(f"  {row['category']:<12}{used:>20}  {bar(row['percent'])} {row['percent']:>3}%  {verdict}")


def manage_limits(budget: Budget) -> None:
    section("Monthly spending limits (EUR)")

    # Show the current limits first.
    if budget.limits:
        for category, limit in budget.limits.items():
            print(f"  {category:<12}{limit:>12,.2f}")
    else:
        print("  No limits set yet.")

    print(f"\n    Expense categories: {', '.join(categories_for('expense'))}")
    category = ask_until_valid("Category (Enter to go back): ", optional(validate_limit_category))
    if category is None:
        return

    # An empty amount removes the limit; anything else must be a valid amount.
    amount = ask_until_valid(
        "Monthly limit (Enter to remove it): ", optional(validate_amount)
    )
    if amount is None:
        if budget.remove_limit(category):
            success(f"Limit for {category} removed.")
        else:
            print(f"  {category} had no limit.")
    else:
        budget.set_limit(category, amount)
        success(f"Limit for {category} set to {amount:,.2f} EUR per month.")


def import_transactions(budget: Budget) -> None:
    section("Import a CSV file")
    path = input(f"  File (Enter for {SAMPLE_FILE}): ").strip() or SAMPLE_FILE
    try:
        added, rejected = budget.import_file(path)
    except ValueError as problem:
        # For example, the file name was typed wrong.
        error(str(problem))
        return

    print()
    success(f"Imported {len(added)} transaction(s)")
    if rejected:
        # Never ignore bad rows silently: show every one with its reason.
        error(f"{len(rejected)} row(s) rejected:")
        for message in rejected:
            print(f"      {message}")


def undo_last(budget: Budget) -> None:
    section("Undo last transaction")

    # last_transaction is a property of Budget, so the menu does not need to
    # know how the list is stored inside (encapsulation, manual 10.3).
    last = budget.last_transaction
    if last is None:
        print("  Nothing to undo.")
        return

    # Show what will be removed and ask before deleting.
    print("  Last transaction added:")
    show_table([last])
    answer = input("\n  Remove it? (y/n): ").strip().lower()
    if answer == "y":
        removed = budget.undo()
        success(f"Removed {removed.id}. The file was updated.")
    else:
        print("  Nothing was removed.")


# ---------------------------------------------------------------------------
# Main program
# ---------------------------------------------------------------------------

def show_menu(budget: Budget) -> None:
    title("Personal Budget Manager")
    # A status line so the user always knows which file is open.
    print(f"  File: {budget.path}   ·   {len(budget.transactions)} transaction(s)")
    print("─" * WIDTH)
    # Tuple unpacking in the for loop: each item is (number, text) (manual 5.3).
    for number, text in MENU_OPTIONS:
        print(f"   [{number}]  {text}")
    print("─" * WIDTH)


def main() -> None:
    # argparse reads options written after the command (manual 9.3),
    # for example: uv run budget --file data/test.csv
    parser = argparse.ArgumentParser(description="Personal budget manager")
    parser.add_argument(
        "--file", default=DATA_FILE, help=f"CSV file to use (default: {DATA_FILE})"
    )
    args = parser.parse_args()

    budget = Budget(args.file)

    # If the working file has bad rows (for example, edited by hand), warn the user.
    if budget.rejected:
        error(f"{len(budget.rejected)} invalid row(s) or limit(s) were skipped:")
        for message in budget.rejected:
            print(f"      {message}")

    # A dictionary that links each menu option to its function.
    # This replaces a long chain of if / elif (manual 4.3).
    actions = {
        "1": add_transaction,
        "2": list_transactions,
        "3": filter_transactions,
        "4": show_report,
        "5": manage_limits,
        "6": import_transactions,
        "7": undo_last,
    }

    # The menu loop: repeat until the user chooses 0.
    try:
        while True:
            show_menu(budget)
            choice = input("  Choose an option: ").strip()
            if choice == "0":
                print("\n  Goodbye!\n")
                break
            if choice in actions:
                # actions[choice] is a function; (budget) calls it.
                actions[choice](budget)
                pause()
            else:
                error("Unknown option, please choose a number from the menu.")
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C or Ctrl+D: exit cleanly. Nothing is lost, because every
        # change was already saved to the file.
        print("\n\n  Goodbye! (all changes were already saved)\n")


# Runs main() only when this file is started directly,
# not when it is imported (for example, by the tests).
if __name__ == "__main__":
    main()