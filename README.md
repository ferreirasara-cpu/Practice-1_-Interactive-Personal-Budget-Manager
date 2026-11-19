# Personal Budget Manager

A command line program to record my income and expenses, save them to a CSV
file, and see reports by category.

## Project structure

- models.py -> the Transaction class (what a transaction is)
- validation.py -> the rules and the category lists
- services.py -> the budget logic (add, list, filter, report, undo)
- storage.py -> reading and writing the CSV file
- cli.py -> the menu the user sees (the only file with input() and print())
- tests/test_core.py -> tests written with assert

## Features and the tool used

- Transaction -> a class with __init__ that checks every field before
  saving it, so an invalid transaction can never exist (models.py)
- Create a transaction from a CSV row -> @classmethod from_dict(row) (models.py)
- Turn a transaction back into a row -> to_dict() method returning a dictionary (models.py)
- Menu -> while True loop with input() and if / elif, break to exit (cli.py)
- Choose the data file when starting -> argparse with a --file option (cli.py)
- Add a transaction -> list.append() on the list of transactions (services.py)
- Automatic id (T001, T002...) -> f-string with format f"T{number:03d}" (services.py)
- List transactions -> for loop with enumerate() and f-strings,
  sorted by date with sorted(key=lambda t: t.date) (services.py, cli.py)
- Filter by kind or category -> list comprehension (services.py)
- Totals by category -> dictionary built with totals.get(category, 0) + amount (services.py)
- Total income, total expenses and balance -> sum() and round(x, 2) (services.py)
- Save to file -> with open(..., "w", newline="") and csv.DictWriter (storage.py)
- Load from file -> with open() and csv.DictReader, file path with pathlib.Path (storage.py)
- Undo last transaction -> list.pop() and then save the whole file again,
  so the file always matches what the program shows (services.py, storage.py)

## Rules and the tool used

Each transaction has: id, date, kind, category, subcategory, amount, currency.

- All fields are required -> loop over the field names, row.get(field, "").strip(),
  raise ValueError if empty
- Clean spaces and capitals -> .strip(), .lower(), .upper()
- Id must look like T001 and can't repeat -> re.fullmatch(r"T\d{3}", id) and a
  set of ids already used
- Date must be a real date in YYYY-MM-DD -> re.fullmatch for the format, then
  date.fromisoformat() from datetime to reject dates like 2026-13-40
- Kind is expense or income -> "in" a set {"expense", "income"}
- Category must exist for that kind -> two dictionaries, EXPENSE_CATEGORIES and
  INCOME_CATEGORIES, checked with "in"
- Subcategory must belong to its category -> each category key holds a list of
  its subcategories, checked with "in"
- The amount must be a number greater than 0 and at most 1,000,000, with at most 2 decimals.” -> float() inside try / except, 
  then if amount <= 0: raise ValueError
  
- Currency must be EUR, USD or GBP -> "in" a set {"EUR", "USD", "GBP"}
- Clear error messages -> raise ValueError(f"amount must be > 0, got {value}")
- Bad rows don't stop the file from loading -> try / except / else inside the
  loop, with enumerate(rows, start=2) for the row number, and two lists:
  accepted and rejected
- Negative amounts are never turned positive and bad dates are never guessed:
  the program rejects them and says why

## Categories

Expenses
- food: supermarket, restaurants, delivery, general
- transport: public_transport, fuel, taxi, general
- home: rent, utilities, internet, general
- leisure: cinema, travel, sports, general
- health: pharmacy, doctor, general
- shopping: clothes, electronics, general

Income
- salary: payroll, bonus, general
- other_income: bizum, refund, general