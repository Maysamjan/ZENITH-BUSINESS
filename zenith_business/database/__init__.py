"""Database infrastructure layer (Prompt 01 §9-§11).

This package provides *infrastructure only*: connection management, SQLite
safety configuration, and generic transaction handling. It creates NO business
tables — schema is the responsibility of a future stage (Stage 02).

Business services will depend on this layer, never on the UI. The public surface
is intentionally small: :class:`~zenith_business.database.connection.Database`.
"""

from zenith_business.database.connection import Database
from zenith_business.database.health import DatabaseHealth, check_health

__all__ = ["Database", "DatabaseHealth", "check_health"]
