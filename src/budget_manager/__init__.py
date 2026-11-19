"""Personal budget manager: Release 1."""
"""
budget_manager - Interactive personal budget manager.

The package is split into layers, each in its own file:
- validation.py: the rules for every field
- models.py:     the Transaction class
- storage.py:    reading and writing CSV files
- services.py:   the Budget class (the business logic)
- cli.py:        the menu (the only file that talks to the user)

Run it with:  uv run budget
"""
