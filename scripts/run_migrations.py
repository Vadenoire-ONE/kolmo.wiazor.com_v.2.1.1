import asyncio
import os
from pathlib import Path

import asyncpg

from kolmo.config import get_settings


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements safely.

    Handles:
    - Semicolons inside dollar-quoted blocks ($$ ... $$ or $tag$ ... $tag$)
    - Semicolons inside single-quoted strings
    - Line comments starting with --
    """
    statements: list[str] = []
    current: list[str] = []

    in_single_quote = False
    in_dollar_block = False
    dollar_tag = ""

    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""

        # Handle line comments -- ... \n (only when not inside quotes/blocks)
        if not in_single_quote and not in_dollar_block and ch == '-' and nxt == '-':
            # skip until end of line
            while i < len(sql) and sql[i] != '\n':
                i += 1
            current.append('\n')
            i += 1
            continue

        # Detect start/end of dollar-quoted blocks
        if not in_single_quote:
            if not in_dollar_block and ch == '$':
                # read tag until next $ (e.g., $$ or $tag$)
                j = i + 1
                while j < len(sql) and sql[j] != '$' and sql[j] != '\n':
                    j += 1
                if j < len(sql) and sql[j] == '$':
                    # opening $tag$
                    in_dollar_block = True
                    dollar_tag = sql[i:j + 1]  # includes both $ ... $
                current.append(sql[i:j + 1])
                i = j + 1
                continue
            elif in_dollar_block:
                # check for closing $tag$
                if sql.startswith(dollar_tag, i):
                    in_dollar_block = False
                    current.append(dollar_tag)
                    i += len(dollar_tag)
                    continue
                # inside block: just append char
                current.append(ch)
                i += 1
                continue

        # Handle single-quoted strings ('' escape)
        if not in_dollar_block:
            if ch == "'":
                if in_single_quote and nxt == "'":
                    # escaped quote inside string
                    current.append("''")
                    i += 2
                    continue
                in_single_quote = not in_single_quote
                current.append(ch)
                i += 1
                continue

        # Statement boundary
        if not in_single_quote and not in_dollar_block and ch == ';':
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        # default: append char
        current.append(ch)
        i += 1

    # last leftover
    tail = ''.join(current).strip()
    if tail:
        statements.append(tail)

    # remove empty statements
    return [s for s in statements if s.strip()]


async def run_migration(sql_path: Path) -> None:
    settings = get_settings()
    sql_text = sql_path.read_text(encoding='utf-8')
    statements = _split_sql_statements(sql_text)

    conn = await asyncpg.connect(
        host=settings.database_host,
        port=settings.database_port,
        database=settings.database_name,
        user=settings.database_user,
        password=settings.database_password,
        ssl='prefer' if settings.database_ssl_mode == 'prefer' else settings.database_ssl_mode,
    )
    try:
        async with conn.transaction():
            for idx, stmt in enumerate(statements, start=1):
                # Skip pure comments or empty
                if not stmt.strip():
                    continue
                await conn.execute(stmt)
                print(f"Executed statement {idx}/{len(statements)}")
    finally:
        await conn.close()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sql_path = root / 'db' / 'migrations' / '001_initial_schema.sql'
    if not sql_path.exists():
        raise FileNotFoundError(f"Migration file not found: {sql_path}")
    print(f"Running migration: {sql_path}")
    asyncio.run(run_migration(sql_path))


if __name__ == '__main__':
    main()
