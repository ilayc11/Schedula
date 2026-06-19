import asyncpg
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator
from src.config import settings


class Database:
    """Database connection pool manager for PostgreSQL"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """
        Create database connection pool.
        Should be called on application startup.
        """
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
                command_timeout=60
            )
            print("✓ Database connection pool created")
    
    async def disconnect(self) -> None:
        """
        Close database connection pool.
        Should be called on application shutdown.
        """
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            print("✓ Database connection pool closed")
    
    async def fetch_one(self, query: str, *args) -> Optional[asyncpg.Record]:
        """
        Execute a query and fetch one row.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Single record or None if no results
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)
    
    async def fetch_all(self, query: str, *args) -> list[asyncpg.Record]:
        """
        Execute a query and fetch all rows.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            List of records
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)
    
    async def execute(self, query: str, *args) -> str:
        """
        Execute a query without returning results.
        
        Args:
            query: SQL query to execute
            *args: Query parameters
            
        Returns:
            Status of the query execution
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)
    
    async def execute_many(self, query: str, args_list: list) -> None:
        """
        Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query to execute
            args_list: List of parameter tuples
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        async with self.pool.acquire() as connection:
            await connection.executemany(query, args_list)
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for database transactions.
        
        Usage:
            async with db.transaction() as conn:
                await conn.execute("INSERT ...")
                await conn.execute("UPDATE ...")
                # Automatically commits on success, rolls back on exception
        """
        if self.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield connection


# Global database instance
db = Database()
