"""
test_core.py - Tests for the budget manager, written with assert.

Each test function checks one behavior, following Think -> Predict -> Test:
the expected value is written in the assert BEFORE running the code.
assert is silent when the condition is True and stops with AssertionError
when it is False (manual 3.3).

The tests never use input() or print() from the program: they call the
functions and classes directly. This is only possible because the CLI is
separated from the logic (brief: "functions that prompt the user, calculate
balances, and write files simultaneously cannot be tested independently").

How to run (from the project folder):
    uv run python tests/test_core.py

What is inside (brief: normal case + boundary cases + malformed input +
persistence round-trips):
1. Normal case: a valid transaction is accepted and cleaned.
2. Boundary cases: amount, date, category and subcategory limits.
3. Malformed input: loading the sample file gives the expected rejected rows.
4. Persistence: save and load give back the same transactions (round trip).
5. Report: totals match numbers calculated by hand.
6. Undo (stretch challenge): saved to the file and survives a restart.
7. Import: a missing file gives a clear error, the sample file never changes.
8. Monthly report: totals for one month only.
9. Monthly limits: under, exactly at, and over the limit; saved to JSON;
   invalid limits rejected.

Tools used:
- assert with exact expected values (manual 3.3).
- lambda to delay a call until error_message() runs it (manual 6.3).
- try / except / return to capture an error message (manual 3.2).
- pathlib: .unlink(), .exists(), .read_text(), .write_text() (manual 7.2).
- A list of functions run in a for loop (functions are values, manual 4.3).
"""

from pathlib import Path

from budget_manager.models import Transaction
from budget_manager.services import Budget
from budget_manager.storage import load_transactions, save_transactions
from budget_manager.validation import (
    validate_amount,
    validate_any_category,
    validate_category,
    validate_date,
    validate_limit_category,
    validate_month,
    validate_subcategory,
)

SAMPLE_FILE = Path("data/sample_transactions.csv")

# A temporary file only for the tests. It is deleted before and after each
# test, so tests never touch the real data/transactions.csv.
TEST_FILE = Path("tests/tmp_test_transactions.csv")
TEST_LIMITS = Path("tests/tmp_test_limits.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def error_message(action) -> str:
    """Run action (a lambda) and return its ValueError message, failing if it succeeds."""
    try:
        action()
    except ValueError as error:
        return str(error)
    raise AssertionError("action did not raise ValueError")


def clean_test_file() -> None:
    # missing_ok=True: no error if the file does not exist.
    TEST_FILE.unlink(missing_ok=True)
    TEST_LIMITS.unlink(missing_ok=True)


def new_budget() -> Budget:
    """A fresh budget that only uses the temporary test files."""
    clean_test_file()
    return Budget(TEST_FILE, TEST_LIMITS)


# ---------------------------------------------------------------------------
# 1. Normal case
# ---------------------------------------------------------------------------

def test_valid_transaction_is_cleaned() -> None:
    # Messy input: lowercase id, spaces, capitals, lowercase currency.
    t = Transaction("t001", " 2026-09-04 ", "Expense", " Food ", "Supermarket", "18.50", "eur")

    # Expected: every value comes out clean.
    assert t.id == "T001"
    assert t.date == "2026-09-04"
    assert t.kind == "expense"
    assert t.category == "food"
    assert t.subcategory == "supermarket"
    assert t.amount == 18.5
    assert t.currency == "EUR"

    # The property gives the amount with a sign.
    assert t.signed_amount == -18.5


# ---------------------------------------------------------------------------
# 2. Boundary cases
# ---------------------------------------------------------------------------

def test_amount_boundaries() -> None:
    # Just inside the limits: accepted.
    assert validate_amount("0.01") == 0.01
    assert validate_amount("1000000") == 1000000

    # Just outside the limits: rejected with the exact message.
    assert error_message(lambda: validate_amount("0")) == "amount must be > 0, got 0"
    assert error_message(lambda: validate_amount("-5")) == "amount must be > 0, got -5"
    assert error_message(lambda: validate_amount("1000000.01")) == (
        "amount must be at most 1000000, got 1000000.01"
    )
    assert error_message(lambda: validate_amount("18.555")) == (
        "amount can have at most 2 decimals, got 18.555"
    )

    # Values that float() accepts but are not real amounts.
    # This boundary changed the design: "nan" passed the first version.
    assert error_message(lambda: validate_amount("nan")) == "amount must be > 0, got nan"
    assert error_message(lambda: validate_amount("inf")) == (
        "amount must be at most 1000000, got inf"
    )

    # Not a number and empty.
    assert error_message(lambda: validate_amount("abc")) == "amount must be a number, got 'abc'"
    assert error_message(lambda: validate_amount("   ")) == "amount is required"


def test_date_boundaries() -> None:
    # 2024 is a leap year, so 29 February exists.
    assert validate_date("2024-02-29") == "2024-02-29"

    # 2025 is not a leap year, so 29 February does not exist.
    assert error_message(lambda: validate_date("2025-02-29")) == "date '2025-02-29' does not exist"
    assert error_message(lambda: validate_date("2026-13-40")) == "date '2026-13-40' does not exist"

    # Wrong format.
    assert error_message(lambda: validate_date("04/09/2026")) == (
        "date must be YYYY-MM-DD, got '04/09/2026'"
    )


def test_category_and_subcategory_rules() -> None:
    # Unknown category: rejected, not mapped to "other".
    assert "category 'gym' is not valid for expense" in error_message(
        lambda: validate_category("expense", "gym")
    )
    # A real category, but for the wrong kind.
    assert "category 'food' is not valid for income" in error_message(
        lambda: validate_category("income", "food")
    )
    # A real subcategory, but of another category.
    assert "subcategory 'cinema' is not valid for food" in error_message(
        lambda: validate_subcategory("expense", "food", "cinema")
    )
    # The filter accepts any existing category, and still rejects typos.
    assert validate_any_category(" Salary ") == "salary"
    assert "category 'fod' does not exist" in error_message(
        lambda: validate_any_category("fod")
    )


# ---------------------------------------------------------------------------
# 3. Malformed input: loading the sample file
# ---------------------------------------------------------------------------

def test_load_sample_file() -> None:
    accepted, rejected = load_transactions(SAMPLE_FILE)

    # The sample has 17 rows: 6 valid and 11 invalid on purpose.
    assert len(accepted) == 6
    assert len(rejected) == 11

    # Each rejected message has the row number and the reason.
    assert rejected[0] == "Row 6: amount must be > 0, got -5"
    assert "Row 15: id T003 is repeated" in rejected
    assert "Row 16: subcategory is required" in rejected

    # Row 5 had " Food " and "eur": accepted and cleaned.
    assert accepted[3].category == "food"
    assert accepted[3].currency == "EUR"


def test_missing_working_file_starts_empty() -> None:
    clean_test_file()
    accepted, rejected = load_transactions(TEST_FILE)
    assert accepted == []
    assert rejected == []


# ---------------------------------------------------------------------------
# 4. Persistence: save and load again (round trip)
# ---------------------------------------------------------------------------

def test_save_and_load_round_trip() -> None:
    clean_test_file()
    original, _ = load_transactions(SAMPLE_FILE)

    save_transactions(TEST_FILE, original)
    loaded, rejected = load_transactions(TEST_FILE)

    # Same transactions, same values, nothing rejected.
    assert rejected == []
    assert [t.to_dict() for t in loaded] == [t.to_dict() for t in original]
    clean_test_file()


# ---------------------------------------------------------------------------
# 5. Report
# ---------------------------------------------------------------------------

def test_report_totals() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    budget.import_file(SAMPLE_FILE)
    budget.add("2026-09-20", "expense", "food", "delivery", "5", "USD")

    # Calculated by hand from the 6 valid sample rows:
    # income   = 1500 + 25 = 1525
    # expenses = 650 + 18.50 + 24.90 + 35 = 728.40
    # balance  = 1525 - 728.40 = 796.60
    assert budget.summary("EUR") == {
        "currency": "EUR", "income": 1525.0, "expenses": 728.4, "balance": 796.6,
    }
    # The USD expense is reported apart, never added to the euros.
    assert budget.summary("USD")["expenses"] == 5.0
    assert budget.currencies() == ["EUR", "USD"]

    # Biggest category first.
    assert budget.totals_by_category("EUR") == {"home": 650.0, "food": 43.4, "leisure": 35.0}

    # Filters.
    assert [t.id for t in budget.filter(kind="income")] == ["T001", "T005"]
    assert len(budget.filter(category="food")) == 3
    clean_test_file()


# ---------------------------------------------------------------------------
# 6. Undo (stretch challenge)
# ---------------------------------------------------------------------------

def test_undo_is_saved_and_survives_restart() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    budget.add("2026-09-10", "expense", "food", "supermarket", "20", "EUR")
    # The second one has an EARLIER date, but it is the last one ADDED.
    budget.add("2026-09-01", "expense", "home", "rent", "650", "EUR")

    # Simulate closing and opening the program: a new Budget reads the file.
    # (Brief: "what happens if the user undoes after a crash and reload?")
    restarted = Budget(TEST_FILE, TEST_LIMITS)
    last = restarted.last_transaction
    assert last is not None
    assert last.id == "T002"
    removed = restarted.undo()

    # Undo removes the last added (T002), not the latest date.
    assert removed is not None
    assert removed.id == "T002"

    # Open again: the file must show the undo too.
    after = Budget(TEST_FILE, TEST_LIMITS)
    assert [t.id for t in after.transactions] == ["T001"]

    # The next id is T002 again, so there are no gaps or repeats.
    assert after.next_id() == "T002"
    clean_test_file()


def test_undo_on_empty_budget() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    # Nothing to undo: returns None instead of crashing.
    assert budget.last_transaction is None
    assert budget.undo() is None


def test_failed_add_changes_nothing() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    message = error_message(
        lambda: budget.add("2026-09-10", "expense", "food", "supermarket", "-1", "EUR")
    )
    assert message == "amount must be > 0, got -1"
    # Nothing was added and no file was created.
    assert budget.transactions == []
    assert not TEST_FILE.exists()


def test_transactions_cannot_be_changed_from_outside() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    budget.add("2026-09-10", "expense", "food", "supermarket", "20", "EUR")

    # The property returns a copy: changing it does not change the budget.
    copy = budget.transactions
    copy.clear()
    assert len(budget.transactions) == 1
    clean_test_file()


# ---------------------------------------------------------------------------
# 7. Import
# ---------------------------------------------------------------------------

def test_import_missing_file() -> None:
    clean_test_file()
    budget = Budget(TEST_FILE, TEST_LIMITS)
    assert error_message(lambda: budget.import_file("nope.csv")) == "file 'nope.csv' was not found"
    # A folder is not a file: clear message instead of IsADirectoryError.
    assert error_message(lambda: budget.import_file("data")) == "file 'data' was not found"


def test_ids_stop_at_T999() -> None:
    budget = new_budget()
    # Boundary: T999 is the last id. Instead of adding 998 transactions, we
    # add one and change its id to T998 (only in memory, for the test).
    # The next one gets T999 (accepted), and one more must fail.
    budget.add("2026-09-01", "expense", "food", "general", "1", "EUR")
    budget._transactions[0].id = "T998"
    assert budget.add("2026-09-01", "expense", "food", "general", "1", "EUR").id == "T999"

    assert error_message(
        lambda: budget.add("2026-09-01", "expense", "food", "general", "1", "EUR")
    ) == "the file is full: ids only go up to T999"
    # An import that does not fit adds nothing (not half of the file).
    assert "not enough space for 6" in error_message(lambda: budget.import_file(SAMPLE_FILE))
    assert len(budget.transactions) == 2
    clean_test_file()


def test_import_never_changes_sample_file() -> None:
    clean_test_file()
    before = SAMPLE_FILE.read_text(encoding="utf-8")

    budget = Budget(TEST_FILE, TEST_LIMITS)
    budget.import_file(SAMPLE_FILE)
    budget.undo()

    after = SAMPLE_FILE.read_text(encoding="utf-8")
    assert before == after
    clean_test_file()


# ---------------------------------------------------------------------------
# 8. Monthly report
# ---------------------------------------------------------------------------

def test_month_rules() -> None:
    assert validate_month(" 2026-09 ") == "2026-09"
    assert error_message(lambda: validate_month("2026-13")) == "month '2026-13' does not exist"
    assert error_message(lambda: validate_month("2026-00")) == "month '2026-00' does not exist"
    assert error_message(lambda: validate_month("09/2026")) == "month must be YYYY-MM, got '09/2026'"


def test_monthly_report() -> None:
    budget = new_budget()
    budget.import_file(SAMPLE_FILE)
    budget.add("2026-10-02", "expense", "food", "supermarket", "60", "EUR")

    assert budget.months() == ["2026-09", "2026-10"]

    # September only: the October expense is NOT counted.
    assert budget.summary("EUR", "2026-09")["expenses"] == 728.4
    # October only: just the new expense.
    assert budget.summary("EUR", "2026-10") == {
        "currency": "EUR", "income": 0, "expenses": 60.0, "balance": -60.0,
    }
    # All time (month=None): both months together. 728.40 + 60 = 788.40
    assert budget.summary("EUR")["expenses"] == 788.4

    assert budget.totals_by_category("EUR", "2026-10") == {"food": 60.0}
    assert [t.id for t in budget.filter(month="2026-10")] == ["T007"]
    clean_test_file()


# ---------------------------------------------------------------------------
# 9. Monthly limits
# ---------------------------------------------------------------------------

def test_limit_status_under_at_and_over() -> None:
    budget = new_budget()
    budget.import_file(SAMPLE_FILE)
    # September spending: food 43.40, home 650.00, leisure 35.00
    budget.set_limit("food", "40")      # over
    budget.set_limit("home", "650")     # exactly at the limit
    budget.set_limit("leisure", "100")  # under
    budget.set_limit("health", "50")    # a limit with no spending

    # A list of dicts turned into a dict by category, to check each one.
    status = {row["category"]: row for row in budget.limit_status("2026-09")}

    assert status["food"]["over"] is True
    assert status["food"]["remaining"] == -3.4

    # Boundary: exactly at the limit is NOT over.
    assert status["home"]["over"] is False
    assert status["home"]["remaining"] == 0
    assert status["home"]["percent"] == 100

    assert status["leisure"]["remaining"] == 65.0
    assert status["health"]["spent"] == 0

    # Sorted by how much of the limit is used: the problem comes first.
    assert budget.limit_status("2026-09")[0]["category"] == "food"
    clean_test_file()


def test_limits_are_saved_and_validated() -> None:
    budget = new_budget()
    budget.set_limit(" Food ", "300")

    # Saved to JSON and loaded again after a restart.
    restarted = Budget(TEST_FILE, TEST_LIMITS)
    assert restarted.limits == {"food": 300.0}

    # Same rules as transactions: expense categories only, valid amounts.
    assert "not valid for expense" in error_message(lambda: budget.set_limit("salary", "100"))
    assert error_message(lambda: budget.set_limit("food", "0")) == "amount must be > 0, got 0"
    assert "not valid for expense" in error_message(lambda: validate_limit_category("gym"))

    # Removing a limit.
    assert restarted.remove_limit("food") is True
    assert restarted.remove_limit("food") is False
    assert Budget(TEST_FILE, TEST_LIMITS).limits == {}
    clean_test_file()


def test_invalid_limits_file_is_reported() -> None:
    clean_test_file()
    # A file edited by hand with one good and two bad limits.
    TEST_LIMITS.write_text('{"food": 300, "gym": 50, "home": -10}', encoding="utf-8")
    budget = Budget(TEST_FILE, TEST_LIMITS)

    assert budget.limits == {"food": 300.0}
    assert len(budget.rejected) == 2

    # A broken JSON file does not crash the program.
    TEST_LIMITS.write_text('{"food": 300,', encoding="utf-8")
    budget = Budget(TEST_FILE, TEST_LIMITS)
    assert budget.limits == {}
    assert "not valid JSON" in budget.rejected[0]
    clean_test_file()


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # A list of functions: functions are values, so they can be stored in a
    # list and called later in a loop (manual 4.3).
    tests = [
        test_valid_transaction_is_cleaned,
        test_amount_boundaries,
        test_date_boundaries,
        test_category_and_subcategory_rules,
        test_load_sample_file,
        test_missing_working_file_starts_empty,
        test_save_and_load_round_trip,
        test_report_totals,
        test_undo_is_saved_and_survives_restart,
        test_undo_on_empty_budget,
        test_failed_add_changes_nothing,
        test_transactions_cannot_be_changed_from_outside,
        test_import_missing_file,
        test_ids_stop_at_T999,
        test_import_never_changes_sample_file,
        test_month_rules,
        test_monthly_report,
        test_limit_status_under_at_and_over,
        test_limits_are_saved_and_validated,
        test_invalid_limits_file_is_reported,
    ]
    print()
    for test in tests:
        test()
        # test.__name__ is the name of the function, e.g. "test_date_boundaries".
        print(f"  ✔ {test.__name__}")
    print(f"\n  All {len(tests)} tests passed.\n")
