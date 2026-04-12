"""Database helpers for the ops API."""
from __future__ import annotations

from contextlib import contextmanager
import logging
from threading import Lock
from typing import Any, Iterator

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError, ThreadedConnectionPool

from .config import settings


logger = logging.getLogger('uvicorn.error')
_pool_lock = Lock()
_pool_maxconn = max(settings.db_pool_minconn, settings.db_pool_maxconn)
_peak_active_connections = 0
_borrow_count = 0
_pressure_logged = False

_connection_pool = ThreadedConnectionPool(
    minconn=max(1, settings.db_pool_minconn),
    maxconn=_pool_maxconn,
    host=settings.db_host,
    database=settings.db_name,
    user=settings.db_user,
    password=settings.db_password,
    cursor_factory=RealDictCursor,
)


def _pool_snapshot() -> dict[str, Any]:
    used = len(getattr(_connection_pool, '_used', {}))
    idle = len(getattr(_connection_pool, '_pool', []))
    return {
        'used': used,
        'idle': idle,
        'max': _pool_maxconn,
        'peak_used': _peak_active_connections,
        'borrow_count': _borrow_count,
    }


def _maybe_log_pool_state(event: str) -> None:
    global _peak_active_connections, _pressure_logged

    snapshot = _pool_snapshot()
    used = int(snapshot['used'])
    max_connections = int(snapshot['max'])
    utilization = used / max_connections if max_connections else 0

    with _pool_lock:
        if used > _peak_active_connections:
            _peak_active_connections = used
            snapshot['peak_used'] = _peak_active_connections
            logger.info('DB pool peak updated after %s: %s', event, snapshot)

        if utilization >= 0.8 and not _pressure_logged:
            _pressure_logged = True
            logger.warning('DB pool pressure high after %s: %s', event, snapshot)
        elif utilization <= 0.5 and _pressure_logged:
            _pressure_logged = False
            logger.info('DB pool pressure recovered after %s: %s', event, snapshot)


def get_pool_stats() -> dict[str, Any]:
    return _pool_snapshot()


def close_connection_pool() -> None:
    snapshot = _pool_snapshot()
    logger.info('Closing DB pool: %s', snapshot)
    _connection_pool.closeall()


logger.info(
    'Initialized DB pool: host=%s db=%s user=%s minconn=%s maxconn=%s',
    settings.db_host,
    settings.db_name,
    settings.db_user,
    max(1, settings.db_pool_minconn),
    _pool_maxconn,
)


@contextmanager
def get_connection() -> Iterator[PgConnection]:
    global _borrow_count

    try:
        conn = _connection_pool.getconn()
    except PoolError:
        logger.exception('DB pool exhausted while acquiring connection: %s', _pool_snapshot())
        raise

    with _pool_lock:
        _borrow_count += 1

    _maybe_log_pool_state('acquire')

    try:
        yield conn
        if conn.closed == 0:
            conn.commit()
    except Exception:
        if conn.closed == 0:
            conn.rollback()
        raise
    finally:
        if conn.closed == 0:
            conn.rollback()
        _connection_pool.putconn(conn)
        _maybe_log_pool_state('release')