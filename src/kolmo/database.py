"""
KOLMO Database Connection

🔒 REQ-7.5: Production database connections MUST use TLS/SSL encryption.
🔒 REQ-7.6: API service MUST use read-only role for queries.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Connection, Pool

from kolmo.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Pool | None = None


async def create_pool() -> Pool:
    """Create database connection pool."""
    settings = get_settings()
    
    pool = await asyncpg.create_pool(
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
        user=settings.database_user,
        password=settings.database_password,
        min_size=2,
        max_size=10,
        command_timeout=30,
        # 🔒 REQ-7.5: SSL configuration
        ssl="prefer" if settings.database_ssl_mode == "prefer" else settings.database_ssl_mode,
    )
    
    logger.info(
        f"Database pool created: {settings.database_host}:{settings.database_port}"
        f"/{settings.database_name}"
    )
    return pool


async def get_pool() -> Pool:
    """Get or create database connection pool."""
    global _pool
    if _pool is None:
        _pool = await create_pool()
    return _pool


async def close_pool() -> None:
    """Close database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[Connection, None]:
    """Get database connection from pool."""
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection


async def check_connection() -> bool:
    """Check if database is reachable."""
    try:
        async with get_connection() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


async def get_latest_data_date() -> str | None:
    """Get the date of the most recent KOLMO data."""
    try:
        async with get_connection() as conn:
            result = await conn.fetchval(
                "SELECT MAX(date) FROM mcol1_compute_data"
            )
            return str(result) if result else None
    except Exception as e:
        logger.error(f"Failed to get latest data date: {e}")
        return None
