"""Base repository utilities and classes for database operations."""

from typing import Any, Dict, List, Optional, Tuple

from src.database.database import db


# =============================================================================
# Low-level database helpers
# =============================================================================

async def fetch_one(query: str, *args: Any) -> Optional[Any]:
    """Execute query and return a single record."""
    return await db.fetch_one(query, *args)


async def fetch_all(query: str, *args: Any) -> List[Any]:
    """Execute query and return all records."""
    return await db.fetch_all(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Execute a query that doesn't return data (INSERT, UPDATE, DELETE).
    
    Returns: PostgreSQL status string (e.g., 'INSERT 0 1', 'UPDATE 1', 'DELETE 1')
    """
    return await db.execute(query, *args)


async def execute_many(query: str, args_list: List[Tuple[Any, ...]]) -> None:
    """Execute the same query multiple times with different parameters."""
    await db.execute_many(query, args_list)


# =============================================================================
# Generic CRUD helpers (legacy - prefer BaseRepository for new code)
# =============================================================================

async def get_by_id(table: str, id_column: str, id_value: Any) -> Optional[Dict[str, Any]]:
    """Fetch a single row by ID."""
    sql = f"SELECT * FROM {table} WHERE {id_column} = $1"
    rec = await fetch_one(sql, id_value)
    return dict(rec) if rec is not None else None


async def list_rows(table: str, where_clause: str = "", *args: Any) -> List[Dict[str, Any]]:
    """Fetch all rows from a table, optionally filtered."""
    sql = f"SELECT * FROM {table}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    rows = await fetch_all(sql, *args)
    return [dict(r) for r in rows]


async def insert_row(table: str, data: Dict[str, Any]) -> str:
    """Insert a row and return PostgreSQL status string."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    return await execute(sql, *data.values())


async def insert_row_returning(table: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a row and return the inserted record."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"
    rec = await fetch_one(sql, *data.values())
    return dict(rec) if rec is not None else None


async def upsert_row(table: str, key_columns: List[str], data: Dict[str, Any]) -> str:
    """Insert or update on conflict, returns PostgreSQL status string."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in data.keys() if col not in key_columns])
    conflict_cols = ", ".join(key_columns)
    sql = (
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {updates}"
    )
    return await execute(sql, *data.values())


async def upsert_row_returning(table: str, key_columns: List[str], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert or update on conflict, returns the resulting record."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in data.keys() if col not in key_columns])
    conflict_cols = ", ".join(key_columns)
    sql = (
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {updates} RETURNING *"
    )
    rec = await fetch_one(sql, *data.values())
    return dict(rec) if rec is not None else None


async def update_row(table: str, id_column: str, id_value: Any, updates: Dict[str, Any]) -> str:
    """Update a row and return PostgreSQL status string."""
    set_clause = ", ".join([f"{col} = ${i}" for i, col in enumerate(updates.keys(), start=1)])
    sql = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ${len(updates) + 1}"
    return await execute(sql, *updates.values(), id_value)


async def update_row_returning(table: str, id_column: str, id_value: Any, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a row and return the updated record."""
    set_clause = ", ".join([f"{col} = ${i}" for i, col in enumerate(updates.keys(), start=1)])
    sql = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ${len(updates) + 1} RETURNING *"
    rec = await fetch_one(sql, *updates.values(), id_value)
    return dict(rec) if rec is not None else None


async def update_row_composite_key(table: str, key_conditions: Dict[str, Any], updates: Dict[str, Any]) -> str:
    """Update a row based on multiple columns in the WHERE clause, returns PostgreSQL status string."""
    # Example: SET col1=$1, col2=$2
    set_clause = ", ".join([f"{col} = ${i}" for i, col in enumerate(updates.keys(), start=1)])

    # Example: WHERE key1=$3 AND key2=$4
    start_index = len(updates) + 1
    where_clauses = [f"{col} = ${i}" for i, col in enumerate(key_conditions.keys(), start=start_index)]
    where_clause = " AND ".join(where_clauses)

    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
    params = list(updates.values()) + list(key_conditions.values())
    return await execute(sql, *params)


async def delete_row(table: str, id_column: str, id_value: Any) -> str:
    """Delete a row and return PostgreSQL status string."""
    sql = f"DELETE FROM {table} WHERE {id_column} = $1"
    return await execute(sql, id_value)


# =============================================================================
# BaseRepository class for standardized CRUD operations
# =============================================================================

class BaseRepository:
    """Base repository class providing standardized CRUD operations.
    
    Subclasses should define TABLE and ID_COLUMN class attributes.
    All methods return consistent types for better predictability.
    
    Example:
        class UserRepository(BaseRepository):
            TABLE = "users"
            ID_COLUMN = "user_id"
    """
    
    TABLE: str = ""
    ID_COLUMN: str = ""
    
    @classmethod
    async def create(cls, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new record and return it."""
        return await insert_row_returning(cls.TABLE, data)
    
    @classmethod
    async def get(cls, id_value: Any) -> Optional[Dict[str, Any]]:
        """Fetch a single record by ID."""
        return await get_by_id(cls.TABLE, cls.ID_COLUMN, id_value)
    
    @classmethod
    async def list_all(cls) -> List[Dict[str, Any]]:
        """Fetch all records."""
        return await list_rows(cls.TABLE)
    
    @classmethod
    async def list_where(cls, where_clause: str, *args: Any) -> List[Dict[str, Any]]:
        """Fetch records matching a WHERE clause."""
        return await list_rows(cls.TABLE, where_clause, *args)
    
    @classmethod
    async def update(cls, id_value: Any, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a record and return the updated record."""
        return await update_row_returning(cls.TABLE, cls.ID_COLUMN, id_value, updates)
    
    @classmethod
    async def delete(cls, id_value: Any) -> bool:
        """Delete a record and return True if successful."""
        result = await delete_row(cls.TABLE, cls.ID_COLUMN, id_value)
        return result.startswith("DELETE 1")
    
    @classmethod
    async def upsert(cls, key_columns: List[str], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insert or update on conflict, returns the resulting record."""
        return await upsert_row_returning(cls.TABLE, key_columns, data)
