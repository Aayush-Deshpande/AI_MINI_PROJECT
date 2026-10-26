"""SQLite locally; PostgreSQL for durable serverless deployments."""
from decimal import Decimal
import re
import sqlite3


class SQLiteConnection(sqlite3.Connection):
    dialect = 'sqlite'
    lock_tour = ''
    lock_booking = ''

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class Record(dict):
    """Keep SQLite's named and positional access on PostgreSQL results."""
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def record_factory(cursor):
    names = [column.name for column in (cursor.description or ())]
    return lambda values: Record(zip(names, (float(v) if isinstance(v, Decimal) else v for v in values)))


class Cursor:
    def __init__(self, raw, inserted=False):
        self.raw = raw
        self.rowcount = raw.rowcount
        inserted_row=raw.fetchone() if inserted else None
        self.lastrowid=inserted_row['id'] if inserted_row else None

    def fetchone(self): return self.raw.fetchone()
    def fetchall(self): return self.raw.fetchall()
    def __iter__(self): return iter(self.raw)


class PostgresConnection:
    dialect = 'postgres'
    lock_tour = ' FOR UPDATE OF t'
    lock_booking = ' FOR UPDATE OF b'

    def __init__(self, url):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError('Install requirements.txt to use PostgreSQL.') from exc
        self.integrity_error = psycopg.IntegrityError
        self.raw = psycopg.connect(url, row_factory=record_factory, connect_timeout=10, prepare_threshold=None)

    def execute(self, sql, args=()):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            # Psycopg already opened a transaction during session lookup.
            # Row locks below serialize reservations for the same departure.
            sql = 'SELECT 1'
        sql = sql.replace('?', '%s')
        inserted = bool(re.match(r'\s*INSERT\s+INTO\s+(users|destinations|tours|bookings|itinerary|reviews|tickets|audit|ai_plans)\b', sql, re.I)) and 'RETURNING' not in sql.upper()
        if inserted: sql = sql.rstrip().rstrip(';') + ' RETURNING id'
        try:
            return Cursor(self.raw.execute(sql, args), inserted)
        except self.integrity_error as exc:
            raise sqlite3.IntegrityError('Conflicting or invalid record') from exc

    def executescript(self, sql):
        sql = sql.replace('id INTEGER PRIMARY KEY', 'id BIGSERIAL PRIMARY KEY')
        sql = sql.replace('DEFAULT CURRENT_TIMESTAMP', 'DEFAULT (CURRENT_TIMESTAMP::text)')
        sql = re.sub(r'\bREAL\b', 'DOUBLE PRECISION', sql)
        for statement in sql.split(';'):
            if statement.strip(): self.execute(statement)

    def commit(self): self.raw.commit()
    def rollback(self): self.raw.rollback()
    def close(self): self.raw.close()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.rollback() if exc_type else self.commit()
        finally:
            self.close()


def connect(path, database_url=None):
    if database_url:
        return PostgresConnection(database_url)
    c = sqlite3.connect(path, timeout=15, factory=SQLiteConnection)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c
