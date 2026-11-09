"""Reusable FastAPI dependencies.

Anything that's a ``Depends(...)`` target used by more than one router
lives here. Single-purpose deps stay next to their route to avoid
making this module the universal grab-bag.
"""
