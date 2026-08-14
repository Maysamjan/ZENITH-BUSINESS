"""Repository / data-access layer (Stage 02 §4, §47).

Repositories own all SQL. Services compose them inside transactions; the UI never
executes SQL. All statements are parameterized.
"""
