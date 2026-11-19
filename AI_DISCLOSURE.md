# AI disclosure

I used Claude (Anthropic) as a co-creation partner to build this project
step by step. I asked it to use only the tools we saw in class (the course
manuals for sessions 1 to 10), and to explain every step i needed to follow  based on the concepts.
the code it generated was based on my psedocode and instructions. 
When I had no ideas or no tools claude proposed them.

## What the AI generated
- The  last correction of `validation.py`, `models.py`, `storage.py`, `services.py`,
  `cli.py` and `__init__.py`, overwriting over my own code and helping me improve the comments and docstrings explaining each part.
- Drafts of `README.md` and `DESIGN.md`, including the two diagrams where also generated over my own versions.

## Decisions I made

- Use categories and subcategories inspired by the BBVA app.
- Reject unknown categories instead of mapping them to "other".
- Never save over the sample file (my key design decision, see DESIGN.md).
- One complete version, including undo (the stretch challenge).
- Create the diagrams in  DESIGN.md and keep the README in the order the brief.
- Add type hints, @property and encapsulation to show more of the class content.
- Add monthly reports and monthly spending limits (inspired by BBVA "Mis presupuestos"). 

## Ideas that came from the AI

- `date.fromisoformat()` to check that a date really exists. We did not see it in class. I chose it because checking days per month and leap years by hand was longer and easier to get wrong.
- Rejecting `nan` and `inf` as amounts, and the 1,000,000 limit. Testing showed that `float("nan")` passed the first version of the amount check.
- Rejecting amounts with more than 2 decimals instead of rounding them.
- Reporting each currency separately instead of adding them together.
- Showing an error when an imported file does not exist, instead of
  "Imported 0 transactions".
- Validating the filter inputs, so a typo like "expence" is reported instead of silently showing no results.
- Returning a copy of the list from `Budget.transactions`, so other files cannot change it without saving.
- Documenting the schema as a table, and adding acceptance criteria and the exit-ticket reflection, after checking the work against the brief.
- Saving limits as JSON (settings) instead of CSV (records), and treating "exactly at the limit" as within the limit.

## How I checked the work
I read every file, understanding the comments of code i did not try to code myself before and iterating the code asking ai to be adversarial with my own versions and its versions.
(`uv run python tests/test_core.py`, 19 passing).