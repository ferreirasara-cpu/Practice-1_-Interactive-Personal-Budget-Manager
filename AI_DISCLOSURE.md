# AI disclosure

I used Claude (Anthropic) as a co-creation partner. I designed the program,
wrote the first versions from my own pseudocode, and directed every stage of
the work with specific instructions. The AI corrected and completed code on
top of my versions, proposed tools when I had none, and tested the program
when I asked it to. I set one rule for the whole project: **only tools from
our course manual (sessions 1 to 10)**. Anything outside it had to be
justified and listed here.

## My decisions

These shaped the program and came from me:

- **The domain:** a budget manager inspired by the BBVA app, with its
  categories and subcategories ("Mi día a día") and monthly spending limits
  ("Mis presupuestos").
- **The key design decision:** the program never saves over the file it
  imports from, so the invalid rows of the sample file are never lost
  (see DESIGN.md).
- **Strict data policy:** unknown categories are rejected instead of mapped
  to "other", and values are cleaned but never corrected.
- **Scope:** one complete release that includes the stretch challenge (undo
  that survives a restart), plus monthly reports and limits.
- **Course content on purpose:** type hints, `@property`, encapsulation and
  composition, to show the OOP sessions in a real program.
- **Documentation:** the diagrams in DESIGN.md, and a README in the order of
  the brief.

## How I directed the AI

Each stage of the work started from a request of mine, and the AI's code
followed it:

1. **Building:** I wrote pseudocode and first versions of each file, and asked
   the AI to correct them and explain every step with the course concepts.
   It wrote the final versions of the six modules over my code, with
   comments and docstrings.
2. **Adversarial iterations:** I asked it to be adversarial with both my
   versions and its own, and I iterated until I understood every part.
3. **Delivery check:** I asked it to make sure the whole project works before
   delivery, using only tools I had seen in class. It fixed two crashes
   (importing a folder, adding after T999) and stopped the program from
   opening the sample file as its working file.
4. **Brief check:** I gave it the assignment brief and asked it to check the
   project against every point without going beyond the course. It moved the
   category percentages from `cli.py` to `services.py`.
5. **Course check:** I gave it my course manual, and it replaced the tools
   outside it with course ones where possible.
6. **Format and aesthetics:** I directed it to enhance the format and look of
   the documents: README and DESIGN drafts over my versions, badges, BBVA blue
   colors, colored diagrams and the checklist table. This goes beyond the
   course on purpose; it is presentation, not code.
7. **Professor review:** I asked it to attack the program "like a professor
   would" and fix every problem with course content only. It stopped
   double imports from counting twice, made amounts follow the pattern
   `18.50`, and added a clear error for files separated by `;`, with tests for
   each fix (22 in total).

## Ideas that came from the AI, and why I kept them

- **`date.fromisoformat()`** to check that a date exists. It is not in the
  course, but checking days per month and leap years by hand was longer and
  easier to get wrong.
- **Boundary rules for amounts:** rejecting `nan` and `inf`, a 1,000,000
  maximum, and more than 2 decimals rejected instead of rounded. They apply my
  own policy of never correcting data.
- **One report per currency**, so euros and dollars are never added together.
- **Clear errors instead of silent results:** a missing import file, and typos
  in the filters such as "expence".
- **A copy of the list from `Budget.transactions`**, so other files cannot
  change it without saving.
- **Limits saved as JSON** (settings) instead of CSV (records), with "exactly
  at the limit" counting as within it.

## Tools outside the course manual

Everything else in the code comes from the manual. These tools do not, and
each one is used only where the course had no equivalent:

| Tool | Where | Why |
|---|---|---|
| `date.fromisoformat()` | `validation.py` | checks that a date really exists |
| `Path.is_file()` | `services.py` | importing a folder gives a clear message instead of crashing |
| `path.parent` | `storage.py` | the folder of a file, to create `data/` with `.mkdir(exist_ok=True)` the first time |
| `.center()` | `cli.py` | display only: centers the menu title |
| `except (KeyboardInterrupt, EOFError)` | `cli.py` | Ctrl+C or Ctrl+D closes the program with a message instead of an error (nothing is lost, every change is already saved) |

## How I checked the work

I read every file and made sure I understood the code I had not written
myself, using its comments. I asked the AI to be adversarial with my versions
and with its own, and I questioned its proposals before keeping them. I ran
the tests (`uv run python tests/test_core.py`, 22 passing) and used every
menu option with valid and wrong input.
